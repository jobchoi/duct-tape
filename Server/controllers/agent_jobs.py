"""HTTP controllers: roles are separate from the read-only monitoring token."""
import secrets
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBearer
from Server.models.agent_jobs import Enrollment, JobRequest, AdminJobRequest, JobUpdate



def router(store, admin_token):
    routes = APIRouter()
    bearer = HTTPBearer(auto_error=False)

    def token(credentials):
        if credentials is None:
            raise HTTPException(401, 'Unauthorized')
        return credentials.credentials

    def admin(credentials=Depends(bearer)):
        if not admin_token:
            raise HTTPException(503, 'Set DUCT_ADMIN_TOKEN to enable job administration')
        if not secrets.compare_digest(token(credentials).encode(), admin_token.encode()):
            raise HTTPException(401, 'Unauthorized')

    def device(role, credentials):
        try:
            return store.authenticate(token(credentials), role)
        except PermissionError:
            raise HTTPException(401, 'Unauthorized') from None

    def client(credentials=Depends(bearer)):
        return device('client', credentials)

    def agent(credentials=Depends(bearer)):
        return device('agent', credentials)

    def enqueue(device_id, body):
        try:
            return store.enqueue(device_id, body.action, str(body.request_id))
        except LookupError:
            raise HTTPException(404, 'Unknown device') from None
        except FileExistsError:
            raise HTTPException(409, 'A job is already pending or request conflicts') from None

    @routes.post('/api/admin/enrollments', dependencies=[Depends(admin)])
    def enrollment():
        return {'code': store.enrollment(), 'expires_in': 600}

    @routes.post('/api/agent/register')
    def register(body: Enrollment):
        try:
            return store.register(body.code, str(body.device_id), body.hostname)
        except PermissionError:
            raise HTTPException(401, 'Invalid or expired enrollment') from None
        except FileExistsError:
            raise HTTPException(409, 'Device already registered') from None

    @routes.get('/api/admin/agents', dependencies=[Depends(admin)])
    def agents():
        return {'agents': store.agents()}

    @routes.get('/api/admin/jobs', dependencies=[Depends(admin)])
    def jobs():
        return {'jobs': store.jobs()}

    @routes.post('/api/admin/jobs', dependencies=[Depends(admin)])
    def request(body: AdminJobRequest):
        return enqueue(str(body.device_id), body)

    @routes.get('/api/client/jobs')
    def client_jobs(device_id=Depends(client)):
        return {'device_id': device_id, 'jobs': store.jobs(device_id)}

    @routes.post('/api/client/jobs')
    def client_request(body: JobRequest, device_id=Depends(client)):
        return enqueue(device_id, body)

    @routes.post('/api/agent/claim')
    def claim(device_id=Depends(agent)):
        return {'job': store.claim(device_id)}

    @routes.post('/api/agent/jobs/{job_id}')
    def update(job_id: UUID, body: JobUpdate, device_id=Depends(agent)):
        try:
            store.update(device_id, str(job_id), body.state, body.exit_code)
        except LookupError:
            raise HTTPException(404, 'Unknown job') from None
        except FileExistsError:
            raise HTTPException(409, 'Invalid job transition') from None
        return {'accepted': True}

    @routes.post('/api/admin/jobs/{job_id}/resolve', dependencies=[Depends(admin)])
    def resolve(job_id: UUID):
        try:
            store.resolve(str(job_id))
        except FileExistsError:
            raise HTTPException(409, 'Only interrupted jobs can be resolved') from None
        return {'accepted': True}

    @routes.post('/api/admin/agents/{device_id}/revoke', dependencies=[Depends(admin)])
    def revoke(device_id: UUID):
        try:
            store.revoke(str(device_id))
        except FileExistsError:
            raise HTTPException(409, 'Inspect and resolve active jobs before revoking') from None
        return {'accepted': True}

    views = Path(__file__).resolve().parents[1] / 'views'
    @routes.get('/')
    def home():
        return RedirectResponse('/client', status_code=307)

    @routes.get('/client')
    def client_page():
        return FileResponse(views / 'client.html')

    @routes.get('/admin')
    def admin_page():
        return FileResponse(views / 'admin.html')

    @routes.get('/portal.js')
    def javascript():
        return FileResponse(views / 'portal.js', media_type='text/javascript')

    return routes
