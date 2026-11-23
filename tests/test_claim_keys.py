from uuid import uuid4

from fastapi.testclient import TestClient

from Server.models.deployment_media import REQUIRED
from Server.models.license_history import LicenseHistory
from Server.server import create_app

ADMIN = 'admin-' + 'a' * 40
WRITE = 'write-' + 'w' * 40
READ = 'read-' + 'r' * 40


def test_key_warning_and_claim_rechecks(tmp_path):
    root = tmp_path / 'media'
    for name in REQUIRED:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('placeholder')
    app = create_app(tmp_path / 'db', WRITE, READ, schools={}, admin_token=ADMIN, media_root=root)
    with TestClient(app) as c:
        auth = lambda token: {'Authorization': 'Bearer ' + token}
        code = c.post('/api/admin/enrollments', headers=auth(ADMIN)).json()['code']
        keys = c.post('/api/agent/register', json={'code': code, 'device_id': str(uuid4()), 'hostname': 'PC'}).json()
        agent, client = auth(keys['agent_token']), auth(keys['client_token'])
        c.post('/api/agent/claim', headers=agent, json={'setup_ready': False})
        job = c.post('/api/client/jobs', headers=client, json={'action': 'deploy', 'request_id': str(uuid4())}).json()
        assert job['id'] and job['key_reasons']
        assert c.post('/api/agent/claim', headers=agent, json={'setup_ready': False}).json()['job'] is None
        blocked = c.get('/api/client/jobs', headers=client).json()['jobs'][0]
        assert blocked['state'] == 'blocked_key_missing' and blocked['key_reasons']
        assert c.post('/api/agent/claim', headers=agent, json={'setup_ready': True}).json()['job']['id'] == job['id']


def test_valid_files_and_failed_active_key(tmp_path):
    from Server.models.agent_jobs import JobStore
    from Server.models.application_catalog import load
    root = tmp_path / 'media'
    store = JobStore(tmp_path / 'db'); store.initialize()
    device = str(uuid4()); store.join(device, 'PC'); store.approve(device)
    licenses = LicenseHistory(store, root); licenses.ensure()
    apps = [app for app in load() if app.id == 'office']
    path = root / apps[0].key_file; path.parent.mkdir(parents=True)
    path.write_text('ABCDE-FGHIJ-KLMNO-PQRST-UVWXY')
    check = lambda db: licenses.key_reasons(apps, db)
    job = store.enqueue(device, 'deploy', str(uuid4()), True)
    rev = licenses.save('office', '11111-22222-33333-44444-55555', 'test', '')
    licenses.change('office', rev, 'apply'); licenses.change('office', rev, 'fail')
    assert store.claim(device, False, key_check=check) is None
    licenses.change('office', rev, 'verify')
    assert store.claim(device, False, key_check=check)['id'] == job['id']
    device2 = str(uuid4()); store.join(device2, 'PC'); store.approve(device2)
    # A separate vault with no history falls back to the valid file.
    other = JobStore(tmp_path / 'other'); other.initialize(); other.join(device2, 'PC'); other.approve(device2)
    fallback = LicenseHistory(other, root); fallback.ensure()
    job2 = other.enqueue(device2, 'deploy', str(uuid4()), True)
    assert other.claim(device2, False, key_check=lambda db: fallback.key_reasons(apps, db))['id'] == job2['id']
