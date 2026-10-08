from datetime import datetime, timezone
from uuid import uuid4
import sqlite3
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.agent_jobs import JobStore

ADMIN='admin-'+ 'a'*40
READ='read-'+ 'r'*40
WRITE='write-'+ 'w'*40

def auth(value):
    return {'Authorization':'Bearer '+value}

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'db.sqlite3', WRITE, READ, schools={}, admin_token=ADMIN, media_root=tmp_path/'missing-media')) as c:
        yield c

def join(c):
    body={'device_id':str(uuid4()),'hostname':'CLIENT-PC'}
    response=c.post('/api/agent/join',json=body)
    assert response.status_code==200
    return response.json(), body

def request():
    return {'action':'deploy','request_id':str(uuid4())}

def test_automatic_join_requires_approval_before_setup(client):
    keys,body=join(client)
    assert not keys['approved']
    data=client.get('/api/client/jobs',headers=auth(keys['client_token'])).json()
    assert data['hostname']=='CLIENT-PC' and not data['approved']
    assert client.post('/api/client/jobs',json=request(),headers=auth(keys['client_token'])).status_code==403
    assert client.post('/api/agent/claim',headers=auth(keys['agent_token'])).json()['job'] is None
    url='/api/admin/agents/'+keys['device_id']+'/approve'
    assert client.post(url,headers=auth(READ)).status_code==401
    assert client.post(url,headers=auth(keys['agent_token'])).status_code==401
    assert client.post(url,headers=auth(ADMIN)).status_code==200
    assert client.get('/api/client/jobs',headers=auth(keys['client_token'])).json()['approved']
    client.post('/api/agent/claim',json={'setup_ready':True},headers=auth(keys['agent_token']))
    job=client.post('/api/client/jobs',json=request(),headers=auth(keys['client_token'])).json()
    assert job['state']=='queued'
    assert client.post('/api/agent/claim',headers=auth(keys['agent_token'])).json()['job']['id']==job['id']
    assert client.post('/api/agent/join',json=body).status_code==409

def test_approved_agent_reports_only_its_own_device(client):
    keys,_=join(client)
    payload={'grade':1,'device_id':keys['device_id'],'report_id':str(uuid4()),'hostname':'CLIENT-PC','office':'확인 전','hancom':'확인 전','stage':'Preflight','status':'running','observed_at':datetime.now(timezone.utc).isoformat()}
    assert client.post('/api/report',json=payload,headers=auth(keys['agent_token'])).status_code==401
    client.post('/api/admin/agents/'+keys['device_id']+'/approve',headers=auth(ADMIN))
    assert client.post('/api/report',json=payload,headers=auth(keys['agent_token'])).status_code==200
    assert client.post('/api/report',json=payload|{'device_id':str(uuid4())},headers=auth(keys['agent_token'])).status_code==403
    assert client.post('/api/report',json=payload,headers=auth(keys['client_token'])).status_code==401

def test_legacy_agents_keep_approval_during_migration(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE agents(device_id TEXT PRIMARY KEY,hostname TEXT,agent_hash TEXT UNIQUE,client_hash TEXT UNIQUE,last_seen REAL)')
        db.execute('INSERT INTO agents VALUES (?,?,?,?,?)',(str(uuid4()),'OLD-PC','agent-hash','client-hash',0))
    store=JobStore(path);store.initialize();store.initialize()
    assert store.agents()[0]['approved']==1

def test_pages_have_separate_basic_flows_and_no_code_login(client):
    admin=client.get('/admin').text
    user=client.get('/client').text
    assert 'href="/client"' not in admin and 'href="/admin"' not in user
    assert 'id="enroll"' not in admin
    assert 'id="access-token"' not in user
    assert '환경 셋업 시작' in user
    assert '<select' not in admin and '<select' not in user
