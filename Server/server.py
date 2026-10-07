"""duct-tape latest-device monitoring. No installer commands or license data."""
from contextlib import asynccontextmanager, closing
import asyncio
import re
import os
from pathlib import Path
import secrets
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer



from Server.gas_relay import GasRelay, load_schools
from Server.outbox import Outbox, initialize
from Server.models.agent_jobs import JobStore
from Server.models.admin_sessions import AdminSessions
from Server.controllers.agent_jobs import router as agent_router
from Server.controllers.monitoring import router as monitoring_router
from Server.models.monitoring import Report
from Server.controllers.artifacts import router as artifact_router
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent

def create_app(db_path=None, report_token=None, read_token=None, schools=None, relay=None, admin_token=None):
    database = Path(db_path or os.environ.get('DUCT_DB_PATH', ROOT / 'data' / 'monitoring.sqlite3'))
    writer = report_token if report_token is not None else os.environ.get('DUCT_REPORT_TOKEN', '')
    reader = read_token if read_token is not None else os.environ.get('DUCT_READ_TOKEN', '')

    administrator = admin_token if admin_token is not None else os.environ.get('DUCT_ADMIN_TOKEN', '')
    jobs = JobStore(database)
    sessions = AdminSessions()
    registry = load_schools() if schools is None else schools
    queue = Outbox(database, relay if relay is not None else GasRelay(registry),
                   int(os.environ.get('DUCT_SENT_RETENTION_DAYS', '30')))

    def connect():
        connection = sqlite3.connect(database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @asynccontextmanager
    async def lifespan(app):
        if (len(writer) < 32 or len(reader) < 32 or writer == reader
                or not writer.isascii() or not reader.isascii()
                or any(c.isspace() for c in writer + reader)):
            raise RuntimeError('Set distinct ASCII DUCT_REPORT_TOKEN and DUCT_READ_TOKEN (32+ characters).')
        if administrator and (len(administrator) < 32 or not administrator.isascii()
                or any(c.isspace() for c in administrator) or administrator in (writer, reader)):
            raise RuntimeError('Set a distinct ASCII DUCT_ADMIN_TOKEN (32+ characters).')
        used_tokens = {writer, reader, administrator}
        for code, school in registry.items():
            token = school.get('report_token', '')
            if (not re.fullmatch(r'[A-Z0-9_-]{1,32}', code)
                    or school.get('school_type') not in ('elementary', 'middle', 'high')
                    or len(token) < 32 or not token.isascii() or any(c.isspace() for c in token)
                    or token in used_tokens):
                raise RuntimeError('Invalid school registration or non-distinct report token.')
            used_tokens.add(token)
        database.parent.mkdir(parents=True, exist_ok=True)
        initialize(database)
        jobs.initialize()
        recovery = asyncio.create_task(asyncio.to_thread(queue.drain))
        try:
            yield
        finally:
            await recovery

    app = FastAPI(title='duct-tape monitoring', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.outbox = queue

    bearer = HTTPBearer(auto_error=False)

    def authenticate(credentials, expected):
        if (credentials is None or not secrets.compare_digest(
                credentials.credentials.encode('utf-8'), expected.encode('utf-8'))):
            raise HTTPException(401, 'Unauthorized', headers={'WWW-Authenticate': 'Bearer'})

    def require_writer(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            authenticate(credentials, writer)
        token = credentials.credentials.encode('utf-8')
        for code, school in registry.items():
            if secrets.compare_digest(token, school['report_token'].encode('utf-8')):
                return code
        try:
            jobs.report_identity(credentials.credentials)
            return None
        except PermissionError:
            authenticate(credentials, writer)
        return None

    def reporting_device(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is not None:
            try:
                return jobs.report_identity(credentials.credentials)
            except PermissionError:
                pass
        return None

    def require_reader(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not sessions.authenticated(request):
            authenticate(credentials, reader)

    @app.exception_handler(RequestValidationError)
    async def invalid_report(request, exc):
        # Do not reflect input values (including accidental secret fields).
        return JSONResponse({'detail': 'Invalid report schema or timestamp'}, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def unavailable(request, exc):
        return JSONResponse({'detail': 'Storage unavailable'}, status_code=503)

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    app.include_router(monitoring_router(queue, connect, registry, require_writer, require_reader, reporting_device))
    app.include_router(agent_router(jobs, administrator, sessions))
    app.include_router(artifact_router(ROOT.parent / "uploads", administrator))
    (ROOT.parent / "downloads").mkdir(exist_ok=True)
    app.mount("/files", StaticFiles(directory=ROOT.parent / "downloads"), name="files")

    @app.get('/dashboard.js')
    def javascript():
        return FileResponse(ROOT / 'static' / 'dashboard.js', media_type='text/javascript')

    @app.get('/dashboard.css')
    def stylesheet():
        return FileResponse(ROOT / 'static' / 'dashboard.css', media_type='text/css')

    return app


app = create_app()
