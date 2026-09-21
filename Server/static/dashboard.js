'use strict';
let token = '', timer = null, generation = 0, devices = [];
const el = id => document.getElementById(id);
const statusNames = {running: '진행 중', completed: '단계 완료', failed: '실패'};
function render() {
  const query = el('search').value.toLowerCase();
  const school = el('school').value.trim().toUpperCase(), grade = el('grade').value;
  const filtered = devices.filter(d => (!school || d.school_code === school) &&
    (!grade || (grade === 'shared' ? d.grade == null : String(d.grade) === grade)) &&
    `${d.hostname} ${d.serial} ${d.model}`.toLowerCase().includes(query));
  el('summary').textContent = `전체 ${devices.length}대 · 선택 ${filtered.length}대 · 배포 완료 ${filtered.filter(d => d.stage === '06' && d.status === 'completed').length}대 · 실패 ${filtered.filter(d => d.status === 'failed').length}대`;
  el('devices').replaceChildren();
  for (const d of filtered) {
    const row = document.createElement('tr');
    if (d.status === 'failed') row.className = 'failed';
    const age = Date.now() - Date.parse(d.received_at);
    const fields = [d.hostname, `${d.school_code || '미지정'} / ${d.grade == null ? '공용·미지정' : d.grade + '학년'}`, `${d.serial || '미수집'} / ${d.model || '미수집'}`, d.mac || '미수집', d.office, d.hancom,
      `${d.stage} / ${statusNames[d.status] || d.status}`, `${d.error_code || '—'} / ${d.installer_exit_code ?? '—'}`,
      d.reboot_required ? '필요' : '—', `${new Date(d.received_at).toLocaleString()}${age > 300000 ? ' (5분 경과)' : ''}`];
    for (const value of fields) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    el('devices').append(row);
  }
}
async function poll(version) {
  try {
    const response = await fetch('/api/devices', {headers: {Authorization: `Bearer ${token}`}, cache: 'no-store', signal: AbortSignal.timeout(8000)});
    if (version !== generation) return;
    if (!response.ok) {
      if (response.status === 401) { disconnect(); el('connection').textContent = '조회 토큰을 확인하세요.'; return; }
      throw new Error('server');
    }
    const data = await response.json();
    if (version !== generation) return;
    devices = data.devices; render(); el('connection').textContent = `연결됨 · 갱신 ${new Date().toLocaleTimeString()}`;
  } catch (_) { if (version === generation) el('connection').textContent = '갱신 실패 · 표시된 데이터는 마지막 성공 시점의 상태입니다.'; }
  if (version === generation && token) timer = setTimeout(() => poll(version), 5000);
}
function disconnect() { generation++; clearTimeout(timer); token = ''; devices = []; render(); el('token').value = ''; el('connection').textContent = '연결 해제됨'; }
el('login').addEventListener('submit', event => { event.preventDefault(); generation++; clearTimeout(timer); token = el('token').value.trim(); el('token').value = ''; devices = []; render(); if (token) poll(generation); });
el('logout').addEventListener('click', disconnect);
el('search').addEventListener('input', render);

el('school').addEventListener('input', render);
el('grade').addEventListener('change', render);
