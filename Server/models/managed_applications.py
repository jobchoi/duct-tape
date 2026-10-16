"""V2 reviewed MSI adapter catalogue. Installer bytes never enter public downloads."""
from contextlib import closing
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import stat
import time
from uuid import UUID, uuid4
from zipfile import ZipFile, BadZipFile
from pydantic import BaseModel, ConfigDict, Field


class AppDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    schema_version: int = Field(default=2, ge=2, le=2)
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,47}$')
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=r'^\d{1,5}\.\d{1,5}\.\d{1,5}(?:\.\d{1,5})?$')
    installer: str = Field(min_length=1, max_length=240)
    product_code: UUID
    enrollment: bool = False

    def descriptor(self):
        value = self.model_dump(mode='json')
        value['product_code'] = '{'+str(self.product_code).upper()+'}'
        value['adapter'] = 'msi-v1'
        return value


def safe_name(name):
    p = PurePosixPath(name)
    return (bool(name) and len(name) < 241 and not p.is_absolute()
            and not any(x in name for x in ('\\', ':', '"', '<', '>', '|', '?', '*'))
            and not any(ord(x)<32 for x in name)
            and not any(x in ('', '.', '..') for x in name.split('/')))


class ManagedApplications:
    def __init__(self, jobs, private_root):
        self.jobs = jobs
        self.root = Path(jobs.database).parent/'application-packages'
        self.private_root = Path(private_root)

    def initialize(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with closing(self.jobs.connect()) as db, db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS managed_apps (
                id TEXT NOT NULL, version TEXT NOT NULL, descriptor TEXT NOT NULL,
                sha256 TEXT NOT NULL, size INTEGER NOT NULL, published INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL, PRIMARY KEY(id,version));
            CREATE TABLE IF NOT EXISTS application_results (
                job_id TEXT NOT NULL, app_id TEXT NOT NULL, result TEXT NOT NULL,
                updated REAL NOT NULL, PRIMARY KEY(job_id,app_id));
            CREATE TABLE IF NOT EXISTS application_audit (
                id TEXT PRIMARY KEY, app_id TEXT NOT NULL, version TEXT NOT NULL,
                action TEXT NOT NULL, created REAL NOT NULL);
            ''')

    def import_package(self, definition, source):
        descriptor = definition.descriptor()
        if not safe_name(definition.installer) or not definition.installer.lower().endswith('.msi'):
            raise ValueError('MSI entry point required')
        try:
            with ZipFile(source) as archive:
                seen = set(); size = 0; matched = False
                entries = archive.infolist()
                if not entries or len(entries) > 10000:
                    raise ValueError('Package entry limit')
                for info in entries:
                    name = info.filename.rstrip('/')
                    if (not safe_name(name) or name.casefold() in seen
                            or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK
                            or info.flag_bits & 1):
                        raise ValueError('Invalid package path')
                    seen.add(name.casefold()); size += info.file_size
                    if size > 2*1024**3:
                        raise ValueError('Expanded package too large')
                    if info.is_dir():
                        continue
                    if PurePosixPath(name).suffix.lower() not in ('.msi', '.exe', '.cab', '.dll'):
                        raise ValueError('Only installer payloads are allowed; exclude credentials/config files')
                    if name == definition.installer:
                        matched = True
                        with archive.open(info) as entry:
                            if entry.read(8) != bytes.fromhex('d0cf11e0a1b11ae1'):
                                raise ValueError('MSI signature missing')
                if not matched:
                    raise ValueError('Installer entry missing')
                if archive.testzip() is not None:
                    raise ValueError('Corrupt package')
        except (BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise ValueError('Invalid ZIP package') from exc
        source = Path(source)
        with source.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        target = self.root/(digest+'.zip')
        # Packages are content addressed; changing an existing version is forbidden.
        with closing(self.jobs.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM managed_apps WHERE id=? AND version=?',
                          (definition.id, definition.version)).fetchone():
                raise FileExistsError('Version already exists')
            if not target.exists():
                os.replace(source, target)
                target.chmod(0o600)
            db.execute('INSERT INTO managed_apps VALUES (?,?,?,?,?,0,?)',
                       (definition.id, definition.version, json.dumps(descriptor), digest,
                        target.stat().st_size, time.time()))
            db.execute('INSERT INTO application_audit VALUES (?,?,?,?,?)',
                       (str(uuid4()),definition.id,definition.version,'import',time.time()))
        return self.get(definition.id, definition.version)

    def get(self, app_id, version):
        with closing(self.jobs.connect()) as db:
            row = db.execute('SELECT * FROM managed_apps WHERE id=? AND version=?', (app_id, version)).fetchone()
        if not row:
            raise LookupError('Application not found')
        return dict(json.loads(row['descriptor']), sha256=row['sha256'], size=row['size'], published=bool(row['published']))

    def list(self, public=False):
        with closing(self.jobs.connect()) as db:
            rows = db.execute('SELECT id,version FROM managed_apps'+(' WHERE published=1' if public else '')+' ORDER BY id,created DESC').fetchall()
        return [self.get(row['id'], row['version']) for row in rows]

    def publish(self, app_id, version, enabled):
        app = self.get(app_id, version)
        if enabled:
            path = self.root/(app['sha256']+'.zip')
            if not path.is_file():
                raise ValueError('Package missing')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != app['sha256']:
                    raise ValueError('Package integrity check failed')
        with closing(self.jobs.connect()) as db, db:
            db.execute('UPDATE managed_apps SET published=? WHERE id=? AND version=?', (int(enabled),app_id,version))
            db.execute('INSERT INTO application_audit VALUES (?,?,?,?,?)',
                       (str(uuid4()),app_id,version,'publish' if enabled else 'unpublish',time.time()))

    def snapshot(self, selected):
        if not selected or len(selected)>16 or len({x.id for x in selected}) != len(selected):
            raise ValueError('Select distinct applications')
        result=[]
        for ref in selected:
            app=self.get(ref.id,ref.version)
            if not app['published']:
                raise ValueError('Application is not published')
            result.append(app)
        return result

    def plan(self, device_id, job_id):
        with closing(self.jobs.connect()) as db:
            row=db.execute('''SELECT p.plan,j.state FROM application_plans p JOIN agent_jobs j ON j.id=p.job_id
                              WHERE p.job_id=? AND j.device_id=?''',(job_id,device_id)).fetchone()
        if not row:
            raise LookupError('Unknown application job')
        return json.loads(row['plan']),row['state']

    def record_result(self, device_id, job_id, app_id, result):
        plan,state=self.plan(device_id,job_id)
        app=next((x for x in plan if x['id']==app_id),None)
        if not app:
            raise LookupError('App is outside this job')
        if result['enrollment'] != ('required' if app['enrollment'] else 'not_required'):
            raise ValueError('Enrollment must not be inferred from installation')
        payload=json.dumps(result,sort_keys=True)
        with closing(self.jobs.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT result FROM application_results WHERE job_id=? AND app_id=?',(job_id,app_id)).fetchone()
            if old:
                if old['result']!=payload:
                    raise FileExistsError('Conflicting result')
                return
            current=db.execute('SELECT state FROM agent_jobs WHERE id=? AND device_id=?',(job_id,device_id)).fetchone()
            if not current or current['state'] not in ('running','interrupted'):
                raise FileExistsError('Job is not running')
            db.execute('INSERT INTO application_results VALUES (?,?,?,?)',(job_id,app_id,payload,time.time()))

    def results(self, job_ids):
        if not job_ids:
            return []
        with closing(self.jobs.connect()) as db:
            rows=db.execute('SELECT * FROM application_results WHERE job_id IN ('+','.join('?' for _ in job_ids)+')',job_ids).fetchall()
            plans={r['job_id']:json.loads(r['plan']) for r in db.execute(
                'SELECT * FROM application_plans WHERE job_id IN ('+','.join('?' for _ in job_ids)+')',job_ids)}
        result=[]
        for row in rows:
            app=next((a for a in plans.get(row['job_id'],[]) if a['id']==row['app_id']),{})
            result.append(dict(job_id=row['job_id'],app_id=row['app_id'],name=app.get('name',row['app_id']),
                               version=app.get('version',''),updated=row['updated'],**json.loads(row['result'])))
        return result

    def secret_status(self):
        """Only readiness is returned. Credentials are never sent to agents/browser."""
        path=self.private_root/'Config/ArgosEnrollment.json'
        if not path.is_file():
            return {'configured':False,'automatic_enrollment':False}
        if os.name != 'nt' and path.stat().st_mode & 0o077:
            return {'configured':False,'automatic_enrollment':False,'reason':'Restrict file permissions to 600'}
        try:
            if path.stat().st_size>16384:
                raise ValueError
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            configured=all(isinstance(data.get(k),str) and bool(data[k].strip()) for k in ('email','username','password','server_url'))
        except (ValueError,OSError):
            configured=False
        return {'configured':configured,'automatic_enrollment':False}
