'use strict';
(async () => {
  const admin=location.pathname.startsWith('/admin'), prefix=admin?'/api/admin':'/api/client';
  const el=id=>document.getElementById(id), selected=new Set(), progressCache=new Map();
  let mode='secure', busy=false, refreshing=false, list=[], agents=[], lastJobs=[];
  el('title').textContent=admin?'앱 관리 · v2':'선택 앱 설치 · v2';
  el('back').href=admin?'/admin':'/client';
  el('admin-tools').hidden=!admin;el('pc-picker').hidden=!admin;el('manage-head').hidden=!admin;
  const phases={queued:'대기',running:'실행 중',succeeded:'설치 작업 완료',failed:'실패',interrupted:'중단 확인 필요',cancelled:'취소'};
  async function api(path,body,method='GET') {
    const headers={'X-Duct-Tape-Request':'1'};
    if(!admin){
      const key=sessionStorage.getItem('duct-client-key'), device=sessionStorage.getItem('duct-client-device');
      if(mode==='development'&&device)headers['X-Duct-Device-ID']=device;
      else if(key)headers.Authorization='Bearer '+key;
    }
    if(body && !(body instanceof FormData))headers['Content-Type']='application/json';
    const response=await fetch(path,{method,headers,credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(body instanceof FormData?600000:15000),...(body?{body:body instanceof FormData?body:JSON.stringify(body)}:{})});
    if(!response.ok){
      let detail='';try{detail=(await response.json()).detail||'';}catch(_){}
      throw new Error(response.status===401?'기존 화면에서 로그인 또는 바탕화면 바로가기로 연결한 뒤 다시 열어주세요.':response.status===403?'PC 관리자 승인 또는 권한을 확인하세요.':`${response.status} · ${detail}`);
    }
    return response.json();
  }
  function text(tag,value){const n=document.createElement(tag);n.textContent=String(value);return n;}
  function button(label,action){const n=text('button',label);n.type='button';n.disabled=busy;n.addEventListener('click',()=>run(action));return n;}
  function updateStart(){
    const target=admin?el('pc').value:null;
    const active=lastJobs.find(j=>(!admin||j.device_id===target)&&['queued','running','interrupted'].includes(j.state));
    const reason=busy?'요청 처리 중입니다.':!selected.size?'설치할 공개 앱을 선택하세요.':admin&&!target?'승인된 PC를 선택하세요.':active?(active.state==='interrupted'?'중단된 작업의 실제 PC 상태를 확인한 뒤 기존 관리자 화면에서 정리하세요.':'이 PC의 기존 작업이 대기 또는 실행 중입니다.') : '';
    el('install').disabled=Boolean(reason);el('install-reason').textContent=reason;
  }
  function lockControls(){for(const control of document.querySelectorAll('button'))control.disabled=busy;updateStart();}
  async function run(action){if(busy)return;busy=true;lockControls();try{await action();await refresh();}catch(e){el('message').textContent=e.message;}finally{busy=false;renderApps();lockControls();}}
  function renderApps(){
    el('app-list').replaceChildren();el('empty').textContent=list.length?'':'아직 공개된 설치 앱이 없습니다.';
    for(const app of list){
      const key=app.id+'@'+app.version,row=document.createElement('tr'),choice=document.createElement('input');choice.type='checkbox';choice.disabled=!app.published||app.id==='argos-mdm';choice.checked=selected.has(key);
      choice.setAttribute('aria-label',app.name+' '+app.version+' 선택');
      choice.addEventListener('change',()=>{choice.checked?selected.add(key):selected.delete(key);updateStart();});
      const cell=document.createElement('td');cell.append(choice);row.append(cell);
      for(const value of [app.name+(app.enrollment?' · 사용자 등록 필요':''),app.version,(app.size/1048576).toFixed(1)+' MB',app.published?'공개':'초안'])row.append(text('td',value));
      if(app.id==='argos-mdm'&&app.published){cell.append(button('MDM ZIP 다운로드',async()=>{
        const headers={'X-Duct-Tape-Request':'1'};if(!admin){const key=sessionStorage.getItem('duct-client-key');if(mode==='development')headers['X-Duct-Device-ID']=sessionStorage.getItem('duct-client-device')||'';else if(key)headers.Authorization='Bearer '+key;}
        const response=await fetch(prefix+'/mdm/'+encodeURIComponent(app.version)+'/package',{headers,credentials:'same-origin',cache:'no-store'});
        if(!response.ok)throw new Error('다운로드 권한과 PC 승인 상태를 확인하세요.');
        const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download='ArgosMDM-'+app.version+'.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
      }));}
      if(admin){const tools=document.createElement('td');tools.append(button(app.published?'비공개로 전환':'검토 후 공개',async()=>{
        if(!app.published&&!confirm(app.id==='argos-mdm'?'MDM 원본을 검토했나요? 승인된 PC에 수동 설치용 ZIP을 공개합니다.':'MSI 단독 무인 설치와 필수 구성요소를 검증했나요?'))return;
        await api('/api/admin/applications/'+encodeURIComponent(app.id)+'/'+encodeURIComponent(app.version),{published:!app.published,reviewed:true},'PUT');
      }));row.append(tools);}el('app-list').append(row);
    }
    const valid=new Set(list.filter(a=>a.published).map(a=>a.id+'@'+a.version));for(const key of selected)if(!valid.has(key))selected.delete(key);
    updateStart();
  }
  async function refresh(){
    const data=await api(prefix+'/applications');list=data.applications;renderApps();
    if(admin){
      el('secret-state').textContent=data.enrollment_config.configured?'등록 정보 준비됨 · 버튼으로 확인 가능':'등록 정보 미설정 · MDM 다운로드는 사용 가능';
      agents=(await api('/api/admin/agents')).agents;
      const previous=el('pc').value;el('pc').replaceChildren();
      for(const agent of agents.filter(a=>a.approved)){const option=text('option',agent.hostname);option.value=agent.device_id;el('pc').append(option);}if(agents.some(a=>a.device_id===previous))el('pc').value=previous;
    }
    const status=await api(prefix+'/application-results');lastJobs=status.jobs;updateStart();
    const visible=status.jobs.filter(j=>j.action==='install-apps').slice(0,20);el('jobs').replaceChildren();
    for(const job of visible){
      const box=document.createElement('article');box.className='readiness-box';
      const name=admin?(agents.find(a=>a.device_id===job.device_id)?.hostname||job.device_id):'이 PC';
      box.append(text('h3',name+' · '+(phases[job.state]||job.state)),text('small',job.id));
      for(const r of status.results.filter(r=>r.job_id===job.id))box.append(text('p',`${r.name} ${r.version} · ${r.verified?(r.status==='already_installed'?'기존 설치 확인':'설치 확인'):'실패 '+r.error_code} · ${r.enrollment==='required'?(r.verified?'MDM 사용자 등록 필요':'설치 확인 후 등록'):'추가 등록 없음'}${r.reboot_required?' · 재부팅 필요':''}`));
      el('jobs').append(box);
      let cached=progressCache.get(job.id)||{after:-1,latest:null};
      let progress;do {
        progress=await api(prefix+'/jobs/'+job.id+'/progress?after='+cached.after);
        for(const event of progress.events){cached.after=event.sequence;if(event.sequence<2147483647)cached.latest=event;}
      }while(progress.has_more);
      progressCache.set(job.id,cached);
      const latest=cached.latest;
      if(latest)box.append(text('p',`${latest.label} · ${{started:'시작',progress:'진행',completed:'완료',failed:'실패'}[latest.status]||latest.status}${latest.unit==='bytes'?` · ${(latest.current/1048576).toFixed(1)} / ${latest.total?(latest.total/1048576).toFixed(1):'?'} MB`:''}`));
    }
    if(!visible.length)el('jobs').append(text('p','선택 앱 설치 작업이 없습니다.'));
  }
  function hideRegistration(){el('registration-details').replaceChildren();el('registration-details').hidden=true;}
  let revealTimer;
  el('hide-registration').addEventListener('click',hideRegistration);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)hideRegistration();});
  el('show-registration').addEventListener('click',()=>run(async()=>{
    const details=await api(prefix+'/mdm/registration');hideRegistration();
    const box=el('registration-details');box.hidden=false;
    if(!details.configured){box.append(text('p','서버의 Config/ArgosEnrollment.json과 파일 권한(600)을 확인하세요.'));return;}
    for(const [key,label] of [['server_url','등록 URL'],['email','이메일'],['username','계정'],['password','비밀번호']])box.append(text('p',label+': '+(details[key]||'미설정')));
    clearTimeout(revealTimer);revealTimer=setTimeout(hideRegistration,60000);
  }));
  el('pc').addEventListener('change',updateStart);
  el('install').addEventListener('click',()=>run(async()=>{
    const device=admin?el('pc').value:null;
    if(admin&&!device)throw new Error('승인된 PC를 선택하세요.');
    const applications=[...selected].map(k=>{const [id,version]=k.split('@');return {id,version};});
    if(new Set(applications.map(a=>a.id)).size!==applications.length)throw new Error('같은 앱은 한 버전만 선택하세요.');
    const job=await api(admin?'/api/admin/agents/'+device+'/application-jobs':'/api/client/application-jobs',{applications,request_id:crypto.randomUUID()},'POST');
    el('message').textContent='작업 요청 완료: '+job.id;
  }));
  el('app-form').addEventListener('submit',event=>{event.preventDefault();run(async()=>{
    const values=new FormData(event.target), body=new FormData();
    const manifest={schema_version:2};for(const key of ['id','name','version','installer','product_code'])manifest[key]=values.get(key);
    manifest.enrollment=values.has('enrollment');body.set('manifest',JSON.stringify(manifest));body.set('package',values.get('package'));
    el('upload-state').textContent='업로드·원본 검사 중…';
    try{await api('/api/admin/applications',body,'POST');el('upload-state').textContent='초안 등록 완료';}catch(e){el('upload-state').textContent='등록 실패';throw e;}
  });});
  el('import-argos').addEventListener('click',()=>run(async()=>{await api('/api/admin/applications/import-argos',{},'POST');el('message').textContent='Argos 초안 등록 완료. 원본 검토 후 수동 다운로드용으로 공개하세요.';}));
  try{mode=(await api('/api/config')).auth_mode;await refresh();el('message').textContent='연결됨 · v2 시험 기능';}catch(e){el('message').textContent=e.message;}
  setInterval(async()=>{if(busy||refreshing)return;refreshing=true;try{await refresh();}catch(e){el('message').textContent=e.message;}finally{refreshing=false;}},5000);
})();
