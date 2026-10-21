'use strict';
(async()=>{
  const el=id=>document.getElementById(id);
  let settings={},reports=[],agents=[],working=false,hasImage=false;
  const labels={qr:'QR 생성',mdm_download:'MDM 다운로드·등록 정보 확인'};
  async function api(path,body){
    const response=await fetch(path,{method:body?'PUT':'GET',credentials:'same-origin',cache:'no-store',headers:{'X-Duct-Tape-Request':'1',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error(response.status===401?'PC 관리 화면에서 관리자 로그인 후 다시 열어주세요.':'요청 실패 ('+response.status+'). 권한과 서버 상태를 확인하세요.');
    return response.json();
  }
  function clearImage(){hasImage=false;el('preview').hidden=true;const c=el('qr-canvas');c.getContext('2d').clearRect(0,0,c.width,c.height);}
  function showSettings(){
    el('feature-panel').hidden=false;el('features').replaceChildren();
    for(const [key,enabled] of Object.entries(settings)){
      const row=document.createElement('p'),label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=enabled;check.disabled=working;check.dataset.feature=key;
      label.append(check,document.createTextNode(' '+(labels[key]||key)));row.append(label);el('features').append(row);
      check.addEventListener('change',async()=>{
        if(working)return;working=true;for(const control of el('features').querySelectorAll('input'))control.disabled=true;
        try{settings=(await api('/api/admin/features/'+key,{enabled:check.checked})).features;el('message').textContent='설정을 저장했습니다.';}
        catch(error){el('message').textContent=error.message;}
        finally{working=false;showSettings();}
      });
    }
    el('qr-panel').hidden=!settings.qr;if(!settings.qr)clearImage();
  }
  el('pc').addEventListener('change',()=>{
    clearImage();const id=el('pc').value;if(!id){el('qr-value').value='';el('serial-status').textContent='';return;}
    const report=reports.find(r=>r.device_id===id),serial=typeof report?.serial==='string'?report.serial.trim():'';
    const invalid=!serial||['to be filled by o.e.m.','default string','unknown','none','system serial number','0'].includes(serial.toLowerCase());
    el('qr-value').value=invalid?'':serial;
    el('serial-status').textContent=invalid?'시리얼 확인 전 또는 기본값입니다. 직접 확인해 입력하세요.':'마지막 보고: '+(report.observed_at||'시각 미상')+' · 실제 기기와 대조하세요.';
  });
  el('qr-value').addEventListener('input',clearImage);
  el('qr-form').addEventListener('submit',async event=>{
    event.preventDefault();if(working)return;working=true;for(const check of el('features').querySelectorAll('input'))check.disabled=true;el('generate').disabled=true;clearImage();const value=el('qr-value').value;
    try{
      const response=await fetch('/api/admin/tools/qr',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'X-Duct-Tape-Request':'1','Content-Type':'application/json'},body:JSON.stringify({value}),signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error(response.status===409?'QR 기능이 비활성화됐습니다.':response.status===422?'공백이 아닌 값으로 UTF-8 기준 1024바이트 이내로 입력하세요.':'QR 생성 실패. 관리자 로그인 상태를 확인하세요.');
      const {matrix}=await response.json();if(el('qr-value').value!==value)return;
      const canvas=el('qr-canvas'),scale=Math.max(4,Math.floor(360/matrix.length));canvas.width=canvas.height=matrix.length*scale;
      const context=canvas.getContext('2d');context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);context.fillStyle='#000';
      matrix.forEach((row,y)=>row.forEach((dark,x)=>{if(dark)context.fillRect(x*scale,y*scale,scale,scale);}));
      hasImage=true;el('preview').hidden=false;el('qr-status').textContent='생성 완료 · 입력값만 포함했습니다.';
    }catch(error){el('qr-status').textContent=error.message;}
    finally{working=false;el('generate').disabled=false;showSettings();}
  });
  el('download').addEventListener('click',()=>{
    if(!hasImage)return;el('qr-canvas').toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='duct-tape-qr.png';link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);},'image/png');
  });
  try{
    settings=(await api('/api/admin/features')).features;showSettings();el('message').textContent='관리자 연결됨';
    const [devices,registered]=await Promise.all([api('/api/devices'),api('/api/admin/agents')]);reports=devices.devices;agents=registered.agents;
    for(const agent of agents){const option=document.createElement('option');option.value=agent.device_id;option.textContent=agent.hostname;el('pc').append(option);}
    const requested=new URLSearchParams(location.search).get('device_id');if(agents.some(a=>a.device_id===requested)){el('pc').value=requested;el('pc').dispatchEvent(new Event('change'));}
  }catch(error){el('message').textContent=error.message;}
})();
