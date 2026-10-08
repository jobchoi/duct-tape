'use strict';
const portal = (() => {
  const el = id => document.getElementById(id), admin = document.body.dataset.role === 'admin';
  const names = {queued:'셋업 대기',running:'셋업 진행 중',succeeded:'셋업 완료',failed:'셋업 실패',interrupted:'PC 상태 확인 필요',cancelled:'취소됨'};
  let mode = 'secure', deviceId = '', serverMediaReady = false, missingMedia = [];
  let token = '', authenticated = false, timer = null, version = 0, pending = false, selected = '', agents = [], jobs = [], clientApproved = false;
  const connected = () => admin ? authenticated : Boolean(token || deviceId);
  async function api(path, body, method) {
    const response = await fetch(path, {method:method || (body ? 'POST':'GET'),credentials:'same-origin',headers:{'X-Duct-Tape-Request':'1',...(!admin && mode==='development' && deviceId ? {'X-Duct-Device-ID':deviceId} : !admin && token ? {Authorization:`Bearer ${token}`} : {}),...(body ? {'Content-Type':'application/json'} : {})},...(body ? {body:JSON.stringify(body)} : {}),cache:'no-store',signal:AbortSignal.timeout(10000)});
    if (!response.ok) {
      const error = new Error(response.status===401 ? (admin ? (path==='/api/admin/session' && body ? '관리자 인증 키가 올바르지 않습니다.' : '관리자 로그인이 필요합니다.') : '바탕화면 바로가기로 다시 접속하세요.') : response.status===403 ? '관리자의 PC 연결 승인을 기다려 주세요.' : response.status===409 ? '연결 또는 진행 중인 셋업 상태를 먼저 확인하세요.' : '서버 요청에 실패했습니다. 연결 상태를 확인하세요.');
      error.status=response.status; throw error;
    }
    return response.json();
  }
  let progressJob = '', progressAfter = -1, progressEvents = [], progressTimer = null, progressClock = null, progressState = null, legacyProgress = null;
  const eventStatus = {started:'시작',progress:'진행',completed:'완료',failed:'실패'};
  function duration(seconds) { const value=Math.max(0,Math.floor(seconds));return value<60 ? `${value}초` : `${Math.floor(value/60)}분 ${value%60}초`; }
  function counter(event) {
    if (event.current == null) return '';
    if (event.unit==='bytes') { const mb=n=>(n/1048576).toFixed(1);return `${mb(event.current)} MB${event.total ? ' / '+mb(event.total)+' MB · '+Math.floor(event.current/event.total*100)+'%' : ''}`; }
    return `${event.current}${event.total ? ' / '+event.total : ''}${event.unit==='steps' ? '단계' : '개'}`;
  }
  function paintProgress() {
    if (!progressState) return;
    const now=Date.now()/1000, active=['queued','running'].includes(progressState.state);
    el('progress-state').textContent=names[progressState.state] || progressState.state;
    el('progress-panel').dataset.state=progressState.state;
    el('progress-meta').textContent=`요청 후 ${duration((active ? now : progressState.updated)-progressState.created)} · ${progressState.state==='queued' ? '실행 도구 인수 대기' : progressState.state==='running' ? '마지막 실행 도구 응답 '+duration(now-progressState.updated)+' 전' : '최종 상태 수신 '+new Date(progressState.updated*1000).toLocaleTimeString()}`;
    const grouped=new Map();
    for (const event of progressEvents) {
      const key=event.phase+'/'+(event.module || '');
      const old=grouped.get(key);grouped.set(key,{...event,started:old?.started || event.received});
    }
    el('progress-events').replaceChildren();
    if (legacyProgress && !progressEvents.some(e=>e.sequence>0 && e.sequence<2147483647)) {
      const row=document.createElement('li');row.textContent=`최근 수신 단계 · ${legacyProgress.label} · ${names[legacyProgress.status] || legacyProgress.status} · ${new Date(legacyProgress.received*1000).toLocaleTimeString()}`;el('progress-events').append(row);
    }
    for (const event of grouped.values()) {
      const row=document.createElement('li');row.className=event.status;
      const elapsed=active && ['started','progress'].includes(event.status) ? ` · ${duration(now-event.started)} 경과` : event.received-event.started>=1 ? ` · ${duration(event.received-event.started)} 소요` : '';
      row.textContent=`${new Date(event.received*1000).toLocaleTimeString()}  ${event.label} · ${eventStatus[event.status] || event.status}${counter(event) ? ' · '+counter(event) : ''}${elapsed}`;
      el('progress-events').append(row);
    }
    const last=[...grouped.values()].reverse().find(e=>e.current!=null && e.total);
    el('progress-bar').hidden=!last;
    if (last) {el('progress-bar').max=last.total;el('progress-bar').value=last.current;el('progress-caption').textContent=`${last.unit==='steps' ? '완료한 실행 단계' : last.label} · ${counter(last)}`;}
    else el('progress-caption').textContent=progressState.state==='queued' ? '요청이 접수되었습니다. 실행 도구가 작업을 가져오기를 기다립니다.' : '현재 단계와 경과 시간을 확인하세요.';
    const detailed=progressEvents.some(e=>e.sequence>0 && e.sequence<2147483647);
    el('progress-warning').textContent=progressState.state==='running' && !detailed ? '실행 도구 응답은 확인 중입니다. 상세 단계가 나타나지 않으면 최신 실행 도구로 갱신하세요.' : '설치기는 단계와 경과 시간을 표시합니다. 수치 막대는 실제 다운로드량·압축 해제 항목·완료 단계 기준입니다.';
  }
  function clearProgress() {
    clearTimeout(progressTimer);clearInterval(progressClock);progressJob='';progressAfter=-1;progressEvents=[];progressState=null;legacyProgress=null;
    el('progress-panel').hidden=true;el('progress-events').replaceChildren();
  }
  async function readProgress(id,current) {
    try {
      const data=await api(`${admin ? '/api/admin':'/api/client'}/jobs/${id}/progress?after=${progressAfter}`);
      if (id!==progressJob || current!==version) return;
      progressState=data.job;legacyProgress=data.legacy || null;
      for (const event of data.events) {progressEvents.push(event);progressAfter=Math.max(progressAfter,event.sequence);}
      paintProgress();
      if (data.has_more) progressTimer=setTimeout(()=>readProgress(id,current),0);
      else if (['queued','running'].includes(data.job.state)) progressTimer=setTimeout(()=>readProgress(id,current),2000);
      else clearInterval(progressClock);
    } catch (_) {
      if (id===progressJob && current===version) {el('progress-warning').textContent='진행 내역 갱신 실패 · 마지막 수신 내용을 유지합니다.';progressTimer=setTimeout(()=>readProgress(id,current),3000);}
    }
  }
  function watchProgress(job) {
    if (!job?.id) {if (progressJob) clearProgress();return;}
    if (progressJob===job.id) return;
    clearProgress();progressJob=job.id;progressState=job;el('progress-panel').hidden=false;paintProgress();
    progressClock=setInterval(paintProgress,1000);readProgress(job.id,version);
  }
  const busy = id => jobs.some(job => job.device_id===id && ['queued','running','interrupted'].includes(job.state));
  function updateSelection() {
    const agent = agents.find(item => item.device_id===selected);
    if (!agent) selected='';
    el('selected').textContent = agent ? `선택한 PC: ${agent.hostname}${busy(selected) ? ' · '+names[jobs.find(j => j.device_id===selected && ['queued','running','interrupted'].includes(j.state)).state] : ''}` : '위 목록에서 PC를 선택하세요.';
    el('start').disabled = pending || !agent || !agent.approved || !(agent.setup_ready || serverMediaReady) || Date.now()/1000-agent.last_seen>=120 || busy(selected);
    el('start-reason').textContent = !agent ? (agents.length ? '목록에서 작업할 PC를 선택하세요.' : '실행 도구 설치 또는 연결 복구 후 PC를 선택할 수 있습니다.') : !agent.approved ? 'PC 연결 승인이 필요합니다.' : Date.now()/1000-agent.last_seen>=120 ? 'PC가 응답하지 않습니다. 실행 도구와 Tailscale을 확인하세요.' : busy(selected) ? '기존 작업이 끝나거나 중단 상태를 확인한 뒤 시작할 수 있습니다.' : !(agent.setup_ready || serverMediaReady) ? '설치 매체가 준비되면 시작할 수 있습니다.' : '셋업을 시작할 수 있습니다.';
    el('media-status').textContent = agent?.setup_ready ? '선택 PC의 설치 매체가 준비되었습니다.' : serverMediaReady ? '서버 매체 준비 완료 · PC에서 자동으로 내려받습니다.' : `서버 확인이 필요한 파일\n${missingMedia.join('\n') || '배포 원본 경로를 확인하세요.'}`;
    watchProgress(agent ? jobs.find(j=>j.device_id===agent.device_id) : null);
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
    el('summary').textContent=`등록 ${agents.length}대 · 승인 대기 ${agents.filter(a=>!a.approved).length}대`;
    const missing = new Set(reports.filter(report => !agents.some(a=>a.device_id===report.device_id)).map(report=>report.device_id)).size;
    el('unmanaged').textContent=missing ? `현재 PC 등록이 없는 기기의 이전 상태 보고 ${missing}대를 별도 보관 중입니다.` : '';
    el('legacy-count').textContent=`${missing}대`;el('legacy-reports').hidden=missing===0;
    el('metric-online').textContent=String(agents.filter(a=>a.approved && Date.now()/1000-a.last_seen<120).length);
    el('metric-pending').textContent=String(agents.filter(a=>!a.approved).length);
    el('metric-media').textContent=serverMediaReady ? '준비 완료' : `누락 ${missingMedia.length}개`;
    for (const agent of agents) {
      const row=document.createElement('tr'), report=reports.find(r=>r.device_id===agent.device_id), latest=jobs.find(j=>j.device_id===agent.device_id);
      row.className=selected===agent.device_id ? 'is-selected':'';
      const values=[agent.hostname, !agent.approved ? '연결 승인 대기' : Date.now()/1000-agent.last_seen<120 ? '연결됨':'연결 끊김', report ? `${report.office} / ${report.hancom}` : '아직 보고 없음', !agent.setup_ready && !serverMediaReady ? '설치 매체 준비 필요' : latest ? names[latest.state] || latest.state : '셋업 전'];
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
    version++;clearProgress();clearTimeout(timer);token='';authenticated=false;selected='';agents=[];jobs=[];clientApproved=false;deviceId='';el('start').disabled=true;
    if (admin) { el('access-token').value='';el('devices').replaceChildren();el('summary').textContent='';el('unmanaged').textContent='';el('empty').hidden=false;el('admin-content').hidden=true;el('legacy-reports').hidden=true;updateSelection(); }
    el('result').textContent='';el('notice').textContent=admin ? '관리자 로그인 후 PC 연결 상태를 확인할 수 있습니다.' : '처음이면 실행 도구를 다운로드해 설치하세요. 설치 후 바탕화면 바로가기가 생성됩니다.';
  }
  async function poll(current) {
    try {
      const configuration=await api('/api/config');if (current!==version) return;serverMediaReady=Boolean(configuration.media?.ready);missingMedia=configuration.media?.missing || [];
      if (admin) {
        const [devices,work,reports]=await Promise.all([api('/api/admin/agents'),api('/api/admin/jobs'),api('/api/devices')]);
        if (current!==version) return;
        el('admin-content').hidden=false;el('auth-status').textContent=mode==='development' ? '로컬 테스트 모드 · 인증 키 없이 연결됨' : '관리자 로그인 완료';agents=devices.agents;jobs=work.jobs;renderAdmin(reports.devices,current);el('notice').textContent='서버에 연결됨 · 5초마다 갱신';

      } else {
        const data=await api('/api/client/jobs');if (current!==version) return;
        jobs=data.jobs;watchProgress(jobs[0]);clientApproved=Boolean(data.approved);
        el('onboarding').hidden=true;
        el('notice').textContent=clientApproved ? `${data.hostname} · ${data.setup_ready || serverMediaReady ? '셋업 준비됨' : '실행 도구 연결 완료'}` : `${data.hostname} · 관리자의 연결 승인을 기다리고 있습니다.`;
        el('client-state').textContent=!data.setup_ready && !serverMediaReady ? '셋업하려면 C:\\ProgramData\\DuctTapeAgent에 Office·Hancom 매체와 Config\\HancomKey.txt·OfficeKey.txt를 준비하세요.' : jobs[0] ? names[jobs[0].state] || jobs[0].state : '';
        el('start').disabled=pending || !clientApproved || !(data.setup_ready || serverMediaReady) || jobs.some(j=>['queued','running','interrupted'].includes(j.state));
      }
    } catch (error) { if (current===version) { if (error.status===401) { disconnect(); if (!admin) { try {sessionStorage.removeItem('duct-client-key');sessionStorage.removeItem('duct-client-device');el('onboarding').hidden=false;} catch (_) {} } } el('notice').textContent=error.message;el('start').disabled=true; } }
    if (current===version && connected()) timer=setTimeout(()=>poll(current),5000);
  }
  disconnect();
  el('request').addEventListener('submit',async event=>{
    event.preventDefault();if (!connected() || pending || el('start').disabled) return;
    const target=admin ? agents.find(a=>a.device_id===selected)?.hostname : '이 PC';
    if (!confirm(`${target}에서 기존 Office·한컴 제거 및 설치를 시작할까요?`)) return;
    const current=version;pending=true;el('start').disabled=true;
    try {const job=await api(admin ? '/api/admin/jobs':'/api/client/jobs',{action:'deploy',request_id:crypto.randomUUID(),...(admin ? {device_id:selected} : {})});if (current===version) {if (job.id) {jobs=[job,...jobs.filter(j=>j.id!==job.id)];watchProgress(job);}el('result').textContent='환경 셋업을 요청했습니다. 진행 상태가 자동 갱신됩니다.';}}
    catch (error) {if (current===version) el('result').textContent=error.message;}
    finally {pending=false;if (current===version && connected()) {clearTimeout(timer);poll(current);}}
  });
  if (admin) {
    el('access').addEventListener('submit',async event=>{
      event.preventDefault();const key=el('access-token').value.trim();disconnect();const current=version;if (!key) return;
      el('notice').textContent='로그인 확인 중…';el('login-button').disabled=true;
      try {await api('/api/admin/session',{token:key});if (current!==version) return;authenticated=true;el('auth-status').textContent='관리자 로그인 완료';await poll(current);}
      catch (error) {if (current===version) el('notice').textContent=error.message;}
      finally {el('login-button').disabled=false;}
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
  }
  async function initialize() {
    const current=version;
    try {
      const config=await api('/api/config');if (current!==version) return;mode=config.auth_mode;serverMediaReady=Boolean(config.media?.ready);missingMedia=config.media?.missing || [];
      if (admin) {
        el('access').hidden=mode==='development';
        if (mode==='development') {authenticated=true;await poll(current);}
        else {el('auth-status').textContent='관리자 로그인이 필요합니다.';try {await api('/api/admin/session');if (current===version) {authenticated=true;await poll(current);}} catch (_) {}}
      } else {
        const fragment=new URLSearchParams(location.hash.slice(1));
        const key=fragment.get('key'), id=fragment.get('device');
        if (key || id) history.replaceState(null,'',location.pathname);
        if (mode==='development') {deviceId=id || sessionStorage.getItem('duct-client-device') || '';if (id) sessionStorage.setItem('duct-client-device',id);}
        else {token=key || sessionStorage.getItem('duct-client-key') || '';if (key) sessionStorage.setItem('duct-client-key',key);}
        if (connected()) await poll(current);
      }
    } catch (error) {if (current===version) el('notice').textContent=error.message;}
  }
  initialize();
  return {disconnect};
})();
