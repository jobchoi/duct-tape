from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import os,sys,time,socket,subprocess,json,sqlite3
from Server.models.agent_jobs import JobStore
from Server.outbox import initialize


import pytest

@pytest.mark.skipif(os.environ.get("DUCT_TEST_BROWSER") != "1", reason="Set DUCT_TEST_BROWSER=1 for browser acceptance")
def test_admin_browser_acceptance():
    from playwright.sync_api import sync_playwright, expect
    with TemporaryDirectory(prefix='duct-ui-') as temp:
     db=Path(temp)/'state.db';initialize(db);store=JobStore(db);store.initialize()
     with sqlite3.connect(db) as connection:
      for _ in range(50):
       did=str(uuid4());payload={'device_id':did,'hostname':'LEGACY-TEST','office':'정상','hancom':'정상'}
       connection.execute('INSERT INTO devices VALUES (?,?,?,?,?,?)',('',did,str(uuid4()),'2026-10-08T00:00:00Z','2026-10-08T00:00:00Z',json.dumps(payload)))
     with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
     env=os.environ|{'DUCT_AUTH_MODE':'development','DUCT_DB_PATH':str(db),'PLAYWRIGHT_BROWSERS_PATH':'/tmp/duct-browser'}
     server=subprocess.Popen([sys.executable,'-m','uvicorn','Server.server:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
     try:
      import httpx
      for _ in range(100):
       try:
        if httpx.get(f'http://127.0.0.1:{port}/api/config',trust_env=False).status_code==200:break
       except httpx.HTTPError:pass
       time.sleep(.1)
      with sync_playwright() as p:
       browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
       page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
       page.goto(f'http://127.0.0.1:{port}/admin');expect(page.locator('#admin-content')).to_be_visible()
       expect(page.locator('#empty')).to_be_visible();expect(page.locator('#start')).to_be_disabled()
       expect(page.locator('#legacy-reports')).to_be_visible();assert not page.locator('#legacy-reports').evaluate('(e)=>e.open')
       page.screenshot(path='/tmp/duct-admin-empty.png',full_page=True)
       identity=str(uuid4());store.join(identity,'LAB-PC-01');store.approve(identity);store.claim(identity,True)
       page.reload();expect(page.locator('#devices tr')).to_have_count(1)
       page.get_by_role('button',name='선택',exact=True).click();expect(page.locator('#start')).to_be_enabled()
       page.on('dialog',lambda dialog:dialog.accept());page.locator('#start').click()
       expect(page.locator('#devices')).to_contain_text('셋업 대기');expect(page.locator('#start')).to_be_disabled()
       job=store.jobs(identity)[0];store.claim(identity,True)
       store.append_progress(identity,job['id'],[{'sequence':1,'phase':'download','status':'progress','current':1048576,'total':2097152,'unit':'bytes'},{'sequence':2,'phase':'module','status':'started','module':'04_InstallOffice.ps1','current':3,'total':6,'unit':'steps'}])
       expect(page.locator('#progress-panel')).to_be_visible()
       expect(page.locator('#progress-events')).to_contain_text('1.0 MB / 2.0 MB')
       expect(page.locator('#progress-events')).to_contain_text('Office 설치')
       expect(page.locator('#progress-caption')).to_contain_text('3 / 6단계')
       store.append_progress(identity,job['id'],[{'sequence':3,'phase':'module','status':'completed','module':'04_InstallOffice.ps1','current':4,'total':6,'unit':'steps'},{'sequence':4,'phase':'module','status':'completed','module':'06_InstallHancom.ps1','current':6,'total':6,'unit':'steps'}])
       store.update(identity,job['id'],'succeeded',0)
       expect(page.locator('#progress-state')).to_contain_text('셋업 완료')
       page.locator('.support-panel summary').click()
       resolve=page.locator('#resolve').bounding_box();revoke=page.locator('#revoke').bounding_box()
       assert revoke['x']-resolve['x']-resolve['width']>=11
       page.screenshot(path='/tmp/duct-admin-desktop.png',full_page=True)
       page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/tmp/duct-admin-mobile.png',full_page=True)
       assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
       assert not errors,errors
       browser.close()
       print('PASS: actual Chromium empty/legacy state, PC selection, queued action, desktop button gap, mobile overflow and JavaScript errors')
     finally:
      server.terminate()
      try:server.wait(timeout=5)
      except subprocess.TimeoutExpired:server.kill();server.wait()
