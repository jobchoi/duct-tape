from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, ZipInfo
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app

ADMIN='admin-'+'a'*40
W='writer-'+'w'*40
R='reader-'+'r'*40
GUID='A23A2428-0549-4AF0-8C9B-85F60CBE9AE7'


def auth(token):return {'Authorization':'Bearer '+token}


def manifest(**kw):
    return dict(id='argos-mdm',name='Argos <script>alert(1)</script>',version='1.1.7',
                product_code=GUID,installer='ArgosMDMSetup.msi',enrollment=True,**kw)


def package(entries=None):
    stream=BytesIO()
    with ZipFile(stream,'w') as archive:
        for name,data in (entries or {'ArgosMDMSetup.msi':bytes.fromhex('d0cf11e0a1b11ae1')+b'fixture'}).items():
            archive.writestr(ZipInfo(name,date_time=(2026,1,1,0,0,0)),data)
    return stream.getvalue()


@pytest.fixture
def api(tmp_path):
    with TestClient(create_app(tmp_path/'db',W,R,schools={},admin_token=ADMIN,media_root=tmp_path/'media')) as client:
        yield client


def register(c):
    code=c.post('/api/admin/enrollments',headers=auth(ADMIN)).json()['code']
    return c.post('/api/agent/register',json={'device_id':str(uuid4()),'hostname':'TEST-PC','code':code}).json()


def upload(c,metadata=None,data=None):
    return c.post('/api/admin/applications',headers=auth(ADMIN),
        data={'manifest':json.dumps(metadata or manifest())},files={'package':('app.zip',data or package(),'application/zip')})


def publish(c,enabled=True,reviewed=True):
    return c.put('/api/admin/applications/argos-mdm/1.1.7',headers=auth(ADMIN),json={'published':enabled,'reviewed':reviewed})


def enqueue(c,keys,request_id=None):
    return c.post('/api/client/application-jobs',headers=auth(keys['client_token']),
        json={'request_id':request_id or str(uuid4()),'applications':[{'id':'argos-mdm','version':'1.1.7'}]})


def result(**kw):
    return dict(status='installed',exit_code=0,verified=True,reboot_required=False,enrollment='required',**kw)


def test_draft_publish_protocol_snapshot_and_result_scope(api):
    c=api;keys=register(c);other=register(c)
    assert upload(c).status_code==200
    assert upload(c).status_code==409
    assert c.get('/api/admin/applications').status_code==401
    assert c.get('/api/client/applications',headers=auth(keys['client_token'])).json()['applications']==[]
    assert publish(c,reviewed=False).status_code==422
    assert publish(c).status_code==200
    assert len(c.get('/api/client/applications',headers=auth(keys['client_token'])).json()['applications'])==1
    assert enqueue(c,keys).status_code==409 # old agent cannot take a v2 job
    c.post('/api/agent/claim',headers=auth(keys['agent_token']),json={'protocol_version':2})
    request_id=str(uuid4());response=enqueue(c,keys,request_id)
    assert response.status_code==200,response.text
    job=response.json();jid=job['id']
    assert enqueue(c,keys,request_id).json()['id']==jid
    assert enqueue(c,keys).status_code==409 # one active job per PC, including v1
    assert c.post('/api/agent/claim',headers=auth(keys['agent_token'])).json()['job'] is None
    claim=c.post('/api/agent/claim',headers=auth(keys['agent_token']),json={'protocol_version':2}).json()['job']
    assert claim['id']==jid
    base='/api/agent/jobs/'+jid
    assert c.get(base+'/application-plan',headers=auth(other['agent_token'])).status_code==404
    plan=c.get(base+'/application-plan',headers=auth(keys['agent_token'])).json()
    assert plan['applications'][0]['version']=='1.1.7'
    assert publish(c,False).status_code==200 # in-flight job retains its frozen plan
    endpoint=base+'/applications/argos-mdm/package'
    assert c.get(endpoint,headers=auth(keys['agent_token'])).content==package()
    ranged=c.get(endpoint,headers=dict(auth(keys['agent_token']),Range='bytes=0-9'))
    assert ranged.status_code==206 and ranged.content==package()[:10]
    assert c.get(endpoint,headers=auth(other['agent_token'])).status_code==404
    assert c.get(endpoint,headers=auth(keys['client_token'])).status_code==401
    assert c.get(base+'/applications/other/package',headers=auth(keys['agent_token'])).status_code==404
    done={'state':'succeeded','exit_code':0}
    assert c.post(base,headers=auth(keys['agent_token']),json=done).status_code==409
    endpoint=base+'/applications/argos-mdm/result'
    invalid=result();invalid['enrollment']='not_required'
    assert c.post(endpoint,headers=auth(keys['agent_token']),json=invalid).status_code==422
    invalid=result();invalid['verified']=False
    assert c.post(endpoint,headers=auth(keys['agent_token']),json=invalid).status_code==422
    assert c.post(endpoint,headers=auth(keys['agent_token']),json=result()).status_code==200
    assert c.post(endpoint,headers=auth(keys['agent_token']),json=result()).status_code==200
    changed=result();changed['reboot_required']=True
    assert c.post(endpoint,headers=auth(keys['agent_token']),json=changed).status_code==409
    assert c.post(base,headers=auth(keys['agent_token']),json=done).status_code==200
    results=c.get('/api/client/application-results',headers=auth(keys['client_token'])).json()['results']
    assert results[0]['verified'] and results[0]['enrollment']=='required'
    assert c.get('/api/client/application-results',headers=auth(other['client_token'])).json()['results']==[]


@pytest.mark.parametrize('entries',[
    {'../evil.msi':b'fixture'}, {'/absolute.msi':b'fixture'}, {'C:/evil.msi':b'fixture'},
    {'ArgosMDMSetup.msi':b'not an MSI'}, {'credentials.json':b'private'},
    {'ArgosMDMSetup.msi':b'x','argosmdmsetup.MSI':b'y'},
    {'bad"name.msi':b'fixture'}, {'Modules/evil.ps1':b'Write-Host no'},
])
def test_rejects_unsafe_or_invalid_packages(api,entries):
    assert upload(api,data=package(entries)).status_code==422
    assert api.get('/api/admin/applications',headers=auth(ADMIN)).json()['applications']==[]


def test_credentials_remain_private_and_not_in_public_zip(api,tmp_path):
    private=tmp_path/'media/Config/ArgosEnrollment.json';private.parent.mkdir(parents=True)
    private.write_text(json.dumps(dict(email='private-email',username='private-user',password='PRIVATE-PASSWORD',server_url='https://private.example')))
    private.chmod(0o600)
    response=api.get('/api/admin/applications',headers=auth(ADMIN))
    assert response.json()['enrollment_config']=={'configured':True,'automatic_enrollment':False}
    assert 'PRIVATE-PASSWORD' not in response.text and 'private-user' not in response.text
    data=api.get('/download/agent.zip').content
    with ZipFile(BytesIO(data)) as z:
        assert 'duct-tape-agent/Scripts/RunApplicationJob.ps1' in z.namelist()
        assert not any('ArgosEnrollment' in name for name in z.namelist())
    private.chmod(0o644)
    assert api.get('/api/admin/applications',headers=auth(ADMIN)).json()['enrollment_config']['configured'] is False


def test_pending_pc_and_unauthorized_upload(api):
    joined=api.post('/api/agent/join',json={'device_id':str(uuid4()),'hostname':'PENDING'}).json()
    assert api.get('/api/client/applications',headers=auth(joined['client_token'])).status_code==403
    assert api.post('/api/admin/applications',data={'manifest':json.dumps(manifest())},files={'package':('x.zip',package())}).status_code==401
