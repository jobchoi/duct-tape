"""Optional loopback test; no Windows installation or external report is performed."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_powershell_to_fastapi(tmp_path):
    engine = os.environ.get('DUCT_TEST_PWSH') or shutil.which('pwsh')
    if not engine:
        pytest.skip('Set DUCT_TEST_PWSH to run the PowerShell/HTTP integration test')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    writer = 'loopback-test-writer-' + 'x' * 40
    reader = 'loopback-test-reader-' + 'y' * 40
    env = os.environ | {'DUCT_DB_PATH': str(tmp_path / 'db.sqlite3'), 'DUCT_REPORT_TOKEN': writer, 'DUCT_READ_TOKEN': reader}
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'Server.server:app', '--host', '127.0.0.1', '--port', str(port)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            for _ in range(100):
                if server.poll() is not None:
                    pytest.fail('Loopback server exited')
                try:
                    if client.get(origin).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail('Loopback server not ready')
            config = tmp_path / 'config.json'
            state = tmp_path / 'state.json'
            config.write_text(json.dumps({'Enabled': True, 'ServerUrl': origin, 'AllowHttp': True,
                                           'ReportToken': writer, 'TimeoutSeconds': 2, 'MaxAttempts': 1}))
            state.write_text(json.dumps({'OfficeState': '정상', 'HancomState': '정상', 'SerialNumber': '학교-통합검증',
                                         'Model': 'Test tablet', 'PIDKEY': 'MUST_NOT_LEAVE_DEVICE'}, ensure_ascii=False))
            harness = tmp_path / 'send.ps1'
            harness.write_text('''param($Reporter,$StatePath,$ConfigPath)
function Get-ItemProperty { param($LiteralPath,$Name,$ErrorAction)
    [pscustomobject]@{MachineGuid='11111111-2222-3333-4444-555555555555'}
}
function Get-CimInstance { param($ClassName,$Filter,$ErrorAction)
    [pscustomobject]@{MACAddress='00:11:22:33:44:55'}
}
& $Reporter -StateFile $StatePath -Stage '06' -Status completed -ErrorCode '' -ConfigPath $ConfigPath
''', encoding='utf-8-sig')
            result = subprocess.run([engine, '-NoProfile', '-File', str(harness), '-Reporter', str(ROOT / 'Scripts/ReportStatus.ps1'),
                                     '-StatePath', str(state), '-ConfigPath', str(config)], capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, 'PowerShell HTTP sender failed'
            response = client.get(origin + '/api/devices', headers={'Authorization': f'Bearer {reader}'})
            assert response.status_code == 200
            rows = response.json()['devices']
            assert len(rows) == 1 and rows[0]['serial'] == '학교-통합검증'
            assert rows[0]['stage'] == '06' and rows[0]['status'] == 'completed'
            assert 'PIDKEY' not in response.text and 'MUST_NOT_LEAVE_DEVICE' not in response.text
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
