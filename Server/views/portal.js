'use strict';
const portal = (() => {
  const el = id => document.getElementById(id), admin = document.body.dataset.role === 'admin';
  let token = '', timer = null, version = 0, pending = false;
  const prefix = admin ? '/api/admin' : '/api/client';
  async function api(path, body, key = token) {
    const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {Authorization: `Bearer ${key}`, ...(body ? {'Content-Type': 'application/json'} : {})}, ...(body ? {body: JSON.stringify(body)} : {}), cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error(response.status === 401 ? '접속 키를 확인하세요.' : response.status === 409 ? '진행 중인 작업이 있거나 요청이 충돌했습니다.' : '요청 실패. 연결과 서버 설정을 확인하세요.');
    return response.json();
  }
  function disconnect() {
    version++; clearTimeout(timer); token = ''; el('access-token').value = ''; el('start').disabled = true;
    el('jobs').textContent = ''; el('notice').textContent = '연결 해제됨';
    if (admin) { el('enroll').disabled = true; el('enrollment').textContent = ''; el('device').replaceChildren(); }
  }
  async function poll(current) {
    try {
      const data = await api(prefix + '/jobs');
      if (current !== version) return;
      el('jobs').textContent = data.jobs.map(j => `${admin ? j.id + ' · ' + j.device_id + ' · ' : ''}${j.action} · ${j.state} · ${new Date(j.updated * 1000).toLocaleString()}${j.exit_code == null ? '' : ' · 종료 코드 ' + j.exit_code}`).join('\n') || '작업 이력이 없습니다.';
      el('notice').textContent = admin ? '관리자 연결됨' : `연결된 PC: ${data.device_id}`;
      el('start').disabled = pending || (!admin && data.jobs.some(j => ['queued', 'running', 'interrupted'].includes(j.state)));
      if (admin) el('enroll').disabled = false;
    } catch (error) { if (current === version) { el('notice').textContent = error.message; el('start').disabled = true; } }
    if (current === version && token) timer = setTimeout(() => poll(current), 5000);
  }
  async function connect(key) {
    disconnect(); token = key.trim(); const current = version;
    if (!token) return;
    try {
      if (admin) {
        const data = await api('/api/admin/agents');
        if (current !== version) return;
        for (const agent of data.agents) {
          const option = document.createElement('option'); option.value = agent.device_id;
          option.textContent = `${agent.hostname} · ${Date.now() / 1000 - agent.last_seen < 120 ? '연결됨' : '연결 대기'}`;
          el('device').append(option);
        }
      }
      await poll(current);
    } catch (error) { if (current === version) el('notice').textContent = error.message; }
  }
  // Use one handler, capturing input before clearing it.
  el('access').addEventListener('submit', event => { event.preventDefault(); connect(el('access-token').value); });
  el('disconnect').addEventListener('click', disconnect);
  el('request').addEventListener('submit', async event => {
    event.preventDefault(); if (!token || pending) return;
    const action = el('action').value;
    if (action === 'deploy' && !confirm('대상 PC에서 기존 Office·한컴 제거 및 설치를 시작합니다. 진행할까요?')) return;
    const current = version; pending = true; el('start').disabled = true;
    try {
      await api(prefix + '/jobs', {action, request_id: crypto.randomUUID(), ...(admin ? {device_id: el('device').value} : {})});
      if (current !== version) return;
      el('notice').textContent = '작업 요청 완료. 에이전트가 실행하면 결과가 갱신됩니다.';
    } catch (error) { if (current === version) el('notice').textContent = error.message; }
    finally { pending = false; if (current === version && token) { clearTimeout(timer); poll(current); } }
  });
  if (admin) el('enroll').addEventListener('click', async () => {
    const current = version;
    try { const data = await api('/api/admin/enrollments', {}); if (current === version) el('enrollment').textContent = `등록 코드 (10분 / 1회): ${data.code}`; }
    catch (error) { if (current === version) el('notice').textContent = error.message; }
  });
  if (admin) {
    el('resolve').addEventListener('submit', async event => {
      event.preventDefault(); if (!token || !confirm('해당 PC에서 설치 프로세스가 종료되었는지 확인했습니까?')) return;
      try { await api('/api/admin/jobs/' + encodeURIComponent(el('resolve-id').value.trim()) + '/resolve', {}); clearTimeout(timer); poll(version); }
      catch (error) { el('notice').textContent = error.message; }
    });
    el('revoke').addEventListener('click', async () => {
      if (!token || !el('device').value || !confirm('선택 PC의 접속 키를 폐기하고 등록을 해제할까요?')) return;
      try { await api('/api/admin/agents/' + encodeURIComponent(el('device').value) + '/revoke', {}); await connect(token); }
      catch (error) { el('notice').textContent = error.message; }
    });
  }
  const fragment = new URLSearchParams(location.hash.slice(1)), key = fragment.get('key');
  if (key && !admin) { history.replaceState(null, '', location.pathname); connect(key); }
  return {disconnect};
})();
