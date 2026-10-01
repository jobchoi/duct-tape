"""Run: python tests/mock_client_report.py

Owns a temporary loopback server/database with a no-network GAS relay.
Never loads real school settings or accepts a production server URL.
"""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
TOKEN_NAMES = ('MOCK_LEGACY_TOKEN', 'MOCK_READ_TOKEN', 'MOCK_E_TOKEN', 'MOCK_M_TOKEN')


def serve(port, database):
    # Clear production settings BEFORE importing server.py (which creates a default app).
    for name in list(os.environ):
        if name.startswith('DUCT_'):
            del os.environ[name]
    sys.path.insert(0, str(ROOT))
    import uvicorn
    from Server.server import create_app

    class LocalRelay:
        def send(self, payload):
            pass  # No HTTP, credentials, Google account or Sheets writes.

    schools = {
        'MOCK_E': {'school_type': 'elementary', 'report_token': os.environ['MOCK_E_TOKEN']},
        'MOCK_M': {'school_type': 'middle', 'report_token': os.environ['MOCK_M_TOKEN']},
    }
    app = create_app(database, os.environ['MOCK_LEGACY_TOKEN'], os.environ['MOCK_READ_TOKEN'], schools, LocalRelay())
    uvicorn.run(app, host='127.0.0.1', port=port, access_log=False, log_level='critical')


def report(**changes):
    payload = {
        'device_id': str(uuid4()), 'report_id': str(uuid4()), 'school_code': 'MOCK_E',
        'hostname': 'MOCK-PC', 'serial': 'TEST-SERIAL', 'model': 'MOCK-MODEL',
        'mac': '02:00:00:00:00:01', 'grade': 6, 'office': '설치 필요', 'hancom': '확인 전',
        'stage': '04', 'status': 'running', 'error_code': '', 'installer_exit_code': None,
        'reboot_required': False, 'observed_at': datetime.now(timezone.utc).isoformat(),
    }
    return payload | changes


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def scenarios(client, tokens, database):
    passed = []

    def check(name, payload, token, expected):
        response = client.post('/api/report', json=payload, headers=bearer(token) if token else {})
        require(response.status_code == expected, f'{name}: expected {expected}, got {response.status_code}')
        passed.append(name)
        return response

    original = report()
    require(check('valid school report', original, tokens['MOCK_E_TOKEN'], 200).json()['updated'], 'Initial report not stored')
    require(not check('duplicate report', original, tokens['MOCK_E_TOKEN'], 200).json()['updated'], 'Duplicate changed state')
    older = original | {'report_id': str(uuid4()), 'observed_at': (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), 'status': 'failed'}
    require(not check('older report', older, tokens['MOCK_E_TOKEN'], 200).json()['updated'], 'Old report regressed state')
    completed = original | {'report_id': str(uuid4()), 'observed_at': (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat(),
                            'stage': '06', 'status': 'completed', 'office': '정상', 'hancom': '정상'}
    require(check('completed report', completed, tokens['MOCK_E_TOKEN'], 200).json()['updated'], 'Completion not stored')
    middle = report(school_code='MOCK_M', grade=3)
    check('middle school valid grade', middle, tokens['MOCK_M_TOKEN'], 200)

    def counts():
        with sqlite3.connect(database) as db:
            return tuple(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('devices', 'outbox'))

    baseline = counts()
    check('missing token', report(), None, 401)
    check('invalid token', report(), 'INVALID-TEST-TOKEN', 401)
    check('read token cannot report', report(), tokens['MOCK_READ_TOKEN'], 401)
    check('school token mismatch', report(school_code='MOCK_M'), tokens['MOCK_E_TOKEN'], 403)
    check('legacy token cannot impersonate school', report(), tokens['MOCK_LEGACY_TOKEN'], 403)
    for field in ('message', 'ip', 'step'):
        check(f'disallowed field {field}', report(**{field: 'test-only'}), tokens['MOCK_E_TOKEN'], 422)
    for grade in (None, '1', True, 1.5, 0, 7):
        check(f'invalid grade {type(grade).__name__}:{grade}', report(grade=grade), tokens['MOCK_E_TOKEN'], 422)
    check('middle school grade limit', report(school_code='MOCK_M', grade=4), tokens['MOCK_M_TOKEN'], 422)
    for field in ('device_id', 'report_id', 'hostname', 'grade', 'office', 'hancom', 'stage', 'status', 'observed_at'):
        payload = report()
        del payload[field]
        check(f'missing {field}', payload, tokens['MOCK_E_TOKEN'], 422)
    payload = report()
    del payload['school_code']
    check('missing school for school token', payload, tokens['MOCK_E_TOKEN'], 403)
    for field, value in [('device_id','invalid'), ('report_id','invalid'), ('stage','99'),
                         ('status','done'), ('observed_at','2026-01-01T00:00:00')]:
        check(f'invalid {field}', report(**{field:value}), tokens['MOCK_E_TOKEN'], 422)
    require(counts() == baseline, 'Rejected reports changed database or queue')
    passed.append('rejected reports leave DB/outbox unchanged')

    response = client.get('/api/devices', headers=bearer(tokens['MOCK_READ_TOKEN']))
    require(response.status_code == 200, 'Read API failed')
    rows = response.json()['devices']
    stored = next(row for row in rows if row['device_id'] == original['device_id'])
    require(len(rows) == 2 and stored['status'] == 'completed' and stored['report_id'] == completed['report_id'], 'Dashboard data mismatch')
    with sqlite3.connect(database) as db:
        row = db.execute('SELECT report_id FROM devices WHERE school_code=? AND device_id=?', ('MOCK_E', original['device_id'])).fetchone()
        require(row and row[0] == completed['report_id'], 'SQLite latest row mismatch')
    passed.append('SQLite and dashboard read API reflection')
    require(client.get('/api/devices').status_code == 401, 'Unauthenticated read allowed')
    require(client.get('/api/devices', headers=bearer(tokens['MOCK_E_TOKEN'])).status_code == 401, 'Writer can read assets')
    require(client.get('/').status_code == 200, 'Dashboard shell unavailable')
    passed.append('read permission separation and dashboard shell')
    # Actual HTTP returns before BackgroundTasks finish. Wait only for our inert relay.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with sqlite3.connect(database) as db:
            remaining = db.execute("SELECT COUNT(*) FROM outbox WHERE state!='sent'").fetchone()[0]
        if remaining == 0:
            break
        time.sleep(.1)
    require(remaining == 0, 'Mock relay did not drain queue')
    passed.append('no-network GAS relay completed')
    return passed


def run():
    tokens = {name: secrets.token_urlsafe(32) for name in TOKEN_NAMES}
    env = {name: value for name, value in os.environ.items() if not name.startswith('DUCT_')}
    env.update(tokens)
    with tempfile.TemporaryDirectory(prefix='duct-mock-') as directory:
        database = Path(directory) / 'monitoring.sqlite3'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve', '--port', str(port), '--database', str(database)],
                                  cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=15, trust_env=False, follow_redirects=False) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    require(server.poll() is None, 'Temporary server failed to start')
                    try:
                        if client.get('/').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.1)
                else:
                    raise AssertionError('Temporary server startup timed out')
                passed = scenarios(client, tokens, database)
                for name in passed:
                    print(f'PASS: {name}')
                print(f'{len(passed)} checks passed; temporary server/DB only; no real GAS calls.')
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--port', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--database', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.serve:
            require(args.port and args.database and all(os.environ.get(k) for k in TOKEN_NAMES), 'Missing internal server settings')
            serve(args.port, args.database)
        else:
            require(args.port is None and args.database is None, 'Use default isolated mode')
            run()
        return 0
    except Exception as error:
        # Never print raw transport errors, payloads or environment credentials.
        detail = str(error) if isinstance(error, AssertionError) else type(error).__name__
        print(f'FAIL: {detail}; isolated mock report validation failed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
