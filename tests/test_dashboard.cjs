// Minimal DOM contract test; real browser rendering is a separate acceptance check.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
class Element {
  constructor() { this.value = ''; this.textContent = ''; this.children = []; this.listeners = {}; }
  set innerHTML(_) { throw new Error('Untrusted HTML rendering'); }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  addEventListener(event, handler) { this.listeners[event] = handler; }
}
const elements = Object.fromEntries(['search','summary','devices','connection','token','login','logout','school','grade'].map(id => [id,new Element()]));
const payload = {school_code:'E01',grade:3,hostname:'<img src=x onerror=alert(1)>',serial:'학교-1',model:'tablet',mac:'00:11:22:33:44:55',office:'정상',hancom:'정상',stage:'06',status:'completed',reboot_required:true,received_at:new Date().toISOString()};
let nextPoll, mode = 'ok';
const context = vm.createContext({document:{getElementById:id=>elements[id],createElement:()=>new Element()},
  AbortSignal, setTimeout: fn => { nextPoll=fn; return 1; }, clearTimeout:()=>{},
  fetch: async (_, options) => {
    assert.equal(options.headers.Authorization, 'Bearer read-test-token');
    if (mode === 'offline') throw new Error('offline');
    return {ok:mode==='ok',status:mode==='unauthorized'?401:200,json:async()=>({devices:[payload]})};
  }});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../Server/static/dashboard.js'),'utf8'),context);
const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  elements.token.value='read-test-token'; elements.login.listeners.submit({preventDefault(){}}); await flush();
  assert.equal(elements.token.value,'');
  assert.equal(elements.devices.children.length,1);
  assert.equal(elements.devices.children[0].children[0].textContent,payload.hostname);
  assert.match(elements.summary.textContent,/배포 완료 1대/);
  elements.search.value='not-found'; elements.search.listeners.input(); assert.equal(elements.devices.children.length,0);
  elements.search.value='학교'; elements.search.listeners.input(); assert.equal(elements.devices.children.length,1);
  elements.school.value='M01'; elements.school.listeners.input(); assert.equal(elements.devices.children.length,0);
  elements.school.value='E01'; elements.grade.value='2'; elements.grade.listeners.change(); assert.equal(elements.devices.children.length,0);
  elements.grade.value='3'; elements.grade.listeners.change(); assert.equal(elements.devices.children.length,1);
  assert.match(elements.devices.children[0].children[1].textContent,/E01.*3학년/);
  mode='offline'; await nextPoll(); assert.match(elements.connection.textContent,/갱신 실패/); assert.equal(elements.devices.children.length,1);
  mode='unauthorized'; await nextPoll(); assert.equal(elements.devices.children.length,0); assert.match(elements.connection.textContent,/토큰/);
  elements.logout.listeners.click(); assert.equal(elements.devices.children.length,0);
  console.log('PASS: dashboard text-only rows, search, completion count, offline notice, authentication failure, logout');
})().catch(error=>{console.error(error);process.exitCode=1;});
