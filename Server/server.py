"""duct-tape latest-device monitoring. No installer commands or license data."""
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone, timedelta
import asyncio
import json
import re
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Annotated, Literal
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from Server.gas_relay import GasRelay, load_schools
from Server.outbox import Outbox, enqueue, initialize

ROOT = Path(__file__).resolve().parent
Text = Annotated[str, Field(min_length=1, max_length=160)]
InstallState = Literal['확인 전', '설치 필요', '설치 중', '정상', '오류']


class Report(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    school_code: Annotated[str, Field(pattern=r'^[A-Z0-9_-]{1,32}$')] | None = None
    grade: Annotated[int, Field(strict=True, ge=1, le=6)] | None = None
    device_id: UUID
    report_id: UUID
    hostname: Text
    serial: Annotated[str, Field(max_length=160)] = ''
    model: Annotated[str, Field(max_length=160)] = ''
    mac: Annotated[str, Field(pattern=r'^$|^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')] = ''
    office: InstallState
    hancom: InstallState
    stage: Literal['Preflight', '01', '02', '03', '04', '05', '06']
    status: Literal['running', 'completed', 'failed']
    error_code: Annotated[str, Field(pattern=r'^[A-Z0-9_]{0,64}$')] = ''
    installer_exit_code: Annotated[int, Field(ge=0, le=4294967295)] | None = None
    reboot_required: bool = False
    observed_at: AwareDatetime

    @field_validator('observed_at')
    @classmethod
    def reject_future(cls, value):
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('clock ahead')
        return value.astimezone(timezone.utc)


def create_app(db_path=None, report_token=None, read_token=None, schools=None, relay=None):
    database = Path(db_path or os.environ.get('DUCT_DB_PATH', ROOT / 'data' / 'monitoring.sqlite3'))
    writer = report_token if report_token is not None else os.environ.get('DUCT_REPORT_TOKEN', '')
    reader = read_token if read_token is not None else os.environ.get('DUCT_READ_TOKEN', '')

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
        used_tokens = {writer, reader}
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
        authenticate(credentials, writer)
        return None

    def require_reader(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
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

    @app.post('/api/report')
    def receive(report: Report, background_tasks: BackgroundTasks, school=Depends(require_writer)):
        if report.school_code != school:
            raise HTTPException(403, 'School scope mismatch')
        if (school is None and report.grade is not None) or (
                school is not None and report.grade is not None
                and report.grade > (6 if registry[school]['school_type'] == 'elementary' else 3)):
            raise HTTPException(422, 'Invalid grade for school')
        payload = report.model_dump(mode='json')
        observed = report.observed_at.isoformat(timespec='microseconds')
        received = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        payload['observed_at'] = observed
        if school is not None:
            payload.update(school_type=registry[school]['school_type'], schema_version=1, received_at=received)
        with closing(connect()) as db, db:
            # Queue event and latest state commit atomically, before network work starts.
            fresh = enqueue(db, payload) if school is not None else True
            updated = False
            if fresh:
                result = db.execute('''INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(school_code, device_id) DO UPDATE SET
                        report_id=excluded.report_id, observed_at=excluded.observed_at,
                        received_at=excluded.received_at, payload=excluded.payload
                    WHERE excluded.observed_at > devices.observed_at
                        AND excluded.report_id != devices.report_id''',
                    (school or '', str(report.device_id), str(report.report_id), observed, received,
                     json.dumps(payload, ensure_ascii=False)))
                updated = result.rowcount == 1
        background_tasks.add_task(queue.drain)
        return {'accepted': True, 'updated': updated}

    @app.get('/api/outbox', dependencies=[Depends(require_reader)])
    def outbox_status():
        return queue.summary()

    @app.get('/api/devices', dependencies=[Depends(require_reader)])
    def devices():
        with closing(connect()) as db:
            rows = db.execute('SELECT payload, received_at FROM devices ORDER BY received_at DESC').fetchall()
        return {'devices': [dict(json.loads(row['payload']), received_at=row['received_at']) for row in rows]}

    @app.get('/')
    def dashboard():
        # Public shell only; asset data is fetched with the read token in memory.
        return FileResponse(ROOT / 'static' / 'index.html')

    @app.get('/dashboard.js')
    def javascript():
        return FileResponse(ROOT / 'static' / 'dashboard.js', media_type='text/javascript')

    @app.get('/dashboard.css')
    def stylesheet():
        return FileResponse(ROOT / 'static' / 'dashboard.css', media_type='text/css')

    return app


app = create_app()
