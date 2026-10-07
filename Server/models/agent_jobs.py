"""Persistent device credentials and finite, non-replayed deployment jobs."""
from contextlib import closing
import hashlib
import secrets
import sqlite3
import time
from uuid import uuid4, UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class JobStore:
    def __init__(self, database):
        self.database = database

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        with closing(self.connect()) as db, db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS agent_enrollment (
                code_hash TEXT PRIMARY KEY, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS agents (
                device_id TEXT PRIMARY KEY, hostname TEXT NOT NULL,
                agent_hash TEXT NOT NULL UNIQUE, client_hash TEXT NOT NULL UNIQUE,
                last_seen REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS agent_jobs (
                id TEXT PRIMARY KEY, device_id TEXT NOT NULL, action TEXT NOT NULL,
                state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                exit_code INTEGER, request_id TEXT NOT NULL,
                UNIQUE(device_id, request_id));
            ''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(agents)')}
            if 'approved' not in columns:
                db.execute('ALTER TABLE agents ADD COLUMN approved INTEGER NOT NULL DEFAULT 1')

    def enrollment(self):
        code = secrets.token_urlsafe(32)
        with closing(self.connect()) as db, db:
            db.execute('DELETE FROM agent_enrollment WHERE expires < ?', (time.time(),))
            db.execute('INSERT INTO agent_enrollment VALUES (?,?)', (digest(code), time.time()+600))
        return code

    def register(self, code, device_id, hostname):
        agent, client = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT expires FROM agent_enrollment WHERE code_hash=?', (digest(code),)).fetchone()
            if not row or row['expires'] < time.time():
                raise PermissionError
            if db.execute('SELECT 1 FROM agents WHERE device_id=?', (device_id,)).fetchone():
                raise FileExistsError
            db.execute('DELETE FROM agent_enrollment WHERE code_hash=?', (digest(code),))
            db.execute('INSERT INTO agents VALUES (?,?,?,?,?,1)',
                       (device_id, hostname, digest(agent), digest(client), time.time()))
        return dict(agent_token=agent, client_token=client, device_id=device_id)

    def authenticate(self, token, role):
        column = 'agent_hash' if role == 'agent' else 'client_hash'
        with closing(self.connect()) as db:
            row = db.execute(f'SELECT device_id FROM agents WHERE {column}=?', (digest(token),)).fetchone()
        if not row:
            raise PermissionError
        return row['device_id']

    def join(self, device_id, hostname):
        agent, client = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM agents WHERE device_id=?', (device_id,)).fetchone():
                raise FileExistsError
            db.execute('INSERT INTO agents VALUES (?,?,?,?,?,0)',
                       (device_id, hostname, digest(agent), digest(client), time.time()))
        return dict(agent_token=agent, client_token=client, device_id=device_id, approved=False)

    def info(self, device_id):
        with closing(self.connect()) as db:
            row = db.execute('SELECT device_id, hostname, approved, last_seen FROM agents WHERE device_id=?', (device_id,)).fetchone()
        if not row:
            raise LookupError
        return dict(row)

    def approve(self, device_id):
        with closing(self.connect()) as db, db:
            if not db.execute('UPDATE agents SET approved=1 WHERE device_id=?', (device_id,)).rowcount:
                raise LookupError

    def report_identity(self, token):
        identity = self.authenticate(token, 'agent')
        if not self.info(identity)['approved']:
            raise PermissionError
        return identity

    @staticmethod
    def expire(db):
        # Never retry a possibly started installer after a lost agent connection.
        db.execute("UPDATE agent_jobs SET state='interrupted', updated=? WHERE state='running' AND updated < ?",
                   (time.time(), time.time()-120))

    def agents(self):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute('SELECT device_id, hostname, last_seen, approved FROM agents ORDER BY hostname')]

    def jobs(self, device_id=None):
        with closing(self.connect()) as db, db:
            self.expire(db)
            where, args = (' WHERE device_id=?', (device_id,)) if device_id else ('', ())
            return [dict(row) for row in db.execute('SELECT * FROM agent_jobs'+where+' ORDER BY created DESC LIMIT 100', args)]

    def enqueue(self, device_id, action, request_id):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self.expire(db)
            identity = db.execute('SELECT approved FROM agents WHERE device_id=?', (device_id,)).fetchone()
            if not identity:
                raise LookupError
            if not identity['approved']:
                raise PermissionError
            old = db.execute('SELECT * FROM agent_jobs WHERE device_id=? AND request_id=?', (device_id, request_id)).fetchone()
            if old:
                if old['action'] != action:
                    raise FileExistsError
                return dict(old)
            if db.execute("SELECT 1 FROM agent_jobs WHERE device_id=? AND state IN ('queued','running','interrupted')", (device_id,)).fetchone():
                raise FileExistsError
            now, job_id = time.time(), str(uuid4())
            db.execute('INSERT INTO agent_jobs VALUES (?,?,?,?,?,?,?,?)',
                       (job_id, device_id, action, 'queued', now, now, None, request_id))
            return dict(db.execute('SELECT * FROM agent_jobs WHERE id=?', (job_id,)).fetchone())

    def claim(self, device_id):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self.expire(db)
            db.execute('UPDATE agents SET last_seen=? WHERE device_id=?', (time.time(), device_id))
            if not db.execute('SELECT 1 FROM agents WHERE device_id=? AND approved=1', (device_id,)).fetchone():
                return None
            row = db.execute("SELECT * FROM agent_jobs WHERE device_id=? AND state='queued' ORDER BY created LIMIT 1", (device_id,)).fetchone()
            if not row:
                return None
            db.execute("UPDATE agent_jobs SET state='running', updated=? WHERE id=?", (time.time(), row['id']))
            return dict(row) | {'state': 'running'}

    def update(self, device_id, job_id, state, exit_code):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM agent_jobs WHERE id=? AND device_id=?', (job_id, device_id)).fetchone()
            if not row:
                raise LookupError
            if row['state'] == state and state != 'running':
                if row['exit_code'] != exit_code:
                    raise FileExistsError
                return
            if row['state'] not in ('running', 'interrupted') or (row['state'] == 'interrupted' and state == 'running'):
                raise FileExistsError
            db.execute('UPDATE agent_jobs SET state=?, updated=?, exit_code=? WHERE id=?', (state, time.time(), exit_code, job_id))
            db.execute('UPDATE agents SET last_seen=? WHERE device_id=?', (time.time(), device_id))

    def resolve(self, job_id):
        with closing(self.connect()) as db, db:
            changed = db.execute("UPDATE agent_jobs SET state='failed', exit_code=1, updated=? WHERE id=? AND state='interrupted'", (time.time(), job_id)).rowcount
            if not changed:
                raise FileExistsError

    def revoke(self, device_id):
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM agent_jobs WHERE device_id=? AND state IN ('running','interrupted')", (device_id,)).fetchone():
                raise FileExistsError
            db.execute("UPDATE agent_jobs SET state='cancelled', updated=? WHERE device_id=? AND state='queued'", (time.time(), device_id))
            db.execute('DELETE FROM agents WHERE device_id=?', (device_id,))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Enrollment(StrictModel):
    code: str = Field(min_length=32, max_length=128)
    device_id: UUID
    hostname: str = Field(min_length=1, max_length=160)


class JobRequest(StrictModel):
    action: Literal['report-test', 'deploy']
    request_id: UUID


class AdminJobRequest(JobRequest):
    device_id: UUID


class JobUpdate(StrictModel):
    state: Literal['running', 'succeeded', 'failed', 'interrupted']
    exit_code: int | None = Field(default=None, ge=0, le=4294967295, strict=True)

    @model_validator(mode='after')
    def valid_result(self):
        if ((self.state in ('running', 'interrupted') and self.exit_code is not None)
                or (self.state == 'succeeded' and self.exit_code != 0)
                or (self.state == 'failed' and (self.exit_code is None or self.exit_code == 0))):
            raise ValueError('Invalid result')
        return self


class AdminLogin(StrictModel):
    token: str = Field(min_length=32, max_length=512)


class JoinRequest(StrictModel):
    device_id: UUID
    hostname: str = Field(min_length=1, max_length=160)
