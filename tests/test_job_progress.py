from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app

ADMIN='admin-'+'a'*40
WRITE='writer-'+'w'*40
READ='reader-'+'r'*40

def auth(token):return {'Authorization':'Bearer '+token}

@pytest.fixture
def api(tmp_path):
    with TestClient(create_app(tmp_path/'db',WRITE,READ,schools={},admin_token=ADMIN,media_root=tmp_path/'empty')) as c:yield c

def device(c):
    code=c.post('/api/admin/enrollments',headers=auth(ADMIN)).json()['code']
    return c.post('/api/agent/register',json={'code':code,'device_id':str(uuid4()),'hostname':'TEST-PC'}).json()

def job(c,keys):
    j=c.post('/api/client/jobs',json={'action':'report-test','request_id':str(uuid4())},headers=auth(keys['client_token'])).json()
    c.post('/api/agent/claim',headers=auth(keys['agent_token']))
    return j

def test_progress_scope_counters_dedup_and_cursor(api):
    c=api;keys=device(c);other=device(c);j=job(c,keys)
    url='/api/agent/jobs/'+j['id']+'/progress'
    event={'sequence':1,'phase':'download','status':'progress','current':50,'total':100,'unit':'bytes'}
    assert c.post(url,json={'events':[event]},headers=auth(other['agent_token'])).status_code==404
    assert c.post(url,json={'events':[event]},headers=auth(keys['client_token'])).status_code==401
    assert c.post(url,json={'events':[event]},headers=auth(keys['agent_token'])).status_code==200
    assert c.post(url,json={'events':[event]},headers=auth(keys['agent_token'])).status_code==200
    assert c.post(url,json={'events':[event|{'current':60}]},headers=auth(keys['agent_token'])).status_code==409
    response=c.get('/api/client/jobs/'+j['id']+'/progress',headers=auth(keys['client_token'])).json()
    assert len(response['events'])==2 and response['events'][1]['current']==50
    assert response['events'][1]['label']=='설치 매체 다운로드'
    assert len(c.get('/api/admin/jobs/'+j['id']+'/progress?after=0',headers=auth(ADMIN)).json()['events'])==1
    assert c.get('/api/client/jobs/'+j['id']+'/progress',headers=auth(other['client_token'])).status_code==404

def test_terminal_state_and_secret_free_validation(api):
    c=api;keys=device(c);j=job(c,keys);url='/api/agent/jobs/'+j['id']+'/progress'
    event={'sequence':1,'phase':'module','status':'started','module':'04_InstallOffice.ps1','current':3,'total':6,'unit':'steps'}
    for invalid in (event|{'message':'SECRET-KEY'},event|{'module':'arbitrary-secret'},event|{'current':7},event|{'phase':'unknown'},event|{'sequence':True}):
        response=c.post(url,json={'events':[invalid]},headers=auth(keys['agent_token']))
        assert response.status_code==422 and 'SECRET-KEY' not in response.text
    assert c.post(url,json={'events':[event]},headers=auth(keys['agent_token'])).status_code==200
    assert c.post('/api/agent/jobs/'+j['id'],json={'state':'succeeded','exit_code':0},headers=auth(keys['agent_token'])).status_code==200
    assert c.post(url,json={'events':[event]},headers=auth(keys['agent_token'])).status_code==200
    assert c.post(url,json={'events':[event|{'sequence':2}]},headers=auth(keys['agent_token'])).status_code==409
    events=c.get('/api/client/jobs/'+j['id']+'/progress',headers=auth(keys['client_token'])).json()['events']
    assert events[-1]['phase']=='complete' and events[-1]['sequence']==2147483647
    assert events[1]['label']=='Office 설치 단계'

def test_live_agent_heartbeat_resumes_status_without_reclaiming_install(api):
    import sqlite3
    c=api;keys=device(c);j=job(c,keys)
    # Simulate a server/network gap while the same installer process is alive.
    from pathlib import Path
    # Use the public state transition to model a missed heartbeat.
    c.post('/api/agent/jobs/'+j['id'],json={'state':'interrupted'},headers=auth(keys['agent_token']))
    assert c.post('/api/agent/claim',headers=auth(keys['agent_token'])).json()['job'] is None
    assert c.post('/api/agent/jobs/'+j['id'],json={'state':'running'},headers=auth(keys['agent_token'])).status_code==200
    assert c.post('/api/agent/claim',headers=auth(keys['agent_token'])).json()['job'] is None
    assert c.get('/api/client/jobs',headers=auth(keys['client_token'])).json()['jobs'][0]['state']=='running'

def test_older_agent_shows_latest_stage_without_fabricated_event(api):
    from datetime import datetime,timezone
    c=api;keys=device(c);j=job(c,keys)
    payload={'device_id':keys['device_id'],'report_id':str(uuid4()),'hostname':'TEST-PC','grade':1,'office':'설치 중','hancom':'확인 전','stage':'04','status':'running','observed_at':datetime.now(timezone.utc).isoformat()}
    assert c.post('/api/report',json=payload,headers=auth(WRITE)).status_code==200
    response=c.get('/api/client/jobs/'+j['id']+'/progress',headers=auth(keys['client_token'])).json()
    assert response['legacy']['label']=='Office 설치 단계'
    assert response['legacy']['status']=='running'
    assert [e['sequence'] for e in response['events']]==[0]
