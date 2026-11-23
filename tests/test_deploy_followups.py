from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient
from Server.server import create_app
from Server.models.agent_package import package_version
from Server.models.monitoring import Report

ADMIN = 'admin-' + 'a' * 40
HEADERS = {'Authorization': 'Bearer ' + ADMIN}
ROOT = Path(__file__).resolve().parents[1]


def test_readiness_versions_and_keys(tmp_path):
    with TestClient(create_app(tmp_path/'state.db', 'w'*40, 'r'*40, schools={}, admin_token=ADMIN, media_root=tmp_path/'media')) as c:
        assert c.get('/api/admin/deploy-readiness').status_code == 401
        assert c.get('/api/admin/deploy-readiness', headers=HEADERS).json()['ready'] is True
        code = c.post('/api/admin/enrollments', headers=HEADERS).json()['code']
        keys = c.post('/api/agent/register', json={'code': code, 'device_id': str(uuid4()), 'hostname': 'PC'}).json()
        agent = {'Authorization': 'Bearer '+keys['agent_token']}
        client = {'Authorization': 'Bearer '+keys['client_token']}
        assert not c.get('/api/admin/deploy-readiness', headers=HEADERS).json()['ready']
        assert c.post('/api/agent/claim', headers=agent, json={}).status_code == 200
        assert c.get('/api/admin/agents', headers=HEADERS).json()['agents'][0]['update_required']
        v = package_version(ROOT)
        assert c.post('/api/agent/claim', headers=agent, json={'package_version': v, 'active_job': False}).status_code == 200
        assert c.get('/api/admin/deploy-readiness', headers=HEADERS).json()['ready']
        assert not c.get('/api/admin/agents', headers=HEADERS).json()['agents'][0]['update_required']
        c.post('/api/agent/claim', headers=agent, json={'package_version': v, 'active_job': True})
        assert c.get('/api/admin/deploy-readiness', headers=HEADERS).json()['active_job_agents'] == 1
        response = c.post('/api/client/jobs', headers=client, json={'action': 'deploy', 'request_id': str(uuid4())})
        assert response.status_code == 200
        assert response.json()['state'] == 'queued'
        assert any('한컴 키' in reason for reason in response.json()['key_reasons'])
        assert c.post('/api/agent/claim', headers=agent, json={'setup_ready': False}).json()['job'] is None
        assert c.post('/api/agent/claim', headers=agent, json={'setup_ready': True}).json()['job']['state'] == 'running'
        with ZipFile(BytesIO(c.get('/download/agent.zip').content)) as archive:
            assert archive.read('duct-tape-agent/Config/PackageVersion.txt').decode() == v
            guide = archive.read('duct-tape-agent/시작 안내.txt').decode()
            assert '이전에 받은 ZIP은 폐기' in guide
            assert f'패키지 버전: {v[:12]}' in guide and v not in guide
            assert archive.read('duct-tape-agent/Config/PackageVersion.txt').decode() == v
        assert 'deploy-readiness' in c.get('/admin').text
        assert 'keyReasons' in c.get('/portal.js').text


def test_old_monitoring_schema_remains_valid():
    from datetime import datetime, timezone
    report = dict(grade=1, device_id=str(uuid4()), report_id=str(uuid4()), hostname='PC', office='정상', hancom='정상', stage='01', status='completed', observed_at=datetime.now(timezone.utc))
    assert Report.model_validate(report).hostname == 'PC'


def test_readiness_store_and_package(tmp_path):
    from Server.models.agent_jobs import JobStore, AgentHeartbeat
    store = JobStore(tmp_path/'state.db')
    store.initialize()
    device = str(uuid4())
    store.join(device, 'PC')
    store.approve(device)
    assert not store.readiness()['ready']
    assert AgentHeartbeat.model_validate({}).package_version is None
    v = package_version(ROOT)
    store.claim(device, package_version=v, active_job=False)
    assert store.readiness()['ready']
    job = store.enqueue(device, 'report-test', str(uuid4()))
    assert store.readiness()['queued'] == 1
    store.claim(device, package_version=v, active_job=False)
    assert store.readiness()['running'] == 1
    store.update(device, job['id'], 'interrupted', None)
    assert store.readiness()['interrupted'] == 1
    store.resolve(job['id'])
    store.claim(device, package_version=v, active_job=True)
    assert store.readiness()['active_job_agents'] == 1


def test_local_deploy_check_gate(monkeypatch, capsys):
    from scripts import deploy_check
    import io
    monkeypatch.setattr(deploy_check, 'urlopen', lambda *a, **k: io.BytesIO(b'{"ready": false, "reasons": ["queued"]}'))
    assert deploy_check.main() == 1
    monkeypatch.setattr(deploy_check, 'urlopen', lambda *a, **k: io.BytesIO(b'{"ready": true}'))
    assert deploy_check.main() == 0


def test_license_status_rules(tmp_path):
    from Server.models.agent_jobs import JobStore
    from Server.models.license_history import LicenseHistory
    store = JobStore(tmp_path/'state.db')
    store.initialize()
    licenses = LicenseHistory(store, tmp_path/'media')
    revision = licenses.save('hancom', 'ABCDE-12345', 'test', '')
    licenses.change('hancom', revision, 'apply')
    assert licenses.snapshot()['hancom']
    licenses.change('hancom', revision, 'fail')
    assert licenses.snapshot()['hancom'] is None


def test_claim_checks_active_key_atomically(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import closing
    import sqlite3
    from threading import Event
    from Server.models.agent_jobs import JobStore
    from Server.models.license_history import LicenseHistory
    from Server.models.application_catalog import load

    store = JobStore(tmp_path/'state.db'); store.initialize()
    device = str(uuid4()); store.join(device, 'PC'); store.approve(device)
    licenses = LicenseHistory(store, tmp_path/'media'); licenses.ensure()
    apps = [app for app in load() if app.id == 'hancom']
    check = lambda db: licenses.key_reasons(apps, db)
    revision = licenses.save('hancom', 'ABCDE-12345', 'test', '')
    licenses.change('hancom', revision, 'apply')
    job = store.enqueue(device, 'deploy', str(uuid4()), True)

    # Hold a concurrent key change open so claim must see its committed result.
    started = Event()
    with closing(sqlite3.connect(store.database)) as db, ThreadPoolExecutor(max_workers=1) as pool:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE license_revisions SET status='failed' WHERE id=?", (revision,))
        def claim():
            started.set()
            return store.claim(device, setup_ready=False, key_check=check)
        future = pool.submit(claim)
        assert started.wait(5)
        assert not future.done()
        db.commit()
        assert future.result(timeout=5) is None
    assert '문제 표시' in licenses.key_reasons(apps)[0]
    assert store.claim(device, setup_ready=True, key_check=check)['id'] == job['id']


def test_media_file_key_fallback_and_failed_history(tmp_path):
    from Server.models.agent_jobs import JobStore
    from Server.models.license_history import LicenseHistory
    from Server.models.application_catalog import load
    store = JobStore(tmp_path/'state.db'); store.initialize()
    root = tmp_path/'media'
    licenses = LicenseHistory(store, root)
    apps = [app for app in load() if app.id == 'office']
    licenses.ensure()  # The file can appear after the vault is initialized.
    assert licenses.key_reasons(apps)
    path = root/'Config/OfficeKey.txt'; path.parent.mkdir(parents=True)
    path.write_text('ABCDE-FGHIJ-KLMNO-PQRST-UVWXY')
    assert licenses.key_reasons(apps) == []
    path.write_text('invalid')
    assert licenses.key_reasons(apps)
    path.write_text('ABCDE-FGHIJ-KLMNO-PQRST-UVWXY')
    rev = licenses.save('office', '11111-22222-33333-44444-55555', 'test', '')
    assert licenses.key_reasons(apps)  # Existing but unapplied history takes precedence.
    licenses.change('office', rev, 'apply')
    licenses.change('office', rev, 'fail')
    assert '문제 표시' in licenses.key_reasons(apps)[0]
