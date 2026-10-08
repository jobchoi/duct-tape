"""No-token local workflow, downloadable agent, and media readiness gates."""
from io import BytesIO
from zipfile import ZipFile
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.agent_package import FILES

H={'X-Duct-Tape-Request':'1'}

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'db',auth_mode='development',schools={},media_root=tmp_path/'missing-media'),base_url='https://testserver') as c:
        yield c


def test_local_connection_duplicate_readiness_and_complete_job(client):
    assert client.get('/api/config').json()['auth_mode']=='development'
    assert client.get('/api/admin/agents',headers=H).status_code==200
    assert client.get('/api/admin/agents').status_code==403
    identity=str(uuid4())
    body={'device_id':identity,'hostname':'TEST-PC'}
    joined=client.post('/api/agent/join',json=body).json()
    assert joined=={'device_id':identity,'approved':True,'auth_mode':'development'}
    assert client.post('/api/agent/join',json=body).status_code==200
    assert len(client.get('/api/admin/agents',headers=H).json()['agents'])==1
    headers=H|{'X-Duct-Device-ID':identity}
    assert client.get('/api/client/jobs',headers=headers).json()['hostname']=='TEST-PC'
    request={'action':'deploy','request_id':str(uuid4())}
    assert client.post('/api/client/jobs',json=request,headers=headers).status_code==409
    assert client.post('/api/agent/claim',json={'setup_ready':False},headers=headers).json()['job'] is None
    client.post('/api/agent/claim',json={'setup_ready':True},headers=headers)
    job=client.post('/api/client/jobs',json=request,headers=headers).json()
    assert job['state']=='queued'
    claim=client.post('/api/agent/claim',headers=headers).json()['job']
    assert claim['id']==job['id']
    assert client.post('/api/agent/claim',headers=headers).json()['job'] is None
    assert client.post('/api/agent/jobs/'+job['id'],json={'state':'succeeded','exit_code':0},headers=headers).status_code==200
    assert client.get('/api/client/jobs',headers=headers).json()['jobs'][0]['state']=='succeeded'
    assert client.get('/api/client/jobs',headers=H|{'X-Duct-Device-ID':str(uuid4())}).status_code==401


def test_download_contains_runnable_files_without_secrets(client):
    response=client.get('/download/agent.zip')
    assert response.status_code==200 and 'attachment' in response.headers['content-disposition']
    with ZipFile(BytesIO(response.content)) as archive:
        names=set(archive.namelist())
        assert { 'duct-tape-agent/'+name for name in FILES } <= names
        assert archive.read('duct-tape-agent/Config/ServerUrl.txt')==b'https://testserver'
        assert not any(name.endswith(('.env','Agent.json','HancomKey.txt','OfficeKey.txt','Monitoring.json')) for name in names)
        script=archive.read('duct-tape-agent/Scripts/InstallAgent.ps1').decode('utf-8-sig')
        assert 'Get-AgentRegistration' in script and 'CommonDesktopDirectory' in script
        assert '/api/agent/join' in archive.read('duct-tape-agent/Scripts/AgentRegistration.ps1').decode('utf-8-sig')
        assert "Start-Process $url" in script


def test_download_and_initial_install_are_visible(client):
    html=client.get('/client').text
    assert 'href="/download/agent.zip"' in html and 'id="onboarding"' in html
    admin=client.get('/admin').text
    assert 'id="admin-content" hidden' in admin and 'id="auth-status"' in admin
