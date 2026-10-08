from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from Server.server import create_app
from Server.models.admin_sessions import AdminSessions, COOKIE

ADMIN = 'admin-' + 'a'*40
READ = 'read-' + 'r'*40
WRITE = 'write-' + 'w'*40
H = {'X-Duct-Tape-Request':'1'}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'db.sqlite3', WRITE, READ, schools={}, admin_token=ADMIN, media_root=tmp_path/'missing-media'), base_url='https://testserver') as c:
        yield c


def test_single_login_reads_devices_and_issues_code(client):
    assert client.post('/api/admin/session', json={'token':ADMIN}).status_code == 403
    assert client.post('/api/admin/session', json={'token':READ}, headers=H).status_code == 401
    response = client.post('/api/admin/session', json={'token':ADMIN}, headers=H)
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
    assert ADMIN not in cookie and ADMIN not in response.text
    assert client.get('/api/admin/session',headers=H).status_code == 200
    assert client.get('/api/devices',headers=H).status_code == 200
    assert client.post('/api/admin/enrollments',headers=H).status_code == 200
    assert client.post('/api/admin/enrollments').status_code == 401
    assert client.get('/api/client/jobs',headers=H).status_code == 401
    assert client.post('/api/agent/claim',headers=H).status_code == 401


def test_logout_invalidates_server_session_and_copied_cookie(client):
    client.post('/api/admin/session',json={'token':ADMIN},headers=H)
    value=client.cookies.get(COOKIE)
    assert client.delete('/api/admin/session',headers=H).status_code == 200
    assert client.get('/api/admin/session',headers=H).status_code == 401
    assert client.get('/api/admin/session',headers=H | {'Cookie':COOKIE+'='+value}).status_code == 401


def test_session_expiry_and_header_required():
    sessions=AdminSessions()
    value=sessions.issue()
    request=Request({'type':'http','headers':[(b'cookie',(COOKIE+'='+value).encode()),(b'x-duct-tape-request',b'1')]})
    assert sessions.authenticated(request)
    sessions.entries[sessions.digest(value)] = time.time()-1
    assert not sessions.authenticated(request)


def test_admin_page_has_one_login_and_actionable_enrollment(client):
    html=client.get('/admin').text
    assert html.count('id="access"') == 1
    assert 'id="login"' not in html
    assert 'id="enroll" type="button" disabled' not in html
    assert '8시간' in html
