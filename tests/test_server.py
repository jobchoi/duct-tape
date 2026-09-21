from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from Server.server import create_app

WRITE = 'test-writer-' + 'a' * 40
READ = 'test-reader-' + 'b' * 40
W = {'Authorization': f'Bearer {WRITE}'}
R = {'Authorization': f'Bearer {READ}'}


def sample(**changes):
    data = dict(device_id=str(uuid4()), report_id=str(uuid4()), hostname='교실-PC01', serial='ASSET-01',
                model='School tablet', mac='00:11:22:33:44:55', office='설치 필요', hancom='확인 전',
                stage='04', status='running', observed_at=datetime.now(timezone.utc).isoformat())
    return data | changes


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'state.db', WRITE, READ)) as test:
        yield test


def test_auth_and_no_public_assets(client):
    assert client.get('/').status_code == 200
    assert client.get('/api/devices').status_code == 401
    assert client.get('/api/devices', headers=W).status_code == 401
    assert client.post('/api/report', json=sample(), headers=R).status_code == 401
    assert client.post('/api/report', json=sample()).status_code == 401
    assert client.get('/dashboard.js').headers['cache-control'] == 'no-store'


def test_upsert_retry_and_out_of_order(client):
    report = sample()
    assert client.post('/api/report', json=report, headers=W).json()['updated']
    assert not client.post('/api/report', json=report, headers=W).json()['updated']
    older = report | {'report_id': str(uuid4()), 'observed_at': (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), 'status': 'failed'}
    assert not client.post('/api/report', json=older, headers=W).json()['updated']
    newer = report | {'report_id': str(uuid4()), 'observed_at': (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat(), 'status': 'completed', 'office': '정상'}
    assert client.post('/api/report', json=newer, headers=W).json()['updated']
    rows = client.get('/api/devices', headers=R).json()['devices']
    assert len(rows) == 1 and rows[0]['status'] == 'completed'
    assert rows[0]['hostname'] == '교실-PC01' and rows[0]['received_at']


@pytest.mark.parametrize('changes', [
    {'mac': 'not-a-mac'}, {'office': 'unexpected'}, {'stage': '99'}, {'hostname': ''},
    {'device_id': 'wrong'}, {'observed_at': '2026-01-01T00:00:00'},
    {'observed_at': (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},
    {'PIDKEY': 'DO-NOT-ECHO-SECRET'}, {'error_code': 'raw exception with secret'},
])
def test_validation_does_not_echo_input(client, changes):
    response = client.post('/api/report', json=sample(**changes), headers=W)
    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid report schema or timestamp'}
    assert client.get('/api/devices', headers=R).json()['devices'] == []


def test_50_devices_concurrent(client):
    reports = [sample(hostname=f'PC-{i}') for i in range(50)]
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(lambda report: client.post('/api/report', json=report, headers=W), reports))
    assert all(r.status_code == 200 and r.json()['updated'] for r in results)
    assert len(client.get('/api/devices', headers=R).json()['devices']) == 50


def test_persists_across_restart(tmp_path):
    path = tmp_path / 'state.db'
    with TestClient(create_app(path, WRITE, READ)) as client:
        assert client.post('/api/report', json=sample(), headers=W).status_code == 200
    with TestClient(create_app(path, WRITE, READ)) as client:
        assert len(client.get('/api/devices', headers=R).json()['devices']) == 1


def test_storage_error_sanitized(tmp_path):
    path = tmp_path / 'state.db'
    with TestClient(create_app(path, WRITE, READ)) as client:
        with sqlite3.connect(path) as db:
            db.execute('DROP TABLE devices')
        response = client.post('/api/report', json=sample(), headers=W)
        assert response.status_code == 503
        assert response.json() == {'detail': 'Storage unavailable'}


def test_requires_distinct_tokens(tmp_path):
    with pytest.raises(RuntimeError):
        with TestClient(create_app(tmp_path / 'state.db', WRITE, WRITE)):
            pass
