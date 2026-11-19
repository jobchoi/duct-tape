from contextlib import closing
from pathlib import Path
from zipfile import ZipFile
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.agent_jobs import JobStore
from Server.models.license_history import LicenseHistory
from Server.models.deployment_media import DeploymentMedia
from tests.test_managed_applications import ADMIN, W, R, auth, register

HEAD={**auth(ADMIN),'X-Duct-Tape-Request':'1'}
KEY='ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'

def setup(tmp_path):
    jobs=JobStore(tmp_path/'db');jobs.initialize()
    return jobs,LicenseHistory(jobs,tmp_path/'media')

def test_encrypted_history_three_good_restore_and_restart(tmp_path):
    jobs,vault=setup(tmp_path)
    ids=[];values=[]
    for n in range(5):
        value=f'{n:05d}-FGHIJ-KLMNO-PQRST-UVWXY';values.append(value)
        rev=vault.save('office',value,f'version-{n}','');ids.append(rev)
        vault.change('office',rev,'apply');vault.change('office',rev,'verify')
    vault.change('office',ids[-1],'fail')
    assert vault.snapshot()['office'] is None
    vault.change('office',ids[0],'restore')
    assert vault.snapshot()['office']==values[0].encode()
    listing=LicenseHistory(jobs,tmp_path/'media').listing()
    assert len(listing['revisions'])==5 and sum(r['status']=='verified' for r in listing['revisions'])==4
    assert any(e['action']=='restore' and e['previous']==ids[-1] for e in listing['audit'])
    assert all(value not in repr(listing) and value.encode() not in (tmp_path/'db').read_bytes() for value in values)
    assert (tmp_path/'license-vault/master.key').stat().st_mode & 0o777==0o600
    (tmp_path/'license-vault/master.key').unlink()
    with pytest.raises(RuntimeError):LicenseHistory(jobs,tmp_path/'media').listing()

def test_import_source_unchanged_and_media_override(tmp_path):
    jobs,vault=setup(tmp_path);media=DeploymentMedia(tmp_path/'media');media.licenses=vault
    for app in media.applications:
        for name in app.required_files:
            f=app.resolve(media.root)/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('fixture')
        f=media.root/app.key_file;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(KEY if app.id=='office' else '1234-5678')
    original=(media.root/'Config/OfficeKey.txt').read_bytes()
    assert media.manifest()['ready']
    assert len(vault.listing()['revisions'])==2
    rev=vault.save('office','11111-22222-33333-44444-55555','new','');vault.change('office',rev,'apply')
    archive=media.build()
    try:
        with ZipFile(archive) as z:
            assert z.read('Config/OfficeKey.txt')==b'11111-22222-33333-44444-55555'
    finally:archive.unlink()
    assert (media.root/'Config/OfficeKey.txt').read_bytes()==original
    vault.change('office',rev,'fail');assert not media.manifest()['ready']
    assert media.manifest()['missing']==['Config/OfficeKey.txt']

def test_active_jobs_block_change_not_revision_storage(tmp_path):
    jobs,vault=setup(tmp_path);rev=vault.save('office',KEY,'first','')
    with closing(jobs.connect()) as db,db:
        db.execute("INSERT INTO agent_jobs VALUES ('job','pc','deploy','running',0,0,NULL,'req')")
    for action in ['apply','restore','verify','fail']:
        with pytest.raises(FileExistsError):vault.change('office',rev,action)
    assert vault.save('office',KEY,'second','')


def test_api_roles_masks_validation_and_agent_sync(tmp_path):
    with TestClient(create_app(tmp_path/'db',W,R,schools={},admin_token=ADMIN,media_root=tmp_path/'media')) as c:
        keys=register(c)
        assert c.get('/admin/licenses').status_code==200
        assert c.get('/api/admin/licenses').status_code==401
        assert c.post('/api/admin/licenses/office',headers=auth(ADMIN),json={'key':KEY,'label':'v1'}).status_code==403
        assert c.post('/api/admin/licenses/office',headers=auth(keys['client_token']),json={'key':KEY,'label':'v1'}).status_code==401
        assert c.post('/api/admin/licenses/office',headers=HEAD,json={'key':'secret!','label':'v1'}).status_code==422
        invalid=c.post('/api/admin/licenses/office',headers=HEAD,json={'key':KEY,'label':''})
        assert invalid.status_code==422 and KEY not in invalid.text
        rev=c.post('/api/admin/licenses/office',headers=HEAD,json={'key':KEY,'label':'v1'}).json()['id']
        assert KEY not in c.get('/api/admin/licenses',headers=auth(ADMIN)).text
        route='/api/admin/licenses/office/'+rev
        assert c.post(route,headers=HEAD,json={'action':'restore','confirmed':True}).status_code==409
        assert c.post(route,headers=HEAD,json={'action':'apply','confirmed':False}).status_code==422
        assert c.post(route,headers=HEAD,json={'action':'apply','confirmed':True}).status_code==200
        assert c.get('/api/agent/licenses').status_code==401
        assert c.get('/api/agent/licenses',headers=auth(keys['client_token'])).status_code==401
        result=c.get('/api/agent/licenses',headers=auth(keys['agent_token']))
        assert result.status_code==200 and result.json()['keys']==[{'app':'office','key':KEY}]
        assert KEY not in c.get('/api/config').text
        assert KEY.encode() not in c.get('/download/agent.zip').content
        assert c.post(route,headers=HEAD,json={'action':'verify','confirmed':True}).status_code==200
        assert c.post('/api/admin/licenses/hancom/'+rev,headers=HEAD,json={'action':'restore','confirmed':True}).status_code==404


def test_usage_links_revision_to_real_job_state(tmp_path):
    jobs,vault=setup(tmp_path);rev=vault.save('office',KEY,'v1','');vault.change('office',rev,'apply')
    with closing(jobs.connect()) as db,db:
        db.execute("INSERT INTO agent_jobs VALUES ('used-job','pc','deploy','running',0,0,NULL,'req')")
    vault.record_usage('other-pc');assert not vault.listing()['usage']
    vault.record_usage('pc');vault.record_usage('pc')
    usage=vault.listing()['usage'];assert len(usage)==1 and usage[0]['revision']==rev
    with closing(jobs.connect()) as db,db:
        db.execute("UPDATE agent_jobs SET state='failed',exit_code=1 WHERE id='used-job'")
    assert vault.listing()['usage'][0]['exit_code']==1
