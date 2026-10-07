"""HTTP controllers: roles are separate from the read-only monitoring token."""
import secrets
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBearer
from Server.models.agent_jobs import Enrollment, JobRequest, AdminJobRequest, JobUpdate, AdminLogin, JoinRequest, AgentHeartbeat
from Server.models.admin_sessions import COOKIE, HEADER
from Server.models.agent_package import build as build_agent_package



def router(store, admin_token, sessions, policy, root):
    routes = APIRouter()
    bearer = HTTPBearer(auto_error=False)

    def token(credentials):
        if credentials is None:
            raise HTTPException(401, 'Unauthorized')
        return credentials.credentials

    def admin(request: Request, credentials=Depends(bearer)):
        if policy.development:
            if request.headers.get(HEADER) != '1':
                raise HTTPException(403, 'Same-origin request required')
            return
        if not admin_token:
            raise HTTPException(503, 'Set DUCT_ADMIN_TOKEN to enable job administration')
        if sessions.authenticated(request):
            return
        if not secrets.compare_digest(token(credentials).encode(), admin_token.encode()):
            raise HTTPException(401, 'Unauthorized')

    def device(role, credentials, request):
        if policy.development and request.headers.get('X-Duct-Device-ID'):
            return policy.device(request, store)
        try:
            return store.authenticate(token(credentials), role)
        except PermissionError:
            raise HTTPException(401, 'Unauthorized') from None

    def client(request: Request, credentials=Depends(bearer)):
        return device('client', credentials, request)

    def agent(request: Request, credentials=Depends(bearer)):
        return device('agent', credentials, request)

    def enqueue(device_id, body):
        try:
            return store.enqueue(device_id, body.action, str(body.request_id))
        except ValueError:
            raise HTTPException(409, 'Prepare Office/Hancom media and license key') from None
        except PermissionError:
            raise HTTPException(403, 'Administrator approval required') from None
        except LookupError:
            raise HTTPException(404, 'Unknown device') from None
        except FileExistsError:
            raise HTTPException(409, 'A job is already pending or request conflicts') from None

    @routes.post('/api/admin/session')
    def login(body: AdminLogin, request: Request, response: Response):
        if request.headers.get(HEADER) != '1':
            raise HTTPException(403, 'Same-origin request required')
        if not admin_token:
            raise HTTPException(503, 'Administrator access is not configured')
        if not secrets.compare_digest(body.token.encode(), admin_token.encode()):
            raise HTTPException(401, 'Unauthorized')
        sessions.revoke(request)
        response.set_cookie(COOKIE, sessions.issue(), max_age=sessions.lifetime,
                            httponly=True, secure=request.url.scheme == 'https',
                            samesite='strict', path='/')
        return {'authenticated': True, 'expires_in': sessions.lifetime}

    @routes.get('/api/admin/session', dependencies=[Depends(admin)])
    def session():
        return {'authenticated': True}

    @routes.delete('/api/admin/session')
    def logout(request: Request, response: Response):
        if request.headers.get(HEADER) != '1':
            raise HTTPException(403, 'Same-origin request required')
        sessions.revoke(request)
        response.delete_cookie(COOKIE, path='/')
        return {'authenticated': False}

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

    @routes.get('/api/config')
    def configuration():
        return {'auth_mode': policy.mode, 'agent_download': '/download/agent.zip'}

    @routes.get('/download/agent.zip')
    def download(request: Request):
        package = build_agent_package(root, str(request.base_url).rstrip('/'))
        return Response(package, media_type='application/zip',
                        headers={'Content-Disposition': 'attachment; filename="duct-tape-agent.zip"'})

    @routes.post('/api/agent/join')
    def join(body: JoinRequest):
        try:
            result = store.join(str(body.device_id), body.hostname)
        except FileExistsError:
            if not policy.development:
                raise HTTPException(409, 'Device already connected') from None
            result = {'device_id': str(body.device_id)}
        if policy.development:
            store.approve(str(body.device_id))
            return {'device_id': str(body.device_id), 'approved': True, 'auth_mode': policy.mode}
        return result | {'auth_mode': policy.mode}

    @routes.post('/api/admin/agents/{device_id}/approve', dependencies=[Depends(admin)])
    def approve(device_id: UUID):
        try:
            store.approve(str(device_id))
        except LookupError:
            raise HTTPException(404, 'Unknown device') from None
        return {'accepted': True}

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
        return store.info(device_id) | {'jobs': store.jobs(device_id)}

    @routes.post('/api/client/jobs')
    def client_request(body: JobRequest, device_id=Depends(client)):
        return enqueue(device_id, body)

    @routes.post('/api/agent/claim')
    def claim(body: AgentHeartbeat = AgentHeartbeat(), device_id=Depends(agent)):
        return {'job': store.claim(device_id, body.setup_ready)}

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
