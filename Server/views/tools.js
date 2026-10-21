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
  el('admission-year').value=String(new Date().getFullYear());
  function currentInput(){
    const label=el('qr-format').value==='label',name=el('person').value.trim(),year=el('admission-year').value,serial=el('qr-value').value;
    return {label,name,year,serial,value:label?year+'|'+name+'|'+serial:serial};
  }
  for(const id of ['qr-value','person','admission-year'])el(id).addEventListener('input',clearImage);
  el('qr-format').addEventListener('change',()=>{
    const label=el('qr-format').value==='label';el('person').required=label;el('admission-year').required=label;el('year-field').hidden=!label;
    el('format-note').textContent=label?'QR 데이터: 입학년도|이름|S/N. 다운로드 이미지에도 세 항목을 표시합니다.':'입력값만 QR에 담습니다. 이름과 입학년도는 포함하지 않습니다.';clearImage();
  });
  el('qr-form').addEventListener('submit',async event=>{
    event.preventDefault();if(working)return;working=true;for(const check of el('features').querySelectorAll('input'))check.disabled=true;el('generate').disabled=true;clearImage();const input=currentInput(),value=input.value;
    try{
      if(input.label&&(!input.name||!input.serial.trim()||!/^(19|20|21)\d{2}$/.test(input.year)||[input.name,input.serial].some(x=>/[|\r\n]/.test(x))))throw new Error('이름·입학년도·S/N을 확인하세요. 이름과 S/N에는 | 또는 줄바꿈을 사용할 수 없습니다.');
      const response=await fetch('/api/admin/tools/qr',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'X-Duct-Tape-Request':'1','Content-Type':'application/json'},body:JSON.stringify({value}),signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error(response.status===409?'QR 기능이 비활성화됐습니다.':response.status===422?'공백이 아닌 값으로 UTF-8 기준 1024바이트 이내로 입력하세요.':'QR 생성 실패. 관리자 로그인 상태를 확인하세요.');
      const {matrix}=await response.json();if(currentInput().value!==value||currentInput().label!==input.label)return;
      const canvas=el('qr-canvas'),scale=Math.max(4,Math.floor(360/matrix.length)),size=matrix.length*scale;
      const context=canvas.getContext('2d'),lines=[];
      context.font='16px sans-serif';
      if(input.label){
        for(const field of ['이름: '+input.name,'입학년도: '+input.year,'S/N: '+input.serial]){
          let line='';for(const char of field){if(line&&context.measureText(line+char).width>size-24){lines.push(line);line='';}line+=char;}lines.push(line);
        }
      }
      canvas.width=size;canvas.height=size+(lines.length?lines.length*24+16:0);
      context.fillStyle='#fff';context.fillRect(0,0,canvas.width,canvas.height);context.fillStyle='#000';
      matrix.forEach((row,y)=>row.forEach((dark,x)=>{if(dark)context.fillRect(x*scale,y*scale,scale,scale);}));
      context.font='16px sans-serif';context.textBaseline='top';lines.forEach((line,index)=>context.fillText(line,12,size+index*24));
      hasImage=true;el('preview').hidden=false;el('qr-status').textContent=input.label?'생성 완료 · 이름·입학년도·S/N을 QR과 이미지에 포함했습니다.':'생성 완료 · 입력값만 포함했습니다.';
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
