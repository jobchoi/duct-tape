"""Actual browser flow with inert MSI payload and a simulated agent; no installations."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4
import pytest
from tests.test_managed_applications import package


@pytest.mark.skipif(os.environ.get('DUCT_TEST_BROWSER')!='1',reason='Browser opt-in')
def test_app_registration_publish_client_selection_and_results(tmp_path):
    import httpx
    from playwright.sync_api import sync_playwright, expect
    from Server.models.agent_jobs import JobStore
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    url=f'http://127.0.0.1:{port}';db=tmp_path/'test.sqlite3'
    env=os.environ|{'DUCT_AUTH_MODE':'development','DUCT_DB_PATH':str(db),'DUCT_MEDIA_ROOT':str(tmp_path/'media')}
    server=subprocess.Popen([sys.executable,'-m','uvicorn','Server.server:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=url,trust_env=False,timeout=10) as client:
            for _ in range(100):
                try:
                    if client.get('/api/config').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            identity=str(uuid4());headers={'X-Duct-Tape-Request':'1','X-Duct-Device-ID':identity}
            assert client.post('/api/agent/join',json={'device_id':identity,'hostname':'V2-TEST-PC'}).status_code==200
            assert client.post('/api/agent/claim',headers=headers,json={'protocol_version':2}).status_code==200
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url+'/admin/apps')
                expect(page.locator('#message')).to_contain_text('연결됨')
                for name,value in dict(id='sample',name='Sample <script>bad()</script>',version='1.0.0',installer='ArgosMDMSetup.msi',product_code='A23A2428-0549-4AF0-8C9B-85F60CBE9AE7').items():
                    page.locator(f'[name="{name}"]').fill(value)
                page.locator('[name="enrollment"]').check()
                page.locator('[name="package"]').set_input_files({'name':'fixture.zip','mimeType':'application/zip','buffer':package()})
                page.get_by_role('button',name='검사 후 초안 등록').click()
                expect(page.locator('#upload-state')).to_have_text('초안 등록 완료')
                expect(page.locator('#app-list')).to_contain_text('초안')
                page.on('dialog',lambda dialog:dialog.accept())
                page.get_by_role('button',name='검토 후 공개',exact=True).click()
                expect(page.get_by_role('button',name='비공개로 전환')).to_be_visible()
                assert page.locator('#app-list script').count()==0
                # Same browser tab storage as the existing client portal.
                page.goto(url+'/client')
                page.evaluate('(id)=>sessionStorage.setItem("duct-client-device",id)',identity)
                page.goto(url+'/client/apps')
                expect(page.locator('#app-list')).to_contain_text('Sample <script>bad()</script>')
                page.locator('#app-list input[type=checkbox]').check()
                page.get_by_role('button',name='선택 앱 설치',exact=True).click()
                expect(page.locator('#message')).to_contain_text('작업 요청 완료')
                jobs=JobStore(db).jobs(identity);job=jobs[0]
                assert job['action']=='install-apps'
                claim=client.post('/api/agent/claim',headers=headers,json={'protocol_version':2}).json()['job']
                assert claim['id']==job['id']
                base='/api/agent/jobs/'+job['id']
                result={'status':'installed','exit_code':0,'verified':True,'reboot_required':True,'enrollment':'required'}
                assert client.post(base+'/applications/sample/result',headers=headers,json=result).status_code==200
                assert client.post(base,headers=headers,json={'state':'succeeded','exit_code':0}).status_code==200
                expect(page.locator('#jobs')).to_contain_text('MDM 사용자 등록 필요',timeout=15000)
                expect(page.locator('#jobs')).to_contain_text('설치 작업 완료')
                page.screenshot(path='/tmp/duct-v2-client.png',full_page=True)
                page.goto(url+'/admin/apps')
                expect(page.locator('#jobs')).to_contain_text('V2-TEST-PC')
                expect(page.locator('#jobs')).to_contain_text('재부팅 필요')
                page.screenshot(path='/tmp/duct-v2-admin.png',full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                assert not errors,errors
                browser.close()
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()
