const fs = require('node:fs'), vm = require('node:vm'), crypto = require('node:crypto');
const assert = require('node:assert/strict');
const secret = 'test-only-secret-' + 'x'.repeat(40);
let rows, locked=false, busy=false, writes=0;
const context = vm.createContext({
  PropertiesService:{getScriptProperties:()=>({getProperty:key=>JSON.stringify(key==='RELAY_KEYS'?{k1:secret}:{E01:{key_id:'k1',school_type:'elementary',spreadsheet_id:'test_sheet'}})})},
  Utilities:{Charset:{UTF_8:'utf8'},computeHmacSha256Signature:(message,key)=>Array.from(crypto.createHmac('sha256',key).update(message).digest())},
  LockService:{getScriptLock:()=>({tryLock:()=>{locked=!busy;return locked;},releaseLock:()=>{locked=false;}})},
  Sheets:{Spreadsheets:{Values:{get:()=>({values:rows}),update:(data,id,range,options)=>{
    assert.equal(locked,true);assert.equal(id,'test_sheet');assert.equal(options.valueInputOption,'RAW');
    assert.equal(data.values[0].length,20);const index=Number(range.match(/A(\d+)/)[1])-1;
    rows[index]=data.values[0];writes++;
  }}}}
});
vm.runInContext(fs.readFileSync('GoogleAppsScript/Code.gs','utf8'),context);
const headers=Array.from(vm.runInContext('HEADERS',context));
const stamp=()=>new Date().toISOString().replace('Z','000+00:00');
const base={school_code:'E01',school_type:'elementary',grade:6,hostname:'=IMPORTXML("bad")',serial:'000123',status:'completed',office:'정상',hancom:'정상',stage:'06',error_code:'',installer_exit_code:0,model:'테스트',mac:'00:11:22:33:44:55',reboot_required:false,observed_at:stamp(),received_at:stamp(),device_id:crypto.randomUUID(),report_id:crypto.randomUUID(),schema_version:1};
function envelope(p){const payload_json=JSON.stringify(p),sent_at=stamp();return {schema_version:1,key_id:'k1',sent_at,payload_json,signature:crypto.createHmac('sha256',secret).update(sent_at+'\n'+payload_json).digest('hex')};}
function receive(p=base,edit=e=>e){context.input={postData:{contents:JSON.stringify(edit(envelope(p)))}};return vm.runInContext('receive_(input)',context);}
rows=[headers];
assert.equal(receive().result,'updated');assert.equal(rows[1][3],base.hostname);assert.equal(rows[1][4],'000123');assert.equal(locked,false);
assert.equal(receive().result,'duplicate');assert.equal(writes,1);
assert.equal(receive({...base,report_id:crypto.randomUUID(),observed_at:'2020-01-01T00:00:00.000000+00:00'}).result,'stale');assert.equal(writes,1);
for(const grade of [null,undefined,'1',true,0,7]) assert.throws(()=>receive({...base,grade}),/schema_invalid/);
assert.throws(()=>receive({...base,observed_at:'2026-02-30T00:00:00.000000+00:00'}),/schema_invalid/);
assert.throws(()=>receive(base,e=>({...e,signature:'0'.repeat(64)})),/auth_failed/);
assert.throws(()=>receive({...base,school_code:'OTHER'}),/unknown_school/);
busy=true;assert.throws(()=>receive(),/lock_busy/);busy=false;
rows[0]=['wrong'];assert.throws(()=>receive(),/schema_mismatch/);assert.equal(locked,false);
rows=[headers];assert.equal(receive({...base,grade:1}).result,'updated');
console.log('PASS: GAS HMAC, grade, timestamp, school scope, lock release, RAW A:T mapping, duplicate/stale reports');
