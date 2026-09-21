/* Script Properties: RELAY_KEYS and SCHOOLS are JSON objects; never log them.
 * RELAY_KEYS: key_id -> 32+ character shared secret.
 * SCHOOLS: school_code -> {school_type, spreadsheet_id, key_id}.
 * Provision a Devices tab with exactly HEADERS in A1:T1 before enabling relay.
 */
const HEADERS = ['school_code','school_type','grade','hostname','serial','status','office','hancom',
  'stage','error_code','installer_exit_code','model','mac','reboot_required','observed_at','received_at',
  'mirrored_at','device_id','report_id','schema_version'];
const STATES = ['확인 전','설치 필요','설치 중','정상','오류'];
function reply_(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
function fail_(code) { throw new Error(code); }
function equal_(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i=0;i<a.length;i++) diff |= a.charCodeAt(i)^b.charCodeAt(i);
  return diff === 0;
}
function timestamp_(s) {
  // Canonical microsecond UTC text allows sub-millisecond ordering (Date loses precision).
  return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$/.test(s) && Number.isFinite(Date.parse(s));
}
function validate_(p) {
  if (!p || typeof p !== 'object' || Array.isArray(p)) fail_('schema_invalid');
  const expected = HEADERS.filter(x => x !== 'mirrored_at');
  if (Object.keys(p).length !== expected.length || expected.some(x => !Object.prototype.hasOwnProperty.call(p,x))) fail_('schema_invalid');
  if (p.schema_version !== 1 || typeof p.school_code !== 'string' || !/^[A-Z0-9_-]{1,32}$/.test(p.school_code) ||
      !['elementary','middle','high'].includes(p.school_type) ||
      (p.grade !== null && (!Number.isInteger(p.grade) || p.grade < 1 || p.grade > (p.school_type === 'elementary' ? 6 : 3)))) fail_('schema_invalid');
  for (const field of ['hostname','serial','model']) {
    if (typeof p[field] !== 'string' || p[field].length > 160 || (field === 'hostname' && !p[field].trim())) fail_('schema_invalid');
  }
  for (const field of ['device_id','report_id']) {
    if (typeof p[field] !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(p[field])) fail_('schema_invalid');
  }
  if (!['running','completed','failed'].includes(p.status) || !STATES.includes(p.office) || !STATES.includes(p.hancom) ||
      !['Preflight','01','02','03','04','05','06'].includes(p.stage) ||
      typeof p.error_code !== 'string' || !/^[A-Z0-9_]{0,64}$/.test(p.error_code) ||
      typeof p.mac !== 'string' || !/^$|^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/.test(p.mac) ||
      typeof p.reboot_required !== 'boolean' ||
      (p.installer_exit_code !== null && (!Number.isInteger(p.installer_exit_code) || p.installer_exit_code<0 || p.installer_exit_code>4294967295)) ||
      !timestamp_(p.observed_at) || !timestamp_(p.received_at) || Date.parse(p.observed_at) > Date.now()+300000) fail_('schema_invalid');
}
function receive_(e) {
  if (!e || !e.postData || typeof e.postData.contents !== 'string' || e.postData.contents.length>32768) fail_('schema_invalid');
  let env;
  try { env=JSON.parse(e.postData.contents); } catch (_) { fail_('schema_invalid'); }
  if (!env || env.schema_version!==1 || typeof env.key_id!=='string' || !/^[A-Za-z0-9_-]{1,64}$/.test(env.key_id) ||
      typeof env.payload_json!=='string' || !timestamp_(env.sent_at) || typeof env.signature!=='string' ||
      !/^[0-9a-f]{64}$/.test(env.signature)) fail_('schema_invalid');
  const properties=PropertiesService.getScriptProperties();
  const keys=JSON.parse(properties.getProperty('RELAY_KEYS') || '{}');
  const secret=Object.prototype.hasOwnProperty.call(keys,env.key_id) ? keys[env.key_id] : null;
  if (typeof secret!=='string' || secret.length<32 || Math.abs(Date.now()-Date.parse(env.sent_at))>300000) fail_('auth_failed');
  const bytes=Utilities.computeHmacSha256Signature(env.sent_at+'\n'+env.payload_json,secret,Utilities.Charset.UTF_8);
  const signature=bytes.map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
  if (!equal_(signature,env.signature)) fail_('auth_failed');
  let p;
  try { p=JSON.parse(env.payload_json); } catch (_) { fail_('schema_invalid'); }
  validate_(p);
  const schools=JSON.parse(properties.getProperty('SCHOOLS') || '{}');
  const school=Object.prototype.hasOwnProperty.call(schools,p.school_code) ? schools[p.school_code] : null;
  if (!school || school.key_id!==env.key_id || school.school_type!==p.school_type ||
      typeof school.spreadsheet_id!=='string' || !/^[A-Za-z0-9_-]+$/.test(school.spreadsheet_id)) fail_('unknown_school');
  const lock=LockService.getScriptLock();
  if (!lock.tryLock(1000)) fail_('lock_busy');
  try {
    const rows=Sheets.Spreadsheets.Values.get(school.spreadsheet_id,'Devices!A:T', {valueRenderOption:'UNFORMATTED_VALUE'}).values || [];
    if (!rows.length || rows[0].length!==HEADERS.length || HEADERS.some((name,i)=>rows[0][i]!==name)) fail_('schema_mismatch');
    let index=-1;
    for (let i=1;i<rows.length;i++) {
      if (rows[i][0]===p.school_code && rows[i][17]===p.device_id) {
        if (index!==-1) fail_('schema_mismatch');
        index=i;
      }
    }
    let result='updated';
    if (index!==-1) {
      const current=rows[index];
      if (current[18]===p.report_id) result='duplicate';
      else {
        if (!timestamp_(current[14])) fail_('schema_mismatch');
        if (current[14]>=p.observed_at) result='stale';
      }
    }
    if (result==='updated') {
      const values=HEADERS.map(name=>name==='mirrored_at' ? new Date().toISOString() : (p[name]===null ? '' : p[name]));
      const row=index===-1 ? rows.length+1 : index+1;
      Sheets.Spreadsheets.Values.update({values:[values]},school.spreadsheet_id,'Devices!A'+row+':T'+row,{valueInputOption:'RAW'});
    }
    return {ok:true,report_id:p.report_id,result:result};
  } finally { lock.releaseLock(); }
}
function doPost(e) {
  try { return reply_(receive_(e)); }
  catch (error) {
    const codes=['auth_failed','schema_invalid','unknown_school','schema_mismatch','lock_busy'];
    return reply_({ok:false,error:codes.includes(error.message) ? error.message : 'sheet_unavailable'});
  }
}
