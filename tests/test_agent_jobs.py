from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.agent_jobs import JobStore

ADMIN = 'admin-' + 'a'*40
READ = 'read-' + 'r'*40
WRITE = 'write-' + 'w'*40

def auth(token):
    return {'Authorization': 'Bearer ' + token}

@pytest.fixture
def api(tmp_path):
    db = tmp_path/'state.db'
    with TestClient(create_app(db, WRITE, READ, schools={}, admin_token=ADMIN)) as client:
        yield client, db

def register(client):
    code = client.post('/api/admin/enrollments', headers=auth(ADMIN)).json()['code']
    body = {'code': code, 'device_id': str(uuid4()), 'hostname': 'TEST-PC'}
    result = client.post('/api/agent/register', json=body)
    assert result.status_code == 200
    return result.json(), body

def request(action='report-test', **extra):
    return dict(action=action, request_id=str(uuid4()), **extra)

def test_pages_and_privilege_separation(api):
    c, _ = api
    assert c.get('/', follow_redirects=False).headers['location'] == '/client'
    assert '이 PC 환경 셋업' in c.get('/client').text
    assert '연결된 PC' in c.get('/admin').text
    for token in (READ, WRITE, 'wrong'):
        assert c.post('/api/admin/enrollments', headers=auth(token)).status_code == 401
    keys, _ = register(c)
    assert c.get('/api/client/jobs', headers=auth(keys['agent_token'])).status_code == 401
    assert c.post('/api/agent/claim', headers=auth(keys['client_token'])).status_code == 401
    assert c.post('/api/admin/enrollments', headers=auth(keys['client_token'])).status_code == 401
    agents = c.get('/api/admin/agents', headers=auth(ADMIN)).text
    assert keys['agent_token'] not in agents and keys['client_token'] not in agents

def test_enrollment_single_use_expiry_and_duplicate(api):
    c, db = api
    keys, body = register(c)
    assert c.post('/api/agent/register', json=body).status_code == 401
    code = c.post('/api/admin/enrollments', headers=auth(ADMIN)).json()['code']
    assert c.post('/api/agent/register', json=body | {'code': code}).status_code == 409
    with sqlite3.connect(db) as conn:
        conn.execute('UPDATE agent_enrollment SET expires=0')
    assert c.post('/api/agent/register', json=body | {'code': code, 'device_id': str(uuid4())}).status_code == 401
    with sqlite3.connect(db) as conn:
        stored = str(conn.execute('SELECT * FROM agents').fetchall())
    assert keys['agent_token'] not in stored and keys['client_token'] not in stored

def test_job_lifecycle_and_device_isolation(api):
    c, _ = api
    first, _ = register(c)
    second, _ = register(c)
    body = request('deploy')
    job = c.post('/api/client/jobs', json=body, headers=auth(first['client_token'])).json()
    assert c.post('/api/client/jobs', json=body, headers=auth(first['client_token'])).json()['id'] == job['id']
    assert c.post('/api/client/jobs', json=request(), headers=auth(first['client_token'])).status_code == 409
    assert c.get('/api/client/jobs', headers=auth(second['client_token'])).json()['jobs'] == []
    assert c.post('/api/agent/claim', headers=auth(second['agent_token'])).json()['job'] is None
    assert c.post('/api/agent/claim', headers=auth(first['agent_token'])).json()['job']['id'] == job['id']
    assert c.post('/api/agent/claim', headers=auth(first['agent_token'])).json()['job'] is None
    url = '/api/agent/jobs/'+job['id']
    assert c.post(url, json={'state':'succeeded', 'exit_code':0}, headers=auth(second['agent_token'])).status_code == 404
    assert c.post(url, json={'state':'running'}, headers=auth(first['agent_token'])).status_code == 200
    assert c.post(url, json={'state':'succeeded', 'exit_code':0}, headers=auth(first['agent_token'])).status_code == 200
    assert c.post(url, json={'state':'succeeded', 'exit_code':0}, headers=auth(first['agent_token'])).status_code == 200
    assert c.post(url, json={'state':'failed', 'exit_code':1}, headers=auth(first['agent_token'])).status_code == 409
    assert c.post('/api/client/jobs', json=request(action='powershell'), headers=auth(first['client_token'])).status_code == 422
    assert c.post('/api/client/jobs', json=request(device_id=second['device_id']), headers=auth(first['client_token'])).status_code == 422

def test_interrupted_never_replayed_and_admin_recovery(api):
    c, db = api
    keys, _ = register(c)
    job = c.post('/api/client/jobs', json=request('deploy'), headers=auth(keys['client_token'])).json()
    c.post('/api/agent/claim', headers=auth(keys['agent_token']))
    with sqlite3.connect(db) as conn:
        conn.execute('UPDATE agent_jobs SET updated=0')
    assert c.get('/api/client/jobs', headers=auth(keys['client_token'])).json()['jobs'][0]['state'] == 'interrupted'
    assert c.post('/api/agent/claim', headers=auth(keys['agent_token'])).json()['job'] is None
    assert c.post('/api/client/jobs', json=request(), headers=auth(keys['client_token'])).status_code == 409
    assert c.post('/api/admin/jobs/'+job['id']+'/resolve', headers=auth(READ)).status_code == 401
    assert c.post('/api/admin/jobs/'+job['id']+'/resolve', headers=auth(ADMIN)).status_code == 200
    assert c.post('/api/admin/agents/'+keys['device_id']+'/revoke', headers=auth(ADMIN)).status_code == 200
    assert c.get('/api/client/jobs', headers=auth(keys['client_token'])).status_code == 401
    assert c.post('/api/agent/claim', headers=auth(keys['agent_token'])).status_code == 401

def test_concurrent_claim_and_persistence(api):
    c, db = api
    keys, _ = register(c)
    job = c.post('/api/admin/jobs', json=request(device_id=keys['device_id']), headers=auth(ADMIN)).json()
    store = JobStore(db)
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: JobStore(db).claim(keys['device_id']), range(8)))
    assert sum(j is not None for j in claims) == 1
    assert store.jobs(keys['device_id'])[0]['id'] == job['id']
    assert store.authenticate(keys['agent_token'], 'agent') == keys['device_id']
    assert c.post('/api/admin/agents/'+keys['device_id']+'/revoke', headers=auth(ADMIN)).status_code == 409
    assert c.post('/api/agent/jobs/'+job['id'], json={'state':'succeeded','exit_code':1}, headers=auth(keys['agent_token'])).status_code == 422

def test_artifact_upload_cannot_overwrite_agent_scripts(tmp_path):
    from fastapi import FastAPI
    from Server.controllers.artifacts import router
    app = FastAPI()
    app.include_router(router(tmp_path, ADMIN))
    with TestClient(app) as c:
        files = {'file': ('../../Scripts/Agent.ps1', b'test-file')}
        assert c.post('/api/upload', files=files).status_code == 401
        assert c.post('/api/upload', files=files, headers=auth(WRITE)).status_code == 401
        response = c.post('/api/upload', files=files, headers=auth(ADMIN))
        assert response.status_code == 200
        name = response.json()['id']
        assert '/' not in name and (tmp_path/name).read_bytes() == b'test-file'

def test_agent_restart_marks_claim_interrupted(api):
    c, _ = api
    keys, _ = register(c)
    job = c.post('/api/client/jobs', json=request('deploy'), headers=auth(keys['client_token'])).json()
    c.post('/api/agent/claim', headers=auth(keys['agent_token']))
    url = '/api/agent/jobs/'+job['id']
    assert c.post(url, json={'state':'interrupted'}, headers=auth(keys['agent_token'])).status_code == 200
    assert c.post(url, json={'state':'interrupted'}, headers=auth(keys['agent_token'])).status_code == 200
    assert c.post('/api/client/jobs', json=request(), headers=auth(keys['client_token'])).status_code == 409
    assert c.post('/api/agent/claim', headers=auth(keys['agent_token'])).json()['job'] is None

def test_revoking_cancels_queued_work_and_allows_new_enrollment(api):
    c, _ = api
    keys, body = register(c)
    job = c.post('/api/client/jobs', json=request(), headers=auth(keys['client_token'])).json()
    assert c.post('/api/admin/agents/'+keys['device_id']+'/revoke', headers=auth(ADMIN)).status_code == 200
    assert c.get('/api/admin/jobs', headers=auth(ADMIN)).json()['jobs'][0]['state'] == 'cancelled'
    code = c.post('/api/admin/enrollments', headers=auth(ADMIN)).json()['code']
    assert c.post('/api/agent/register', json=body | {'code':code}).status_code == 200
    assert c.post('/api/agent/claim', headers=auth(keys['agent_token'])).status_code == 401

def test_agent_reconnect_rotates_browser_key_and_blocks_active_work(api):
    c,_=api
    keys,_=register(c)
    assert c.get('/api/agent/status',headers=auth(keys['agent_token'])).json()['device_id']==keys['device_id']
    assert c.post('/api/agent/reconnect',headers=auth(keys['client_token'])).status_code==401
    result=c.post('/api/agent/reconnect',headers=auth(keys['agent_token']))
    assert result.status_code==200
    new=result.json()['client_token']
    assert c.get('/api/client/jobs',headers=auth(keys['client_token'])).status_code==401
    assert c.get('/api/client/jobs',headers=auth(new)).status_code==200
    assert 'agent_token' not in result.json()
    c.post('/api/client/jobs',json=request(),headers=auth(new))
    assert c.post('/api/agent/reconnect',headers=auth(keys['agent_token'])).status_code==409
    assert c.get('/api/client/jobs',headers=auth(new)).status_code==200
