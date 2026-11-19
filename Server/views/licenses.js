'use strict';
(async()=>{
  const el=id=>document.getElementById(id),names={office:'Office',hancom:'한컴'},states={candidate:'검증 전',verified:'정상 확인',failed:'문제 있음'},actions={save:'저장',import:'기존 파일 보관',apply:'적용',restore:'복구',verify:'정상 확인',fail:'문제 표시'};
  let busy=false;
  async function api(path,body){
    const response=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:{'X-Duct-Tape-Request':'1',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(15000)});
    if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(response.status===401?'PC 관리에서 관리자 로그인 후 다시 열어주세요.':typeof error.detail==='string'?error.detail:'입력 형식과 연결을 확인하세요.');}
    return response.json();
  }
  function text(tag,value){const item=document.createElement(tag);item.textContent=value;return item;}
  function setBusy(value){busy=value;for(const c of document.querySelectorAll('button,input,select'))c.disabled=value;}
  function render(data){
    el('content').hidden=false;el('revisions').replaceChildren();el('summary').replaceChildren();el('audit').replaceChildren();el('usage').replaceChildren();
    for(const app of ['office','hancom']){
      const list=data.revisions.filter(r=>r.app===app),good=list.filter(r=>r.status==='verified').length,active=list.find(r=>r.active);
      el('summary').append(text('p',`${names[app]} · 적용: ${active?.label||'없음'} · 정상 이력 ${good}개${good<3?' / 3개 확보 권장':''}`));
    }
    for(const revision of data.revisions){
      const row=document.createElement('tr');row.dataset.revision=revision.id;
      for(const value of [names[revision.app],revision.label+(revision.note?' · '+revision.note:''),revision.masked,(revision.active?'현재 적용 · ':'')+states[revision.status],new Date(revision.created*1000).toLocaleString()])row.append(text('td',value));
      const cell=document.createElement('td');
      for(const [action,title] of [['apply','이 값 적용'],['verify','정상 확인'],['fail','문제 표시'],['restore','이전 정상 값으로 복구']]){
        if((action==='apply'&&(revision.active||revision.status==='failed'))||(action==='restore'&&(revision.active||revision.status!=='verified'))||(action==='verify'&&revision.status==='verified')||(action==='fail'&&revision.status==='failed'))continue;
        const button=text('button',title);button.type='button';button.disabled=busy;
        button.addEventListener('click',async()=>{
          if(busy)return;
          const prompt=action==='verify'?'이 키로 실제 설치·인증을 확인했습니까?':action==='fail'?'문제 이력으로 표시할까요? 현재 적용 중이면 정상 키 복구 전까지 새 셋업을 막습니다.':`${revision.label}: ${title}할까요? 기존 PC의 키는 다음 셋업에서 갱신됩니다.`;
          if(!window.confirm(prompt))return;
          setBusy(true);
          try{render(await api(`/api/admin/licenses/${revision.app}/${revision.id}`,{action,confirmed:true}));el('message').textContent=title+' 완료';}catch(e){el('message').textContent=e.message;}finally{setBusy(false);}
        });cell.append(button,document.createTextNode(' '));
      }
      row.append(cell);el('revisions').append(row);
    }
    for(const used of data.usage){const revision=data.revisions.find(r=>r.id===used.revision);el('usage').append(text('li',`${names[used.app]} · ${revision?.label||used.revision} · 작업 ${used.job_id} · ${used.state||'상태 없음'} · 종료 ${used.exit_code??'확인 전'}`));}
    for(const event of data.audit){const revision=data.revisions.find(r=>r.id===event.revision);el('audit').append(text('li',`${new Date(event.created*1000).toLocaleString()} · ${names[event.app]} · ${actions[event.action]} · ${revision?.label||event.revision}`));}
  }
  el('key-form').addEventListener('submit',async event=>{
    event.preventDefault();if(busy)return;
    const body={key:el('product-key').value,label:el('label').value,note:el('note').value};el('product-key').value='';setBusy(true);
    try{await api('/api/admin/licenses/'+el('app').value,body);render(await api('/api/admin/licenses'));el('message').textContent='검증 전 이력으로 보관했습니다. 적용할 이력을 선택하세요.';}catch(e){el('message').textContent=e.message;}finally{body.key='';setBusy(false);}
  });
  try{render(await api('/api/admin/licenses'));el('message').textContent='관리자 연결됨 · 제품 키는 다시 표시하지 않습니다.';}catch(e){el('message').textContent=e.message;}
})();
