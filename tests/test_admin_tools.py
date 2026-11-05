"""Admin feature boundaries, persistence, serial reuse and QR payload safety."""
import pytest
from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.qr import encode
from tests.test_managed_applications import ADMIN,W,R,auth,register,upload,manifest

@pytest.fixture
def api(tmp_path):
    with TestClient(create_app(tmp_path/'db',W,R,schools={},admin_token=ADMIN,media_root=tmp_path/'media')) as client:
        yield client


def test_qr_admin_only_exact_payload_and_limits(api):
    c=api;keys=register(c);url='/api/admin/tools/qr'
    assert c.post(url,json={'value':'serial'}).status_code==401
    assert c.post(url,headers=auth(keys['client_token']),json={'value':'serial'}).status_code==401
    value='  00001234|홍길동|<script>  '
    response=c.post(url,headers=auth(ADMIN),json={'value':value})
    assert response.status_code==200
    assert response.json()['matrix']==encode(value) # preserves leading zeros and whitespace
    matrix=response.json()['matrix']
    assert all(not x for row in matrix[:4] for x in row) # QR quiet zone
    for bad in ('','   ','가'*400,'x'*1025):
        assert c.post(url,headers=auth(ADMIN),json={'value':bad}).status_code==422
    assert c.post(url,headers=auth(ADMIN),json={'value':'ok','name':'private'}).status_code==422


def test_feature_toggle_persists_and_api_enforces(api,tmp_path):
    c=api
    assert c.get('/api/admin/features').status_code==401
    assert c.put('/api/admin/features/qr',json={'enabled':False}).status_code==401
    assert c.put('/api/admin/features/no-such-feature',headers=auth(ADMIN),json={'enabled':False}).status_code==404
    assert c.put('/api/admin/features/qr',headers=auth(ADMIN),json={'enabled':'false'}).status_code==422
    assert c.put('/api/admin/features/qr',headers=auth(ADMIN),json={'enabled':False}).status_code==200
    assert c.post('/api/admin/tools/qr',headers=auth(ADMIN),json={'value':'SN'}).status_code==409
    with TestClient(create_app(tmp_path/'db',W,R,schools={},admin_token=ADMIN,media_root=tmp_path/'media')) as restarted:
        assert restarted.get('/api/admin/features',headers=auth(ADMIN)).json()['features']['qr'] is False
    c.put('/api/admin/features/qr',headers=auth(ADMIN),json={'enabled':True})
    assert c.post('/api/admin/tools/qr',headers=auth(ADMIN),json={'value':'SN'}).status_code==200


def test_mdm_toggle_hides_and_blocks_download_and_secret_reveal(api):
    c=api;keys=register(c);metadata=manifest();metadata['id']='argos-mdm'
    assert upload(c,metadata=metadata).status_code==200
    c.put('/api/admin/applications/argos-mdm/1.1.7',headers=auth(ADMIN),json={'published':True,'reviewed':True})
    client_auth=auth(keys['client_token'])
    assert c.get('/api/client/mdm/1.1.7/package',headers=client_auth).status_code==200
    c.put('/api/admin/features/mdm_download',headers=auth(ADMIN),json={'enabled':False})
    assert c.get('/api/client/applications',headers=client_auth).json()['applications']==[]
    for role,headers in [('admin',auth(ADMIN)),('client',client_auth)]:
        assert c.get(f'/api/{role}/mdm/1.1.7/package',headers=headers).status_code==409
        assert c.get(f'/api/{role}/mdm/registration',headers=headers).status_code==409
    c.put('/api/admin/features/mdm_download',headers=auth(ADMIN),json={'enabled':True})
    assert c.get('/api/client/mdm/1.1.7/package',headers=client_auth).status_code==200
