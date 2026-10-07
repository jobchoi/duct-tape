'use strict';
const portal = (() => {
  const el = id => document.getElementById(id), admin = document.body.dataset.role === 'admin';
  let token = '', authenticated = false, timer = null, version = 0, pending = false;
  const prefix = admin ? '/api/admin' : '/api/client';
  const connected = () => admin ? authenticated : Boolean(token);
  function announce() {
    if (admin && document.dispatchEvent) document.dispatchEvent(new CustomEvent('admin-session', {detail: {authenticated}}));
  }
  async function api(path, body, method) {
    const response = await fetch(path, {method: method || (body ? 'POST' : 'GET'), credentials: 'same-origin', headers: {'X-Duct-Tape-Request': '1', ...(!admin && token ? {Authorization: `Bearer ${token}`} : {}), ...(body ? {'Content-Type': 'application/json'} : {})}, ...(body ? {body: JSON.stringify(body)} : {}), cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) {
      const error = new Error(response.status === 401 ? (admin ? '관리자 로그인이 필요합니다. 조회 토큰이 아닌 관리자 인증 키로 로그인하세요.' : '접속 키를 확인하세요.') : response.status === 503 ? '서버에 관리자 인증이 설정되지 않았습니다.' : response.status === 409 ? '진행 중인 작업이 있거나 요청이 충돌했습니다.' : '요청 실패. 연결과 서버 설정을 확인하세요.');
      error.status = response.status; throw error;
    }
    return response.json();
  }
  function disconnect() {
    version++; clearTimeout(timer); token = ''; authenticated = false; el('access-token').value = ''; el('start').disabled = true;
    el('jobs').textContent = ''; el('notice').textContent = admin ? '관리자 로그인 후 이용하세요.' : '연결 해제됨';
    if (admin) { el('enrollment').textContent = ''; el('device').replaceChildren(); announce(); }
  }
  async function poll(current) {
    try {
      if (admin) {
        const data = await api('/api/admin/agents');
        if (current !== version) return;
        const selected = el('device').value; el('device').replaceChildren();
        for (const agent of data.agents) {
          const option = document.createElement('option'); option.value = agent.device_id;
          option.textContent = `${agent.hostname} · ${Date.now() / 1000 - agent.last_seen < 120 ? '연결됨' : '연결 대기'}`;
          el('device').append(option);
        }
        if (data.agents.some(agent => agent.device_id === selected)) el('device').value = selected;
      }
      const data = await api(prefix + '/jobs');
      if (current !== version) return;
      el('jobs').textContent = data.jobs.map(j => `${admin ? j.id + ' · ' + j.device_id + ' · ' : ''}${j.action} · ${j.state} · ${new Date(j.updated * 1000).toLocaleString()}${j.exit_code == null ? '' : ' · 종료 코드 ' + j.exit_code}`).join('\n') || '작업 이력이 없습니다.';
      el('notice').textContent = admin ? '관리자 로그인됨' : `연결된 PC: ${data.device_id}`;
      el('start').disabled = pending || (!admin && data.jobs.some(j => ['queued', 'running', 'interrupted'].includes(j.state)));
    } catch (error) {
      if (current === version) {
        if (error.status === 401) disconnect();
        el('notice').textContent = error.message; el('start').disabled = true;
      }
    }
    if (current === version && connected()) timer = setTimeout(() => poll(current), 5000);
  }
  async function connect(key) {
    disconnect(); const current = version;
    if (!key.trim()) return;
    try {
      if (admin) { await api('/api/admin/session', {token: key.trim()}); if (current !== version) return; authenticated = true; announce(); }
      else token = key.trim();
      await poll(current);
    } catch (error) { if (current === version) el('notice').textContent = error.message; }
  }
  el('access').addEventListener('submit', event => { event.preventDefault(); connect(el('access-token').value); });
  el('disconnect').addEventListener('click', async () => {
    disconnect();
    if (admin) { try { await api('/api/admin/session', null, 'DELETE'); } catch (_) { el('notice').textContent = '로그아웃 요청 실패. 다시 시도하세요.'; } }
  });
  el('request').addEventListener('submit', async event => {
    event.preventDefault(); if (!connected() || pending) return;
    const action = el('action').value;
    if (action === 'deploy' && !confirm('대상 PC에서 기존 Office·한컴 제거 및 설치를 시작합니다. 진행할까요?')) return;
    const current = version; pending = true; el('start').disabled = true;
    try { await api(prefix + '/jobs', {action, request_id: crypto.randomUUID(), ...(admin ? {device_id: el('device').value} : {})}); }
    catch (error) { if (current === version) el('notice').textContent = error.message; }
    finally { pending = false; if (current === version && connected()) { clearTimeout(timer); poll(current); } }
  });
  if (admin) {
    el('enroll').addEventListener('click', async () => {
      if (!authenticated) { el('enrollment').textContent = '먼저 화면 위에서 관리자 로그인을 진행하세요.'; el('access-token').focus(); return; }
      const current = version; el('enroll').disabled = true; el('enrollment').textContent = '등록 코드 발급 중…';
      try {
        const data = await api('/api/admin/enrollments', {});
        if (current === version) el('enrollment').textContent = `등록 코드 (10분 / 1회): ${data.code}`;
      } catch (error) { if (current === version) el('enrollment').textContent = error.message; }
      finally { el('enroll').disabled = false; }
    });
    el('resolve').addEventListener('submit', async event => {
      event.preventDefault(); if (!authenticated || !confirm('해당 PC에서 설치 프로세스가 종료되었는지 확인했습니까?')) return;
      try { await api('/api/admin/jobs/' + encodeURIComponent(el('resolve-id').value.trim()) + '/resolve', {}); clearTimeout(timer); poll(version); }
      catch (error) { el('notice').textContent = error.message; }
    });
    el('revoke').addEventListener('click', async () => {
      if (!authenticated || !el('device').value || !confirm('선택 PC의 접속 키를 폐기하고 등록을 해제할까요?')) return;
      try { await api('/api/admin/agents/' + encodeURIComponent(el('device').value) + '/revoke', {}); clearTimeout(timer); poll(version); }
      catch (error) { el('notice').textContent = error.message; }
    });
    const current = version;
    api('/api/admin/session').then(() => { if (current === version) { authenticated = true; announce(); poll(current); } }).catch(() => {});
  }
  const fragment = new URLSearchParams(location.hash.slice(1)), key = fragment.get('key');
  if (key && !admin) { history.replaceState(null, '', location.pathname); connect(key); }
  return {disconnect};
})();
