from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pathlib import Path
import os,shutil,subprocess,json,time
import pytest


def test_powershell_measures_real_http_bytes_and_does_not_follow_redirect(tmp_path):
    engine=os.environ.get('DUCT_TEST_PWSH') or shutil.which('pwsh')
    if not engine:pytest.skip('Set DUCT_TEST_PWSH for real HTTP progress')
    payload=bytes(range(256))*16384
    requested=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requested.append(self.path)
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','/unexpected');self.end_headers();return
            self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
            for start in range(0,len(payload),65536):
                self.wfile.write(payload[start:start+65536]);self.wfile.flush();time.sleep(.02)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    scripts=tmp_path/'Scripts';scripts.mkdir()
    source=Path(__file__).resolve().parents[1]/'Scripts/JobProgress.ps1'
    shutil.copyfile(source,scripts/'JobProgress.ps1')
    harness=scripts/'download.ps1'
    harness.write_text("param($Uri,$OutFile)\n. (Join-Path $PSScriptRoot 'JobProgress.ps1')\n$env:DUCT_JOB_ID='11111111-2222-3333-4444-555555555555'\nReceive-AgentMedia -Uri $Uri -Headers @{Authorization='Bearer test-fixture'} -OutFile $OutFile\n")
    try:
        origin=f'http://127.0.0.1:{server.server_port}'
        result=subprocess.run([engine,'-NoProfile','-File',str(harness),'-Uri',origin+'/payload','-OutFile',str(tmp_path/'payload.bin')],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert (tmp_path/'payload.bin').read_bytes()==payload
        events=[json.loads(line) for line in (tmp_path/'logs/11111111-2222-3333-4444-555555555555.progress.jsonl').read_text().splitlines()]
        assert events[-1]['status']=='completed' and events[-1]['current']==len(payload) and events[-1]['total']==len(payload)
        assert any(e['status']=='progress' and e.get('current',0)>0 for e in events)
        result=subprocess.run([engine,'-NoProfile','-File',str(harness),'-Uri',origin+'/redirect','-OutFile',str(tmp_path/'blocked.bin')],capture_output=True,text=True,timeout=10)
        assert result.returncode!=0
        assert '/unexpected' not in requested
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
