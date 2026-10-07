"""Browser controller behavior in an isolated JS engine with a minimal DOM."""
from pathlib import Path
import json
import quickjs
import pytest

SOURCE = Path(__file__).resolve().parents[1]/'Server/views/portal.js'


def browser(role='client'):
    ctx = quickjs.Context()
    ctx.eval('''
    class Element {
      constructor() { this.value=''; this.textContent=''; this.disabled=false; this.children=[]; this.listeners={}; }
      addEventListener(name, fn) { this.listeners[name]=fn; }
      append(item) { this.children.push(item); }
      replaceChildren() { this.children=[]; }
      set innerHTML(value) { throw Error('HTML injection'); }
    }
    const elements = {};
    for (const id of ['access','access-token','disconnect','start','jobs','notice','enroll','enrollment','device','action','request','resolve','resolve-id','revoke']) elements[id] = new Element();
    const document = {body: {dataset: {role: ROLE}}, getElementById: id => elements[id], createElement: () => new Element()};
    const location = {hash:'',pathname:'/client'};
    const history = {replaceState() {}};
    class URLSearchParams { get() { return null; } }
    const AbortSignal = {timeout: () => ({})};
    let nextPoll, allowed=true, calls=[], mode='ok';
    const crypto = {randomUUID: () => '11111111-2222-3333-4444-555555555555'};
    function confirm() { return allowed; }
    function setTimeout(fn) { nextPoll=fn; return 1; }
    function clearTimeout() {}
    async function fetch(path, options) {
      calls.push({path, ...options});
      const data = path.endsWith('/agents') ? {agents:[{device_id:'device-1',hostname:'<img onerror=evil()>',last_seen: Date.now()/1000}]} : path.endsWith('/enrollments') ? {code:'one-use-code'} : {device_id:'device-1',jobs:[]};
      return {ok:mode==='ok',status:mode==='unauthorized'?401:409,json:async()=>data};
    }
    '''.replace('ROLE', json.dumps(role)))
    ctx.eval(SOURCE.read_text())
    return ctx


def settle(ctx):
    for _ in range(50):
        if not ctx.execute_pending_job():
            return
    raise AssertionError('Unbounded JS jobs')


def connect(ctx):
    ctx.eval("elements['access-token'].value='scoped-key'; elements.access.listeners.submit({preventDefault(){}})")
    settle(ctx)


def test_client_key_memory_and_fixed_job_request():
    ctx = browser()
    connect(ctx)
    assert ctx.eval("elements['access-token'].value") == ''
    assert ctx.eval("elements.start.disabled") is False
    ctx.eval("elements.action.value='report-test'; elements.request.listeners.submit({preventDefault(){}}); elements.request.listeners.submit({preventDefault(){}})")
    settle(ctx)
    calls = json.loads(ctx.eval('JSON.stringify(calls)'))
    posts = [c for c in calls if c['method'] == 'POST']
    assert len(posts) == 1
    assert posts[0]['path'] == '/api/client/jobs'
    assert json.loads(posts[0]['body']) == {'action':'report-test','request_id':'11111111-2222-3333-4444-555555555555'}
    assert posts[0]['headers']['Authorization'] == 'Bearer scoped-key'
    ctx.eval("elements.disconnect.listeners.click()")
    assert ctx.eval('elements.start.disabled') is True
    assert ctx.eval('elements.jobs.textContent') == ''


def test_deploy_confirmation_and_auth_error():
    ctx = browser()
    connect(ctx)
    ctx.eval("allowed=false; elements.action.value='deploy'; elements.request.listeners.submit({preventDefault(){}})")
    settle(ctx)
    assert ctx.eval("calls.filter(c => c.method==='POST').length") == 0
    ctx.eval("mode='unauthorized'; nextPoll()")
    settle(ctx)
    assert ctx.eval('elements.start.disabled') is True
    assert '접속 키' in ctx.eval('elements.notice.textContent')


def test_admin_scope_and_safe_hostname_rendering():
    ctx = browser('admin')
    connect(ctx)
    assert ctx.eval('elements.device.children[0].textContent').startswith('<img onerror=evil()>')
    ctx.eval("elements.enroll.listeners.click()")
    settle(ctx)
    assert 'one-use-code' in ctx.eval('elements.enrollment.textContent')
    ctx.eval("elements.device.value='device-1'; elements.action.value='report-test'; elements.request.listeners.submit({preventDefault(){}})")
    settle(ctx)
    calls = json.loads(ctx.eval('JSON.stringify(calls)'))
    post = next(c for c in calls if c['path']=='/api/admin/jobs' and c['method']=='POST')
    assert json.loads(post['body'])['device_id'] == 'device-1'
    ctx.eval('elements.disconnect.listeners.click()')
    assert ctx.eval('elements.enrollment.textContent') == ''
