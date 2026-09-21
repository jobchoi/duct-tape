"""Transactional queue with cross-process leases and bounded replay batches."""
from contextlib import closing
import json
import random
import sqlite3
import threading
import time
from uuid import uuid4

from Server.gas_relay import RelayError


def initialize(database):
    """Offline/startup migration. Back up Phase 3 rows before changing their key."""
    with closing(sqlite3.connect(database, timeout=10)) as db:
        columns = [row[1] for row in db.execute('PRAGMA table_info(devices)')]
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 4:
            raise RuntimeError('Database schema is newer than this server.')
        if columns and 'school_code' not in columns:
            backup_path = str(database) + '.phase3-backup.sqlite3'
            # Exclusive creation avoids silently replacing the original backup.
            try:
                with open(backup_path, 'xb'):
                    pass
            except FileExistsError:
                raise RuntimeError('Migration backup already exists; inspect it before retrying.') from None
            with closing(sqlite3.connect(backup_path)) as backup:
                db.backup(backup)
        db.execute('PRAGMA journal_mode=WAL')
        with db:
            db.execute('BEGIN IMMEDIATE')
            if columns and 'school_code' not in columns:
                db.execute('ALTER TABLE devices RENAME TO devices_phase3')
            db.execute('''CREATE TABLE IF NOT EXISTS devices (
                school_code TEXT NOT NULL, device_id TEXT NOT NULL, report_id TEXT NOT NULL,
                observed_at TEXT NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(school_code, device_id))''')
            if columns and 'school_code' not in columns:
                db.execute("INSERT INTO devices SELECT '', device_id, report_id, observed_at, received_at, payload FROM devices_phase3")
                db.execute('DROP TABLE devices_phase3')
            db.execute('''CREATE TABLE IF NOT EXISTS outbox (
                school_code TEXT NOT NULL, report_id TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at REAL NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
                owner TEXT, last_error TEXT NOT NULL DEFAULT '', sent_at REAL,
                PRIMARY KEY(school_code, report_id))''')
            db.execute('CREATE INDEX IF NOT EXISTS outbox_due ON outbox(state, next_attempt_at)')
            db.execute('PRAGMA user_version=4')


def enqueue(db, payload):
    return db.execute('INSERT OR IGNORE INTO outbox(school_code,report_id,payload) VALUES(?,?,?)',
                      (payload['school_code'], payload['report_id'], json.dumps(payload, ensure_ascii=False))).rowcount == 1


class Outbox:
    def __init__(self, database, relay, retention_days=30, sleep=time.sleep):
        if not 1 <= retention_days <= 3650:
            raise ValueError('Retention must be between 1 and 3650 days.')
        self.database, self.relay, self.retention_days, self.sleep = database, relay, retention_days, sleep
        self.slots = threading.BoundedSemaphore(2)
        self.last_error = ''

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def claim(self):
        now, owner = time.time(), str(uuid4())
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE outbox SET state=CASE WHEN attempts>=3 THEN 'failed' ELSE 'pending' END, owner=NULL, last_error='lease_expired' WHERE state='sending' AND lease_until<=?", (now,))
            db.execute("DELETE FROM outbox WHERE state='sent' AND sent_at<?", (now-self.retention_days*86400,))
            # Across app processes and CLI, at most two jobs have live leases.
            if db.execute("SELECT count(*) FROM outbox WHERE state='sending'").fetchone()[0] >= 2:
                return None
            row = db.execute("SELECT * FROM outbox WHERE state='pending' AND next_attempt_at<=? ORDER BY next_attempt_at, rowid LIMIT 1", (now,)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE outbox SET state='sending', owner=?, lease_until=? WHERE school_code=? AND report_id=?",
                       (owner, now+180, row['school_code'], row['report_id']))
            return dict(row) | {'owner': owner}

    def process(self, row):
        identity = (row['school_code'], row['report_id'], row['owner'])
        for attempt in range(row['attempts']+1, 4):
            with closing(self.connect()) as db, db:
                owned = db.execute("UPDATE outbox SET attempts=?, lease_until=? WHERE school_code=? AND report_id=? AND owner=? AND state='sending'",
                                   (attempt, time.time()+180, *identity)).rowcount
            if not owned:
                return
            error, retryable = '', False
            try:
                self.relay.send(json.loads(row['payload']))
            except RelayError as exc:
                error, retryable = exc.code, exc.retryable
            except Exception:
                error = 'relay_internal'
            retry = bool(error and retryable and attempt < 3)
            delay = 2 ** (attempt-1) + random.uniform(0, 0.25) if retry else 0
            with closing(self.connect()) as db, db:
                db.execute('''UPDATE outbox SET state=?, last_error=?, next_attempt_at=?, sent_at=?,
                              lease_until=?, owner=? WHERE school_code=? AND report_id=? AND owner=?''',
                           ('sending' if retry else ('failed' if error else 'sent'), error, time.time()+delay,
                            None if error else time.time(), time.time()+180 if retry else 0,
                            row['owner'] if retry else None, *identity))
            if not retry:
                return
            self.sleep(delay)

    def drain(self, limit=50):
        # A failing relay or queue worker can never escape into the report response.
        if not self.slots.acquire(blocking=False):
            return
        try:
            for _ in range(limit):
                row = self.claim()
                if row is None:
                    break
                self.process(row)
            self.last_error = ''
        except Exception:
            self.last_error = 'queue_unavailable'
        finally:
            self.slots.release()

    def replay_failed(self):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE outbox SET state='pending', attempts=0, next_attempt_at=0, owner=NULL, lease_until=0 WHERE state='failed'")

    def summary(self):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT state,last_error,count(*) AS count FROM outbox GROUP BY state,last_error').fetchall()
        return {'groups': [dict(row) for row in rows], 'worker_error': self.last_error}
