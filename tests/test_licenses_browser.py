"""Actual UI: save, apply, normal history and restore without plaintext display."""
import os,sys,time,socket,subprocess
import pytest

@pytest.mark.skipif(os.environ.get('DUCT_TEST_BROWSER')!='1',reason='Enable browser acceptance')
def test_license_ui(tmp_path):
    import httpx
    from playwright.sync_api import sync_playwright,expect
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env=os.environ|{'DUCT_AUTH_MODE':'development','DUCT_DB_PATH':str(tmp_path/'db'),'DUCT_MEDIA_ROOT':str(tmp_path/'media')}
    server=subprocess.Popen([sys.executable,'-m','uvicorn','Server.server:app','--host','127.0.0.1','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(base+'/api/config',trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
            page=browser.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
            page.goto(base+'/admin');page.get_by_role('link',name='제품 키·이력 관리',exact=True).click()
            expect(page.locator('#content')).to_be_visible()
            for n in range(3):
                page.locator('#label').fill('good-'+str(n));page.locator('#product-key').fill('ABCDE-FGHIJ-KLMNO-PQRST-UVWXY')
                page.get_by_role('button',name='검증 전 이력으로 저장',exact=True).click()
                row=page.locator('#revisions tr').filter(has_text='good-'+str(n))
                expect(row).to_be_visible();expect(page.locator('#product-key')).to_have_value('')
                row.get_by_role('button',name='이 값 적용',exact=True).click();expect(row).to_contain_text('현재 적용')
                row.get_by_role('button',name='정상 확인',exact=True).click();expect(row.get_by_role('button',name='정상 확인',exact=True)).to_have_count(0)
            expect(page.locator('#summary')).to_contain_text('정상 이력 3개')
            page.locator('#label').fill('bad-new');page.locator('#product-key').fill('11111-22222-33333-44444-55555');page.get_by_role('button',name='검증 전 이력으로 저장').click()
            bad=page.locator('#revisions tr').filter(has_text='bad-new');bad.get_by_role('button',name='이 값 적용',exact=True).click();expect(bad).to_contain_text('현재 적용')
            bad.get_by_role('button',name='문제 표시',exact=True).click();expect(bad).to_contain_text('문제 있음')
            good=page.locator('#revisions tr').filter(has_text='good-0');good.get_by_role('button',name='이전 정상 값으로 복구',exact=True).click();expect(good).to_contain_text('현재 적용')
            assert 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY' not in page.locator('body').inner_text()
            expect(page.locator('#audit')).to_contain_text('복구');assert not errors
            browser.close()
    finally:
        server.terminate();server.wait(timeout=10)
