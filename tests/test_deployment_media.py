from io import BytesIO
from zipfile import ZipFile
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.deployment_media import DeploymentMedia, REQUIRED

ADMIN='admin-'+'a'*40
WRITE='writer-'+'w'*40
READ='reader-'+'r'*40

def auth(value): return {'Authorization':'Bearer '+value}

@pytest.fixture
def source(tmp_path):
    root=tmp_path/'source'
    for name in REQUIRED:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test-placeholder')
    (root/'Office/extra.cab').write_bytes(b'full-media')
    (root/'.env').write_bytes(b'not-for-clients')
    return root


def test_configured_ignored_files_are_transferred_privately(tmp_path,source):
    with TestClient(create_app(tmp_path/'db',WRITE,READ,schools={},admin_token=ADMIN,media_root=source)) as c:
        assert c.get('/api/config').json()['media']['ready']
        identity=str(uuid4())
        keys=c.post('/api/agent/join',json={'device_id':identity,'hostname':'CLIENT'}).json()
        assert c.get('/api/agent/media').status_code==401
        assert c.get('/api/agent/media',headers=auth(keys['client_token'])).status_code==401
        assert c.get('/api/agent/media',headers=auth(keys['agent_token'])).status_code==403
        c.post('/api/admin/agents/'+identity+'/approve',headers=auth(ADMIN))
        # A PC without local files can now request setup when the server has media.
        request={'action':'deploy','request_id':str(uuid4())}
        job=c.post('/api/client/jobs',json=request,headers=auth(keys['client_token']))
        assert job.status_code==200
        r=c.get('/api/agent/media',headers=auth(keys['agent_token']))
        assert r.status_code==200
        with ZipFile(BytesIO(r.content)) as archive:
            assert set(REQUIRED)<=set(archive.namelist())
            assert 'Office/extra.cab' in archive.namelist()
            assert '.env' not in archive.namelist()
        assert not c.get('/api/config').json()['media']['missing']


def test_missing_source_and_symlinks_are_rejected(tmp_path,source):
    media=DeploymentMedia(source)
    (source/'Config/HancomKey.txt').unlink()
    assert media.manifest()['missing']==['Config/HancomKey.txt']
    with pytest.raises(FileNotFoundError):media.build()
    (source/'Config/HancomKey.txt').write_bytes(b'placeholder')
    outside=tmp_path/'outside';outside.write_bytes(b'private')
    (source/'Office/link').symlink_to(outside)
    with pytest.raises(ValueError):media.build()
