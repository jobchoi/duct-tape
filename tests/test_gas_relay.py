from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import sqlite3
import threading
import time
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from Server.gas_relay import GasRelay, RelayError, load_schools
from Server.outbox import Outbox, enqueue, initialize
from Server.server import create_app
from test_server import READ, WRITE, R, W, sample

TOKEN = 'school-one-' + 's' * 40
TOKEN2 = 'school-two-' + 't' * 40
SCHOOLS = {
    'E01': {'school_type': 'elementary', 'report_token': TOKEN,
            'gas_url': 'https://script.google.com/macros/s/test/exec', 'key_id': 'k1', 'secret_env': 'TEST_RELAY_SECRET'},
    'M01': {'school_type': 'middle', 'report_token': TOKEN2},
}
SW = {'Authorization': 'Bearer ' + TOKEN}
MW = {'Authorization': 'Bearer ' + TOKEN2}


def event(**changes):
    return sample(school_code='E01', grade=6, school_type='elementary', schema_version=1,
                  observed_at=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                  received_at=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                  installer_exit_code=None, reboot_required=False, error_code='', **changes)


class Recorder:
    def __init__(self, failures=0, code='network_unavailable', retryable=True):
        self.calls, self.failures, self.code, self.retryable = [], failures, code, retryable

    def send(self, payload):
        self.calls.append(payload)
        if len(self.calls) <= self.failures:
            raise RelayError(self.code, self.retryable)


def test_school_auth_grades_legacy_and_scoped_devices(tmp_path):
    relay = Recorder()
    with TestClient(create_app(tmp_path/'db', WRITE, READ, SCHOOLS, relay)) as c:
        p = sample(school_code='E01', grade=6)
        assert c.post('/api/report', json=p, headers=SW).status_code == 200
        assert c.post('/api/report', json=p, headers=W).status_code == 403
        assert c.post('/api/report', json=p, headers=MW).status_code == 403
        for grade in (0, 7, '2', True, 1.5):
            assert c.post('/api/report', json=p | {'grade': grade}, headers=SW).status_code == 422
        assert c.post('/api/report', json=p | {'school_code': 'M01', 'grade': 6}, headers=MW).status_code == 422
        assert c.post('/api/report', json=p | {'school_code': 'M01', 'grade': None}, headers=MW).status_code == 200
        legacy = {k: v for k, v in p.items() if k not in ('school_code', 'grade')}
        assert c.post('/api/report', json=legacy, headers=W).status_code == 200
        assert c.post('/api/report', json=legacy | {'grade': 1}, headers=W).status_code == 422
        assert len(c.get('/api/devices', headers=R).json()['devices']) == 3
        assert len(relay.calls) == 2
        assert c.get('/api/outbox').status_code == 401
        assert c.get('/api/outbox', headers=R).json()['groups'][0]['count'] == 2


def test_failure_isolation_and_duplicate_identity(tmp_path):
    relay = Recorder(failures=100)
    app = create_app(tmp_path/'db', WRITE, READ, SCHOOLS, relay)
    app.state.outbox.sleep = lambda _: None
    with TestClient(app) as c:
        p = sample(school_code='E01', grade=None)
        assert c.post('/api/report', json=p, headers=SW).json()['updated']
        assert len(relay.calls) == 3
        assert not c.post('/api/report', json=p | {'status': 'failed', 'observed_at': (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat()}, headers=SW).json()['updated']
        assert len(relay.calls) == 3
        assert c.get('/api/devices', headers=R).json()['devices'][0]['status'] == 'running'
        assert c.get('/api/outbox', headers=R).json()['groups'] == [{'state': 'failed', 'last_error': 'network_unavailable', 'count': 1}]


def test_phase3_migration_backup_and_restart(tmp_path):
    path = tmp_path/'old.sqlite3'
    p = sample()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE devices(device_id TEXT PRIMARY KEY, report_id TEXT, observed_at TEXT, received_at TEXT, payload TEXT)')
        db.execute('INSERT INTO devices VALUES(?,?,?,?,?)', (p['device_id'], p['report_id'], p['observed_at'], p['observed_at'], json.dumps(p)))
    for _ in range(2):
        with TestClient(create_app(path, WRITE, READ, SCHOOLS, Recorder())) as c:
            assert c.get('/api/devices', headers=R).json()['devices'][0]['device_id'] == p['device_id']
            assert c.get('/api/outbox', headers=R).json()['groups'] == []
    with sqlite3.connect(str(path)+'.phase3-backup.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM devices').fetchone()[0] == 1
        assert 'school_code' not in [r[1] for r in db.execute('PRAGMA table_info(devices)')]


def test_outbox_transaction_rollback(tmp_path):
    path = tmp_path/'db'
    with TestClient(create_app(path, WRITE, READ, SCHOOLS, Recorder())) as c:
        with sqlite3.connect(path) as db:
            db.execute('DROP TABLE devices')
        assert c.post('/api/report', json=sample(school_code='E01'), headers=SW).status_code == 503
        with sqlite3.connect(path) as db:
            assert db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0


def seeded(tmp_path, relay=None, count=1):
    path = tmp_path/'queue.sqlite3'
    initialize(path)
    with sqlite3.connect(path) as db:
        for _ in range(count):
            enqueue(db, event())
    return Outbox(path, relay or Recorder(), sleep=lambda _: None)


def test_retry_recovery_and_explicit_replay(tmp_path):
    relay = Recorder(failures=2)
    queue = seeded(tmp_path, relay)
    claimed = queue.claim()
    with sqlite3.connect(queue.database) as db:
        db.execute("UPDATE outbox SET lease_until=0, attempts=1")
    # New instance simulates restart after worker death.
    restarted = Outbox(queue.database, relay, sleep=lambda _: None)
    restarted.drain()
    assert len(relay.calls) == 2
    assert restarted.summary()['groups'][0]['state'] == 'failed'
    restarted.replay_failed()
    restarted.drain()
    assert restarted.summary()['groups'][0]['state'] == 'sent'
    assert len({p['report_id'] for p in relay.calls}) == 1
    queue.process(claimed)  # Old owner cannot send after lease recovery.
    assert len(relay.calls) == 3


def test_startup_recovers_pending(tmp_path):
    queue = seeded(tmp_path)
    relay = Recorder()
    with TestClient(create_app(queue.database, WRITE, READ, SCHOOLS, relay)):
        pass  # Lifespan waits for its bounded recovery worker on shutdown.
    assert len(relay.calls) == 1


def test_permanent_error_no_retry_and_queue_worker_exception(tmp_path):
    queue = seeded(tmp_path, Recorder(100, 'auth_failed', False))
    queue.drain()
    assert len(queue.relay.calls) == 1
    queue.claim = lambda: (_ for _ in ()).throw(RuntimeError('secret'))
    queue.drain()
    assert queue.summary()['worker_error'] == 'queue_unavailable'


def test_50_school_events_concurrent(tmp_path):
    relay = Recorder()
    with TestClient(create_app(tmp_path/'db', WRITE, READ, SCHOOLS, relay)) as c:
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda _: c.post('/api/report', json=sample(school_code='E01', grade=1), headers=SW), range(50)))
        assert all(r.status_code == 200 for r in results)
        c.app.state.outbox.drain()
        assert len(relay.calls) == len({p['report_id'] for p in relay.calls}) == 50
        assert len(c.get('/api/devices', headers=R).json()['devices']) == 50


def test_two_cross_instance_leases_no_duplicate_send(tmp_path):
    guard = threading.Lock()
    active = maximum = 0
    class Slow(Recorder):
        def send(self, payload):
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
            time.sleep(.005)
            super().send(payload)
            with guard:
                active -= 1
    relay = Slow()
    queue = seeded(tmp_path, relay, count=50)
    workers = [Outbox(queue.database, relay) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda q: q.drain(), workers))
    assert maximum <= 2
    assert len(relay.calls) == len({p['report_id'] for p in relay.calls}) == 50


def test_transport_signature_redirect_and_unicode(monkeypatch):
    monkeypatch.setenv('TEST_RELAY_SECRET', 'z'*40)
    payload = event()
    requests = []
    def mock(request):
        requests.append(request)
        if request.method == 'POST':
            env = json.loads(request.content)
            expected = hmac.new(b'z'*40, (env['sent_at']+'\n'+env['payload_json']).encode(), hashlib.sha256).hexdigest()
            assert env['signature'] == expected
            assert json.loads(env['payload_json']) == payload
            return httpx.Response(302, headers={'location': 'https://script.googleusercontent.com/macros/echo?test=1'})
        assert request.content == b''
        return httpx.Response(200, json={'ok': True, 'report_id': payload['report_id'], 'result': 'updated'})
    GasRelay(SCHOOLS, httpx.MockTransport(mock)).send(payload)
    assert len(requests) == 2


@pytest.mark.parametrize('response,code,retryable', [
    (httpx.Response(429), 'http_unavailable', True),
    (httpx.Response(503), 'http_unavailable', True),
    (httpx.Response(200, text='<html>login</html>'), 'response_invalid', False),
    (httpx.Response(200, json={'ok': True, 'report_id': 'wrong', 'result': 'updated'}), 'response_invalid', False),
    (httpx.Response(200, json={'ok': False, 'error': 'auth_failed'}), 'auth_failed', False),
    (httpx.Response(200, json={'ok': False, 'error': 'lock_busy'}), 'lock_busy', True),
    (httpx.Response(302, headers={'location': 'https://evil.example/macros/echo'}), 'redirect_invalid', False),
    (httpx.Response(307, headers={'location': 'https://script.googleusercontent.com/macros/echo'}), 'http_rejected', False),
])
def test_transport_rejects_bad_responses(monkeypatch, response, code, retryable):
    monkeypatch.setenv('TEST_RELAY_SECRET', 'z'*40)
    with pytest.raises(RelayError) as caught:
        GasRelay(SCHOOLS, httpx.MockTransport(lambda _: response)).send(event())
    assert (caught.value.code, caught.value.retryable) == (code, retryable)


def test_network_timeout_and_bad_config(monkeypatch):
    monkeypatch.setenv('TEST_RELAY_SECRET', 'z'*40)
    def timeout(request):
        raise httpx.ReadTimeout('secret', request=request)
    with pytest.raises(RelayError, match='network_unavailable'):
        GasRelay(SCHOOLS, httpx.MockTransport(timeout)).send(event())
    monkeypatch.delenv('TEST_RELAY_SECRET')
    with pytest.raises(RelayError, match='relay_config'):
        GasRelay(SCHOOLS).send(event())


def test_sent_retention_never_discards_failed(tmp_path):
    queue = seeded(tmp_path, count=3)
    with sqlite3.connect(queue.database) as db:
        ids = [r[0] for r in db.execute('SELECT report_id FROM outbox')]
        db.execute("UPDATE outbox SET state='sent',sent_at=0 WHERE report_id=?", (ids[0],))
        db.execute("UPDATE outbox SET state='failed' WHERE report_id=?", (ids[1],))
    queue.drain()
    assert sum(r['count'] for r in queue.summary()['groups']) == 2
    assert any(r['state'] == 'failed' for r in queue.summary()['groups'])
