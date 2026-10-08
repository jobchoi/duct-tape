"""Basic setup UI: real connected PCs, approval, and one setup action."""
from pathlib import Path
import json
import quickjs

SOURCE=Path(__file__).resolve().parents[1]/'Server/views/portal.js'


def browser(role='admin', session=True, key='', mode='secure'):
    ctx=quickjs.Context()
    ctx.eval('''
    class Element {
      constructor() {this.value='';this.textContent='';this.disabled=false;this.hidden=false;this.children=[];this.listeners={};}
      append(item) {this.children.push(item);}
      replaceChildren() {this.children=[];}
      addEventListener(name,fn) {this.listeners[name]=fn;}
      set innerHTML(_) {throw Error('Unsafe HTML');}
    }
    const elements={};
    for (const id of ['access','access-token','disconnect','devices','summary','empty','unmanaged','selected','request','start','result','notice','resolve','revoke','client-state','onboarding','auth-status','login-button','admin-content','media-status','start-reason','legacy-reports','legacy-count','metric-online','metric-pending','metric-media']) elements[id]=new Element();
    const document={body:{dataset:{role:ROLE}},getElementById:id=>elements[id],createElement:()=>new Element()};
    const location={hash:KEY ? (MODE==='development'?'#device=':'#key=')+KEY:'',pathname:ROLE==='admin'?'/admin':'/client'};
    const history={replaceState(){location.hash='';}};
    const sessionStorage={values:{},getItem(name){return this.values[name] || null;},setItem(name,value){this.values[name]=value;},removeItem(name){delete this.values[name];}};
    class URLSearchParams {constructor(value){this.value=value;} get(name){return this.value.startsWith(name+'=')?this.value.slice(name.length+1):null;}}
    const AbortSignal={timeout:()=>({})};
    const crypto={randomUUID:()=> '11111111-2222-3333-4444-555555555555'};
    let calls=[],nextPoll,sessionValid=SESSION,allowed=true,mode='ok', serverMedia=false;
    let agentData=[{device_id:'device-1',hostname:'<img onerror=evil()>',approved:1,setup_ready:1,last_seen:Date.now()/1000}];
    let reportData=[{device_id:'dummy-1',hostname:'DUMMY-PC',office:'정상',hancom:'정상'}];
    let jobData=[];
    function setTimeout(fn){nextPoll=fn;return 1;} function clearTimeout(){} function confirm(){return allowed;}
    async function fetch(path,options){
      calls.push({path,...options});
      if(path==='/api/config') return {ok:true,json:async()=>({auth_mode:MODE,media:{ready:serverMedia,missing:serverMedia?[]:['Hancom/Install/Hwp130.msi','Hancom/Install/VC_redist.x86.exe']}})};
      if(path==='/api/admin/session'){
        if(options.method==='POST') sessionValid=mode==='ok';
        if(options.method==='DELETE') sessionValid=false;
        return {ok:sessionValid || options.method==='DELETE',status:401,json:async()=>({authenticated:sessionValid})};
      }
      if(path.endsWith('/approve')) agentData[0].approved=1;
      const data=path.endsWith('/agents')?{agents:agentData}:path.endsWith('/devices')?{devices:reportData}:path==='/api/client/jobs'?{...agentData[0],jobs:jobData}:{jobs:jobData};
      return {ok:mode==='ok',status:mode==='unauthorized'?401:409,json:async()=>data};
    }
    '''.replace('ROLE',json.dumps(role)).replace('SESSION',json.dumps(session)).replace('KEY',json.dumps(key)).replace('MODE',json.dumps(mode)))
    ctx.eval(SOURCE.read_text())
    settle(ctx)
    return ctx


def settle(ctx):
    for _ in range(100):
        if not ctx.execute_pending_job(): return
    raise AssertionError('Unbounded async work')


def select(ctx):
    ctx.eval('elements.devices.children[0].children[4].children[0].listeners.click()')
    settle(ctx)


def submit(ctx):
    ctx.eval('elements.request.listeners.submit({preventDefault(){}})')
    settle(ctx)


def test_real_pc_selection_persists_and_dummy_reports_are_excluded():
    ctx=browser()
    assert ctx.eval('elements.devices.children.length') == 1
    assert ctx.eval('elements.devices.children[0].children[0].textContent') == '<img onerror=evil()>'
    assert '1대' in ctx.eval('elements.unmanaged.textContent')
    assert ctx.eval('elements.start.disabled') is True
    select(ctx)
    assert ctx.eval('elements.start.disabled') is False
    ctx.eval('nextPoll()');settle(ctx)
    assert ctx.eval('elements.devices.children[0].children[4].children[0].textContent') == '선택됨'
    submit(ctx)
    calls=json.loads(ctx.eval('JSON.stringify(calls)'))
    body=json.loads(next(c['body'] for c in calls if c['path']=='/api/admin/jobs' and c['method']=='POST'))
    assert body['device_id']=='device-1' and body['action']=='deploy'
    assert not any('enrollments' in c['path'] for c in calls)


def test_pending_pc_is_approved_in_place():
    ctx=browser()
    ctx.eval('agentData[0].approved=0;nextPoll()');settle(ctx)
    assert ctx.eval('elements.devices.children[0].children[4].children[0].textContent') == '연결 승인'
    assert ctx.eval('elements.start.disabled') is True
    select(ctx)
    assert ctx.eval('elements.start.disabled') is False
    assert ctx.eval("calls.some(c=>c.path==='/api/admin/agents/device-1/approve')") is True


def test_offline_busy_and_empty_pcs_cannot_start():
    ctx=browser();select(ctx)
    ctx.eval('agentData[0].last_seen=0;nextPoll()');settle(ctx)
    assert ctx.eval('elements.start.disabled') is True
    ctx.eval("agentData[0].last_seen=Date.now()/1000;jobData=[{device_id:'device-1',state:'running'}];nextPoll()")
    settle(ctx);assert ctx.eval('elements.start.disabled') is True
    ctx.eval('agentData=[];nextPoll()');settle(ctx)
    assert ctx.eval('elements.empty.hidden') is False
    assert ctx.eval('elements.start.disabled') is True


def test_client_shortcut_has_only_deploy_and_prevents_double_click():
    ctx=browser('client',key='scoped-key')
    assert ctx.eval('location.hash') == ''
    assert ctx.eval("sessionStorage.getItem('duct-client-key')") == 'scoped-key'
    assert ctx.eval('elements.start.disabled') is False
    ctx.eval('elements.request.listeners.submit({preventDefault(){}});elements.request.listeners.submit({preventDefault(){}})')
    settle(ctx)
    calls=json.loads(ctx.eval('JSON.stringify(calls)'))
    posts=[c for c in calls if c['method']=='POST']
    assert len(posts)==1
    assert json.loads(posts[0]['body'])['action']=='deploy'
    assert posts[0]['headers']['Authorization']=='Bearer scoped-key'
    assert 'device_id' not in json.loads(posts[0]['body'])


def test_client_pending_missing_key_auth_failure_and_confirmation():
    ctx=browser('client')
    assert ctx.eval('elements.start.disabled') is True
    assert '다운로드' in ctx.eval('elements.notice.textContent')
    ctx=browser('client',key='scoped-key')
    ctx.eval('agentData[0].approved=0;nextPoll()');settle(ctx)
    assert ctx.eval('elements.start.disabled') is True
    assert '승인' in ctx.eval('elements.notice.textContent')
    ctx.eval('agentData[0].approved=1;nextPoll()');settle(ctx)
    ctx.eval('allowed=false');submit(ctx)
    assert ctx.eval("calls.filter(c=>c.method==='POST').length") == 0
    ctx.eval("mode='unauthorized';nextPoll()");settle(ctx)
    assert ctx.eval("sessionStorage.getItem('duct-client-key')") is None
    assert ctx.eval('elements.start.disabled') is True


def test_admin_login_and_logout_restore_cookie_session():
    ctx=browser(session=False)
    ctx.eval("elements['access-token'].value='admin-key';elements.access.listeners.submit({preventDefault(){}})")
    settle(ctx)
    assert ctx.eval("elements['access-token'].value") == ''
    select(ctx)
    assert ctx.eval('elements.start.disabled') is False
    ctx.eval('elements.disconnect.listeners.click()');settle(ctx)
    assert ctx.eval('elements.devices.children.length') == 0
    assert ctx.eval('sessionValid') is False


def test_local_admin_connects_without_login_and_media_gate_is_visible():
    ctx=browser(mode='development',session=False)
    assert ctx.eval('elements.access.hidden') is True
    assert '테스트' in ctx.eval("elements['auth-status'].textContent")
    assert ctx.eval("elements['admin-content','media-status','start-reason','legacy-reports','legacy-count','metric-online','metric-pending','metric-media'].hidden") is False
    assert not ctx.eval("calls.some(c=>c.path==='/api/admin/session' && c.method==='POST')")
    select(ctx)
    ctx.eval('agentData[0].setup_ready=0;nextPoll()');settle(ctx)
    assert ctx.eval('elements.start.disabled') is True
    assert '매체' in ctx.eval('elements.devices.children[0].children[3].textContent')


def test_local_client_uses_identifier_without_bearer_token():
    ctx=browser('client',key='11111111-2222-3333-4444-555555555555',mode='development')
    assert ctx.eval('elements.start.disabled') is False
    submit(ctx)
    calls=json.loads(ctx.eval('JSON.stringify(calls)'))
    post=next(c for c in calls if c['path']=='/api/client/jobs' and c['method']=='POST')
    assert 'Authorization' not in post['headers']
    assert post['headers']['X-Duct-Device-ID']=='11111111-2222-3333-4444-555555555555'
    assert ctx.eval('elements.onboarding.hidden') is True


def test_server_media_enables_setup_without_local_files():
    ctx=browser();select(ctx)
    ctx.eval('agentData[0].setup_ready=0;nextPoll()');settle(ctx)
    assert ctx.eval('elements.start.disabled') is True
    ctx.eval('serverMedia=true;nextPoll()');settle(ctx)
    assert ctx.eval('elements.start.disabled') is False
    assert '자동으로' in ctx.eval("elements['media-status'].textContent")


def test_admin_readiness_shows_exact_missing_files():
    ctx=browser()
    message=ctx.eval("elements['media-status'].textContent")
    assert 'Hancom/Install/Hwp130.msi' in message
    assert 'Hancom/Install/VC_redist.x86.exe' in message
    assert 'OfficeKey.txt' not in message


def test_console_distinguishes_legacy_reports_and_current_selection():
    ctx=browser()
    assert ctx.eval("elements['metric-online'].textContent")=='1'
    assert ctx.eval("elements['metric-pending'].textContent")=='0'
    assert ctx.eval("elements['metric-media'].textContent")=='누락 2개'
    assert '이전 상태 보고' in ctx.eval('elements.unmanaged.textContent')
    assert '제외' not in ctx.eval('elements.unmanaged.textContent')
    assert '선택' in ctx.eval("elements['start-reason'].textContent")
    select(ctx)
    assert ctx.eval("elements['media-status'].textContent")=='선택 PC의 설치 매체가 준비되었습니다.'
    assert ctx.eval('elements.devices.children[0].className')=='is-selected'
