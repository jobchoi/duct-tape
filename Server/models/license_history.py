"""Encrypted, append-only product-key revisions; no plaintext management reads."""
from contextlib import closing
from pathlib import Path
import os
import re
import threading
import time
from uuid import uuid4
from cryptography.fernet import Fernet

KEYS = {'office': 'Config/OfficeKey.txt', 'hancom': 'Config/HancomKey.txt'}


def normalize(app, value):
    if app not in KEYS or not isinstance(value, str):
        raise ValueError('Invalid product key')
    value = value.strip()
    pattern = r'[A-Za-z0-9]{5}(?:-[A-Za-z0-9]{5}){4}' if app == 'office' else r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*'
    if not re.fullmatch(pattern, value) or len(value) > 160 or value in ('REPLACE_WITH_YOUR_LICENSE_KEY', 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX'):
        raise ValueError('Invalid product key')
    return value.upper() if app == 'office' else value


class LicenseHistory:
    def __init__(self, jobs, media_root):
        self.jobs, self.media_root = jobs, Path(media_root)
        self.directory = Path(jobs.database).parent/'license-vault'
        self._lock = threading.Lock()
        self._ready = False

    def ensure(self):
        with self._lock:
            if self._ready:
                return
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            keyfile = self.directory/'master.key'
            with closing(self.jobs.connect()) as db, db:
                db.executescript('''
                    CREATE TABLE IF NOT EXISTS license_revisions (
                      id TEXT PRIMARY KEY, app TEXT NOT NULL, label TEXT NOT NULL, note TEXT NOT NULL,
                      ciphertext BLOB NOT NULL, masked TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL);
                    CREATE TABLE IF NOT EXISTS license_active (app TEXT PRIMARY KEY, revision TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS license_audit (
                      id INTEGER PRIMARY KEY AUTOINCREMENT, app TEXT NOT NULL, revision TEXT NOT NULL,
                      previous TEXT, action TEXT NOT NULL, created REAL NOT NULL);
                ''')
                db.execute('CREATE TABLE IF NOT EXISTS license_job_revisions (job_id TEXT NOT NULL, app TEXT NOT NULL, revision TEXT NOT NULL, received REAL NOT NULL, PRIMARY KEY(job_id,app))')
                if not keyfile.exists():
                    if db.execute('SELECT COUNT(*) FROM license_revisions').fetchone()[0]:
                        raise RuntimeError('License recovery key missing')
                    try:
                        fd = os.open(keyfile, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                    except FileExistsError:
                        pass
                    else:
                        with os.fdopen(fd, 'wb') as out:
                            out.write(Fernet.generate_key()); out.flush(); os.fsync(out.fileno())
                self.cipher = Fernet(keyfile.read_bytes())
                # Existing key files are preserved, imported once, never treated as verified.
                for app, relative in KEYS.items():
                    if db.execute('SELECT 1 FROM license_revisions WHERE app=?', (app,)).fetchone():
                        continue
                    source = self.media_root/relative
                    if not source.is_file() or not source.resolve().is_relative_to(self.media_root.resolve()):
                        continue
                    try:
                        value = normalize(app, source.read_text(encoding='utf-8-sig'))
                    except (ValueError, OSError, UnicodeError):
                        continue
                    rev = self._insert(db, app, value, '기존 서버 파일', '기존 원본에서 최초 가져옴. 실제 설치 확인 전입니다.')
                    db.execute('INSERT INTO license_active VALUES (?,?)', (app, rev))
                    self._audit(db, app, rev, None, 'import')
            self._ready = True

    def _insert(self, db, app, value, label, note):
        rev = str(uuid4())
        db.execute('INSERT INTO license_revisions VALUES (?,?,?,?,?,?,?,?)',
                   (rev, app, label, note, self.cipher.encrypt(value.encode()), '•••••-'+value[-5:], 'candidate', time.time()))
        return rev

    def _audit(self, db, app, rev, previous, action):
        db.execute('INSERT INTO license_audit(app,revision,previous,action,created) VALUES (?,?,?,?,?)',
                   (app, rev, previous, action, time.time()))

    def listing(self):
        self.ensure()
        with closing(self.jobs.connect()) as db:
            rows = db.execute('SELECT id,app,label,note,masked,status,created FROM license_revisions ORDER BY created DESC').fetchall()
            active = dict(db.execute('SELECT app,revision FROM license_active'))
            audit = [dict(r) for r in db.execute('SELECT * FROM license_audit ORDER BY id DESC LIMIT 100')]
            usage = [dict(r) for r in db.execute('SELECT k.*,j.state,j.exit_code FROM license_job_revisions k LEFT JOIN agent_jobs j ON j.id=k.job_id ORDER BY k.received DESC LIMIT 100')]
        return {'revisions': [dict(r, active=active.get(r['app']) == r['id']) for r in rows], 'audit': audit,
                'usage': usage, 'retention': 'all', 'minimum_verified_retained': 3}

    def save(self, app, value, label, note):
        value = normalize(app, value)
        self.ensure()
        with closing(self.jobs.connect()) as db, db:
            rev = self._insert(db, app, value, label, note)
            self._audit(db, app, rev, None, 'save')
        return rev

    def change(self, app, rev, action):
        if action not in ('apply', 'restore', 'verify', 'fail'):
            raise ValueError('Unknown change')
        self.ensure()
        with closing(self.jobs.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM license_revisions WHERE id=? AND app=?', (rev, app)).fetchone()
            if row is None:
                raise LookupError('Unknown revision')
            if db.execute("SELECT 1 FROM agent_jobs WHERE action='deploy' AND state IN ('queued','running','interrupted') LIMIT 1").fetchone():
                raise FileExistsError('A setup job is pending')
            previous = db.execute('SELECT revision FROM license_active WHERE app=?', (app,)).fetchone()
            previous = previous[0] if previous else None
            if action in ('apply', 'restore'):
                if row['status'] == 'failed' or (action == 'restore' and row['status'] != 'verified'):
                    raise ValueError('Restore requires a verified revision')
                self.cipher.decrypt(row['ciphertext'])  # verify recoverability before activation
                db.execute('INSERT INTO license_active VALUES (?,?) ON CONFLICT(app) DO UPDATE SET revision=excluded.revision', (app, rev))
            else:
                db.execute('UPDATE license_revisions SET status=? WHERE id=?', ('verified' if action == 'verify' else 'failed', rev))
            self._audit(db, app, rev, previous, action)

    def record_usage(self, device_id):
        self.ensure()
        with closing(self.jobs.connect()) as db, db:
            job = db.execute("SELECT id FROM agent_jobs WHERE device_id=? AND action='deploy' AND state='running' ORDER BY created DESC LIMIT 1", (device_id,)).fetchone()
            if job:
                db.execute('INSERT OR IGNORE INTO license_job_revisions SELECT ?,app,revision,? FROM license_active', (job[0], time.time()))

    def snapshot(self):
        self.ensure()
        with closing(self.jobs.connect()) as db:
            rows = db.execute('SELECT r.* FROM license_revisions r JOIN license_active a ON a.revision=r.id').fetchall()
        return {r['app']: (self.cipher.decrypt(r['ciphertext']) if r['status'] != 'failed' else None) for r in rows}
