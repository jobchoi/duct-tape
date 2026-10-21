"""Real browser QR generation/download/decoding with a simulated PC report."""
import io
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4
import pytest

@pytest.mark.skipif(os.environ.get('DUCT_TEST_BROWSER')!='1',reason='Browser opt-in')
def test_serial_qr_download_and_feature_switches(tmp_path):
    import httpx
    import zxingcpp
    from PIL import Image
    from playwright.sync_api import sync_playwright, expect
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    url=f'http://127.0.0.1:{port}'
    env=os.environ|{'DUCT_AUTH_MODE':'development','DUCT_DB_PATH':str(tmp_path/'db'),
                    'DUCT_MEDIA_ROOT':str(tmp_path/'media'),'DUCT_REPORT_TOKEN':'w'*40,'DUCT_READ_TOKEN':'r'*40}
    server=subprocess.Popen([sys.executable,'-m','uvicorn','Server.server:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=url,trust_env=False) as client:
            for _ in range(100):
                try:
                    if client.get('/api/config').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            identity=str(uuid4())
            assert client.post('/api/agent/join',json={'device_id':identity,'hostname':'QR-TEST-PC'}).status_code==200
            report=dict(device_id=identity,report_id=str(uuid4()),hostname='QR-TEST-PC',grade=1,
                        serial='00001234',office='확인 전',hancom='확인 전',stage='01',status='completed',
                        observed_at=datetime.now(timezone.utc).isoformat())
            assert client.post('/api/report',headers={'Authorization':'Bearer '+'w'*40},json=report).status_code==200
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
                page=browser.new_page();errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url+'/admin')
                expect(page.get_by_role('link',name='QR 만들기')).to_be_visible()
                page.get_by_role('link',name='QR 만들기').click()
                expect(page.locator('#qr-value')).to_have_value('00001234')
                expect(page.locator('#serial-status')).to_contain_text('마지막 보고')
                page.locator('#person').fill('비공개 사용자')
                page.get_by_role('button',name='QR 생성',exact=True).click()
                expect(page.locator('#preview')).to_be_visible()
                with page.expect_download() as download:
                    page.get_by_role('button',name='PNG 다운로드').click()
                result=zxingcpp.read_barcode(Image.open(download.value.path()))
                assert result is not None and result.text=='00001234'
                # A different payload must invalidate the old preview and preserve UTF-8.
                page.locator('#qr-value').fill('한글|<script>|0009')
                expect(page.locator('#preview')).to_be_hidden()
                page.get_by_role('button',name='QR 생성',exact=True).click()
                expect(page.locator('#preview')).to_be_visible()
                with page.expect_download() as download:
                    page.get_by_role('button',name='PNG 다운로드').click()
                assert zxingcpp.read_barcode(Image.open(download.value.path())).text=='한글|<script>|0009'
                toggle=page.locator('[data-feature="qr"]')
                toggle.uncheck()
                expect(page.locator('#qr-panel')).to_be_hidden()
                page.reload()
                expect(toggle).not_to_be_checked()
                expect(page.locator('#qr-panel')).to_be_hidden()
                toggle.check()
                expect(page.locator('#qr-panel')).to_be_visible()
                expect(page.locator('#preview')).to_be_hidden()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                assert not errors,errors
                browser.close()
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()
