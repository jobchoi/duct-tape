'use strict';
const portal = (() => {
  const el = id => document.getElementById(id), admin = document.body.dataset.role === 'admin';
  const names = {queued:'셋업 대기',running:'셋업 진행 중',succeeded:'셋업 완료',failed:'셋업 실패',interrupted:'PC 상태 확인 필요',cancelled:'취소됨'};
  let token = '', authenticated = false, timer = null, version = 0, pending = false, selected = '', agents = [], jobs = [], clientApproved = false;
  const connected = () => admin ? authenticated : Boolean(token);
  async function api(path, body, method) {
    const response = await fetch(path, {method:method || (body ? 'POST':'GET'),credentials:'same-origin',headers:{'X-Duct-Tape-Request':'1',...(!admin && token ? {Authorization:`Bearer ${token}`} : {}),...(body ? {'Content-Type':'application/json'} : {})},...(body ? {body:JSON.stringify(body)} : {}),cache:'no-store',signal:AbortSignal.timeout(10000)});
    if (!response.ok) {
      const error = new Error(response.status===401 ? (admin ? '관리자 로그인이 필요합니다.' : '바탕화면 바로가기로 다시 접속하세요.') : response.status===403 ? '관리자의 PC 연결 승인을 기다려 주세요.' : response.status===409 ? '연결 또는 진행 중인 셋업 상태를 먼저 확인하세요.' : '서버 요청에 실패했습니다. 연결 상태를 확인하세요.');
      error.status=response.status; throw error;
    }
    return response.json();
  }
  const busy = id => jobs.some(job => job.device_id===id && ['queued','running','interrupted'].includes(job.state));
  function updateSelection() {
    const agent = agents.find(item => item.device_id===selected);
    if (!agent) selected='';
    el('selected').textContent = agent ? `선택한 PC: ${agent.hostname}${busy(selected) ? ' · '+names[jobs.find(j => j.device_id===selected && ['queued','running','interrupted'].includes(j.state)).state] : ''}` : '위 목록에서 PC를 선택하세요.';
    el('start').disabled = pending || !agent || !agent.approved || Date.now()/1000-agent.last_seen>=120 || busy(selected);
    el('revoke').disabled = !agent;
    el('resolve').disabled = !jobs.some(job => job.device_id===selected && job.state==='interrupted');
  }
  async function approve(id, current) {
    try { await api(`/api/admin/agents/${encodeURIComponent(id)}/approve`,{}); if (current===version) { selected=id; el('result').textContent='PC 연결을 승인했습니다.'; clearTimeout(timer); poll(current); } }
    catch (error) { if (current===version) el('result').textContent=error.message; }
  }
  function renderAdmin(reports, current) {
    el('devices').replaceChildren();
    el('empty').hidden=agents.length>0;
    el('summary').textContent=`연결된 PC ${agents.filter(a=>a.approved).length}대 · 승인 대기 ${agents.filter(a=>!a.approved).length}대`;
    const missing = new Set(reports.filter(report => !agents.some(a=>a.device_id===report.device_id)).map(report=>report.device_id)).size;
    el('unmanaged').textContent=missing ? `에이전트가 연결되지 않은 보고 ${missing}대는 셋업 대상에서 제외했습니다.` : '';
    for (const agent of agents) {
      const row=document.createElement('tr'), report=reports.find(r=>r.device_id===agent.device_id), latest=jobs.find(j=>j.device_id===agent.device_id);
      const values=[agent.hostname, !agent.approved ? '연결 승인 대기' : Date.now()/1000-agent.last_seen<120 ? '연결됨':'연결 끊김', report ? `${report.office} / ${report.hancom}` : '아직 보고 없음', latest ? names[latest.state] || latest.state : '셋업 전'];
      for (const value of values) { const cell=document.createElement('td');cell.textContent=value;row.append(cell); }
      const cell=document.createElement('td'), button=document.createElement('button');button.type='button';
      button.textContent=agent.approved ? (selected===agent.device_id ? '선택됨':'선택') : '연결 승인';
      button.className=selected===agent.device_id ? 'selected':'secondary';
      button.addEventListener('click',()=> { if (current!==version) return; if (!agent.approved) { approve(agent.device_id,current); return; } selected=agent.device_id;renderAdmin(reports,current); });
      cell.append(button);row.append(cell);el('devices').append(row);
    }
    updateSelection();
  }
  function disconnect() {
    version++;clearTimeout(timer);token='';authenticated=false;selected='';agents=[];jobs=[];clientApproved=false;el('start').disabled=true;
    if (admin) { el('access-token').value='';el('devices').replaceChildren();el('summary').textContent='';el('unmanaged').textContent='';el('empty').hidden=false;updateSelection(); }
    el('result').textContent='';el('notice').textContent=admin ? '관리자 로그인 후 PC 연결 상태를 확인할 수 있습니다.' : '바탕화면의 ‘duct-tape 작업’ 바로가기로 접속하세요.';
  }
  async function poll(current) {
    try {
      if (admin) {
        const [devices,work,reports]=await Promise.all([api('/api/admin/agents'),api('/api/admin/jobs'),api('/api/devices')]);
        if (current!==version) return;
        agents=devices.agents;jobs=work.jobs;renderAdmin(reports.devices,current);el('notice').textContent='서버에 연결됨 · 5초마다 갱신';
      } else {
        const data=await api('/api/client/jobs');if (current!==version) return;
        jobs=data.jobs;clientApproved=Boolean(data.approved);
        el('notice').textContent=clientApproved ? `${data.hostname} · 셋업 준비됨` : `${data.hostname} · 관리자의 연결 승인을 기다리고 있습니다.`;
        el('client-state').textContent=jobs[0] ? names[jobs[0].state] || jobs[0].state : '';
        el('start').disabled=pending || !clientApproved || jobs.some(j=>['queued','running','interrupted'].includes(j.state));
      }
    } catch (error) { if (current===version) { if (error.status===401) { disconnect(); if (!admin) { try {sessionStorage.removeItem('duct-client-key');} catch (_) {} } } el('notice').textContent=error.message;el('start').disabled=true; } }
    if (current===version && connected()) timer=setTimeout(()=>poll(current),5000);
  }
  disconnect();
  el('request').addEventListener('submit',async event=>{
    event.preventDefault();if (!connected() || pending || el('start').disabled) return;
    const target=admin ? agents.find(a=>a.device_id===selected)?.hostname : '이 PC';
    if (!confirm(`${target}에서 기존 Office·한컴 제거 및 설치를 시작할까요?`)) return;
    const current=version;pending=true;el('start').disabled=true;
    try {await api(admin ? '/api/admin/jobs':'/api/client/jobs',{action:'deploy',request_id:crypto.randomUUID(),...(admin ? {device_id:selected} : {})});if (current===version) el('result').textContent='환경 셋업을 요청했습니다. 진행 상태가 자동 갱신됩니다.';}
    catch (error) {if (current===version) el('result').textContent=error.message;}
    finally {pending=false;if (current===version && connected()) {clearTimeout(timer);poll(current);}}
  });
  if (admin) {
    el('access').addEventListener('submit',async event=>{
      event.preventDefault();const key=el('access-token').value.trim();disconnect();const current=version;if (!key) return;
      try {await api('/api/admin/session',{token:key});if (current!==version) return;authenticated=true;poll(current);}
      catch (error) {if (current===version) el('notice').textContent=error.message;}
    });
    el('disconnect').addEventListener('click',async()=>{disconnect();try {await api('/api/admin/session',null,'DELETE');} catch (_) {el('notice').textContent='로그아웃 요청 실패. 다시 시도하세요.';}});
    el('resolve').addEventListener('click',async()=>{
      const job=jobs.find(j=>j.device_id===selected && j.state==='interrupted');if (!job || !confirm('대상 PC에서 설치 프로세스가 종료되었는지 확인했습니까?')) return;
      const current=version;try {await api(`/api/admin/jobs/${job.id}/resolve`,{});if (current===version) {el('result').textContent='중단 상태 확인 완료';clearTimeout(timer);poll(current);}} catch (error) {el('result').textContent=error.message;}
    });
    el('revoke').addEventListener('click',async()=>{
      if (!selected || !confirm('선택 PC의 연결을 해제할까요?')) return;
      const current=version;try {await api(`/api/admin/agents/${selected}/revoke`,{});if (current===version) {selected='';clearTimeout(timer);poll(current);}} catch (error) {el('result').textContent=error.message;}
    });
    const current=version;api('/api/admin/session').then(()=>{if (current===version) {authenticated=true;poll(current);}}).catch(()=>{});
  } else {
    const key=new URLSearchParams(location.hash.slice(1)).get('key');
    if (key) {history.replaceState(null,'',location.pathname);token=key;try {sessionStorage.setItem('duct-client-key',key);} catch (_) {}}
    else {try {token=sessionStorage.getItem('duct-client-key') || '';} catch (_) {}}
    if (token) poll(version);
  }
  return {disconnect};
})();
