"""V2 catalogue UI/API using the existing admin sessions and PC credentials."""
from pathlib import Path
import json
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_STORED
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
from Server.models.managed_applications import AppDefinition


class AppRef(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,47}$')
    version: str = Field(pattern=r'^\d{1,5}\.\d{1,5}\.\d{1,5}(?:\.\d{1,5})?$')


class InstallRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: UUID
    applications: list[AppRef] = Field(min_length=1,max_length=16)


class Publish(BaseModel):
    model_config=ConfigDict(extra='forbid')
    published: bool = Field(strict=True)
    reviewed: bool = False


class AppResult(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status: Literal['installed','already_installed','failed']
    exit_code: int = Field(ge=0,le=4294967295,strict=True)
    verified: bool = Field(strict=True)
    reboot_required: bool = Field(strict=True)
    enrollment: Literal['required','not_required']
    error_code: Literal['','INSTALL_FAILED','VERIFY_FAILED','PACKAGE_INVALID','APP_OPERATION_FAILED'] = ''


def router(store, catalogue, admin, client, agent, root):
    routes=APIRouter()

    @routes.get('/admin/apps')
    @routes.get('/client/apps')
    def page():
        return FileResponse(root/'Server/views/applications.html')

    @routes.get('/applications.js')
    def javascript():
        return FileResponse(root/'Server/views/applications.js',media_type='text/javascript')

    @routes.get('/applications.css')
    def stylesheet():
        return FileResponse(root/'Server/views/applications.css',media_type='text/css')

    @routes.get('/api/admin/applications',dependencies=[Depends(admin)])
    def admin_list():
        return {'applications':catalogue.list(), 'enrollment_config':catalogue.secret_status()}

    @routes.post('/api/admin/applications',dependencies=[Depends(admin)])
    def import_app(manifest: str = Form(...), package: UploadFile = File(...)):
        path=None
        try:
            if len(manifest)>4096:
                raise ValueError('Manifest too large')
            definition=AppDefinition.model_validate_json(manifest)
            with NamedTemporaryFile(dir=catalogue.root,suffix='.upload',delete=False) as target:
                path=Path(target.name);size=0
                while chunk:=package.file.read(1024*1024):
                    size+=len(chunk)
                    if size>512*1024**2:
                        raise ValueError('Package exceeds 512 MB')
                    target.write(chunk)
            return catalogue.import_package(definition,path)
        except FileExistsError:
            raise HTTPException(409,'This app version already exists; create a new version') from None
        except ValidationError:
            raise HTTPException(422,'Invalid MSI application manifest') from None
        except (ValueError,OSError):
            raise HTTPException(422,'Invalid installer package or manifest; check MSI path and exclude configuration files') from None
        finally:
            package.file.close()
            if path:
                path.unlink(missing_ok=True)

    @routes.post('/api/admin/applications/import-argos',dependencies=[Depends(admin)])
    def import_argos():
        definition=AppDefinition(id='argos-mdm',name='Argos MDM Agent',version='1.1.7',
            installer='ArgosMDMSetup.msi',product_code='A23A2428-0549-4AF0-8C9B-85F60CBE9AE7',enrollment=True)
        try:
            catalogue.get('argos-mdm','1.1.7')
        except LookupError:
            pass
        else:
            raise HTTPException(409,'Argos 1.1.7 draft already exists')
        source=next((p for p in (catalogue.private_root/'ArgosMDM',catalogue.private_root/'Tools/ArgosMDM')
                     if (p/'ArgosMDMSetup.msi').is_file() and (p/'setup.exe').is_file()),None)
        if source is None:
            raise HTTPException(409,'Place the original MSI and setup.exe in the server media root ArgosMDM directory')
        for name in ('ArgosMDMSetup.msi','setup.exe'):
            if not (source/name).resolve().is_relative_to(catalogue.private_root.resolve()):
                raise HTTPException(422,'Invalid source link')
        path=None
        try:
            with NamedTemporaryFile(dir=catalogue.root,suffix='.upload',delete=False) as target:
                path=Path(target.name)
            with ZipFile(path,'w',ZIP_STORED) as archive:
                for name in ('ArgosMDMSetup.msi','setup.exe'):
                    archive.write(source/name,name)
            return catalogue.import_package(definition,path)
        except FileExistsError:
            raise HTTPException(409,'Argos 1.1.7 draft already exists') from None
        except ValueError:
            raise HTTPException(422,'Invalid Argos package') from None
        finally:
            if path:
                path.unlink(missing_ok=True)

    @routes.put('/api/admin/applications/{app_id}/{version}',dependencies=[Depends(admin)])
    def publish(app_id: str,version: str,body: Publish):
        if body.published and not body.reviewed:
            raise HTTPException(422,'Review the MSI prerequisites and unattended installation before publishing')
        try:
            catalogue.publish(app_id,version,body.published)
        except LookupError:
            raise HTTPException(404,'Unknown application') from None
        except ValueError:
            raise HTTPException(409,'Package missing or corrupt') from None
        return {'published':body.published}

    @routes.get('/api/client/applications')
    def client_list(device_id=Depends(client)):
        if not store.info(device_id)['approved']:
            raise HTTPException(403,'Administrator approval required')
        return {'applications':catalogue.list(public=True)}

    def allowed_client(device_id):
        if not store.info(device_id)['approved']:
            raise HTTPException(403,'Administrator approval required')

    @routes.get('/api/admin/mdm/registration',dependencies=[Depends(admin)])
    def admin_registration():
        return JSONResponse(catalogue.registration_details(),headers={'Cache-Control':'no-store'})

    @routes.get('/api/client/mdm/registration')
    def client_registration(device_id=Depends(client)):
        allowed_client(device_id)
        return JSONResponse(catalogue.registration_details(),headers={'Cache-Control':'no-store'})

    def manual_package(app_id,version):
        try:
            app=catalogue.get(app_id,version)
        except LookupError:
            raise HTTPException(404,'Unknown application') from None
        if app_id!='argos-mdm' or not app['published']:
            raise HTTPException(404,'No published MDM download')
        path=catalogue.root/(app['sha256']+'.zip')
        if not path.is_file():
            raise HTTPException(409,'Package missing')
        return FileResponse(path,media_type='application/zip',filename='ArgosMDM-'+version+'.zip',
                            headers={'Cache-Control':'no-store'})

    @routes.get('/api/admin/mdm/{version}/package',dependencies=[Depends(admin)])
    def admin_manual_package(version: str):
        return manual_package('argos-mdm',version)

    @routes.get('/api/client/mdm/{version}/package')
    def client_manual_package(version: str,device_id=Depends(client)):
        allowed_client(device_id)
        return manual_package('argos-mdm',version)

    def enqueue(device_id,body):
        try:
            plan=catalogue.snapshot(body.applications)
            if any(app['id']=='argos-mdm' for app in plan):
                raise HTTPException(409,'MDM is download-only; install and enroll manually')
            return store.enqueue(device_id,'install-apps',str(body.request_id),application_plan=plan)
        except LookupError:
            raise HTTPException(404,'Unknown PC or application') from None
        except PermissionError:
            raise HTTPException(403,'Administrator approval required') from None
        except FileExistsError:
            raise HTTPException(409,'An active/interrupted job exists, or request ID conflicts') from None
        except ValueError:
            raise HTTPException(409,'Update PC to the v2 agent and select published distinct apps') from None

    @routes.post('/api/client/application-jobs')
    def request(body: InstallRequest,device_id=Depends(client)):
        return enqueue(device_id,body)

    @routes.post('/api/admin/agents/{device_id}/application-jobs',dependencies=[Depends(admin)])
    def admin_request(device_id: UUID,body: InstallRequest):
        return enqueue(str(device_id),body)

    def plan(device_id,job_id):
        if not store.info(device_id)['approved']:
            raise HTTPException(403,'Administrator approval required')
        try:
            value,state=catalogue.plan(device_id,str(job_id))
        except LookupError:
            raise HTTPException(404,'Unknown job') from None
        return value,state

    @routes.get('/api/agent/jobs/{job_id}/application-plan')
    def agent_plan(job_id: UUID,device_id=Depends(agent)):
        value,state=plan(device_id,job_id)
        if state not in ('running','interrupted'):
            raise HTTPException(409,'Job is not active')
        return {'schema_version':2,'applications':value}

    @routes.get('/api/agent/jobs/{job_id}/applications/{app_id}/package')
    def package(job_id: UUID,app_id: str,device_id=Depends(agent)):
        value,state=plan(device_id,job_id)
        app=next((x for x in value if x['id']==app_id),None)
        if not app:
            raise HTTPException(404,'Application is outside this job')
        if state!='running':
            raise HTTPException(409,'Job is not running')
        path=catalogue.root/(app['sha256']+'.zip')
        if not path.is_file():
            raise HTTPException(409,'Package missing')
        return FileResponse(path,media_type='application/zip',filename=app['sha256']+'.zip')

    @routes.post('/api/agent/jobs/{job_id}/applications/{app_id}/result')
    def result(job_id: UUID,app_id: str,body: AppResult,device_id=Depends(agent)):
        plan(device_id,job_id)
        if body.status!='failed' and (not body.verified or body.exit_code not in (0,3010) or body.error_code):
            raise HTTPException(422,'Installation success requires verification')
        if body.status=='failed' and body.verified:
            raise HTTPException(422,'Failure cannot be verified success')
        if body.status=='failed' and not body.error_code:
            raise HTTPException(422,'Failure requires a fixed error code')
        try:
            catalogue.record_result(device_id,str(job_id),app_id,body.model_dump())
        except LookupError:
            raise HTTPException(404,'Application is outside this job') from None
        except FileExistsError:
            raise HTTPException(409,'Result conflicts or job has ended') from None
        except ValueError:
            raise HTTPException(422,'Enrollment state cannot be inferred') from None
        return {'accepted':True}

    @routes.get('/api/admin/application-results',dependencies=[Depends(admin)])
    def admin_results():
        return {'jobs':store.jobs(), 'results':catalogue.results([j['id'] for j in store.jobs()])}

    @routes.get('/api/client/application-results')
    def client_results(device_id=Depends(client)):
        jobs=store.jobs(device_id)
        return {'jobs':jobs,'results':catalogue.results([j['id'] for j in jobs])}

    return routes
