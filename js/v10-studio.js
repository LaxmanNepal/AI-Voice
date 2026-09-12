(()=>{
  const $=id=>document.getElementById(id);
  const KEY='laxman-ai-voice-v10-state';
  const versions=JSON.parse(localStorage.getItem(KEY)||'[]');
  const scenePrefs={};
  let subtitleRows=[];
  const status=(a,b)=>window.setStatus?.(a,b);

  function addPanel(){
    if($('v10Panel')) return;
    const studio=document.querySelector('.studio');
    if(!studio) return;
    const panel=document.createElement('section');
    panel.id='v10Panel'; panel.className='v10-grid';
    panel.innerHTML=`
      <article class="card v10-card"><div class="card-head"><div><h2>🎙 Scene Voice Lab</h2><p>Give every scene its own voice, speed and pause profile.</p></div><span class="badge">V10</span></div><div id="sceneVoiceLab" class="v10-scene-lab"><div class="tiny">Build a timeline to configure scenes.</div></div></article>
      <article class="card v10-card"><div class="card-head"><div><h2>📝 Subtitle Studio</h2><p>Edit subtitle text and timing before your creator export.</p></div><button id="addSubtitle" class="ghost-btn">Add cue</button></div><div class="subtitle-head"><span>#</span><span>Start</span><span>End</span><span>Subtitle</span><span></span></div><div id="subtitleEditor" class="subtitle-editor"></div><div class="v10-actions"><button id="makeSubtitles" class="ghost-btn">Build from scenes</button><button id="saveVersion" class="ghost-btn">Save version</button><button id="restoreVersion" class="ghost-btn">Restore latest</button></div></article>`;
    studio.after(panel);
    $('addSubtitle').onclick=()=>{subtitleRows.push({start:0,end:3,text:''});renderSubs()};
    $('makeSubtitles').onclick=buildSubs;
    $('saveVersion').onclick=saveVersion;
    $('restoreVersion').onclick=restoreVersion;
  }

  function getScenes(){return Array.isArray(window.scenes)?window.scenes:[]}
  function renderSceneLab(){
    const host=$('sceneVoiceLab'); if(!host)return;
    const scenes=getScenes();
    if(!scenes.length){host.innerHTML='<div class="tiny">Build a timeline to configure scenes.</div>';return}
    host.innerHTML='';
    scenes.forEach((s,i)=>{
      const p=scenePrefs[s.id]||{};
      const row=document.createElement('div'); row.className='v10-scene-row';
      row.innerHTML=`<div class="v10-scene-title"><b>${String(i+1).padStart(2,'0')}</b><span>${(s.text||'').slice(0,90)||'Empty scene'}</span></div><label>Voice<select class="v10-voice"></select></label><label>Speed<input class="v10-speed" type="range" min="0.5" max="2" step="0.05"></label><output class="v10-speed-out"></output><label>Pitch<input class="v10-pitch" type="range" min="0.5" max="1.5" step="0.05"></label><output class="v10-pitch-out"></output>`;
      const vs=row.querySelector('.v10-voice');
      const source=$('voiceSelect');
      [...(source?.options||[])].forEach(o=>{const n=document.createElement('option');n.value=o.value;n.textContent=o.textContent;vs.appendChild(n)});
      vs.value=p.voice||source?.value||'';
      const sp=row.querySelector('.v10-speed'),po=row.querySelector('.v10-pitch'),so=row.querySelector('.v10-speed-out'),oo=row.querySelector('.v10-pitch-out');
      sp.value=p.speed??s.speed??$('speed')?.value??1;po.value=p.pitch??$('pitch')?.value??1;so.textContent=`${(+sp.value).toFixed(2)}×`;oo.textContent=`${(+po.value).toFixed(2)}×`;
      vs.onchange=()=>setPref(s.id,'voice',vs.value);sp.oninput=()=>{setPref(s.id,'speed',+sp.value);so.textContent=`${(+sp.value).toFixed(2)}×`};po.oninput=()=>{setPref(s.id,'pitch',+po.value);oo.textContent=`${(+po.value).toFixed(2)}×`};
      host.appendChild(row);
    });
  }
  function setPref(id,k,v){scenePrefs[id]??={};scenePrefs[id][k]=v;localStorage.setItem(KEY,JSON.stringify({versions,prefs:scenePrefs}))}

  function buildSubs(){
    subtitleRows=[];let t=0;
    getScenes().forEach(s=>{const d=+s.duration||Math.max(1,(s.text||'').length/14);subtitleRows.push({start:t,end:t+d,text:s.text||''});t+=d});
    if(!subtitleRows.length) subtitleRows=[{start:0,end:3,text:$('textInput')?.value||''}];
    renderSubs();status('Subtitle timeline ready',`${subtitleRows.length} editable cues created`)
  }
  function renderSubs(){
    const host=$('subtitleEditor');if(!host)return;host.innerHTML='';
    subtitleRows.forEach((r,i)=>{const row=document.createElement('div');row.className='subtitle-row';row.innerHTML=`<span>${i+1}</span><input class="sub-start" type="number" min="0" step="0.1" value="${r.start}"><input class="sub-end" type="number" min="0" step="0.1" value="${r.end}"><textarea class="sub-text" rows="2">${escapeHtml(r.text)}</textarea><button class="ghost-btn sub-del" type="button">×</button>`;row.querySelector('.sub-start').oninput=e=>r.start=+e.target.value;row.querySelector('.sub-end').oninput=e=>r.end=+e.target.value;row.querySelector('.sub-text').oninput=e=>r.text=e.target.value;row.querySelector('.sub-del').onclick=()=>{subtitleRows.splice(i,1);renderSubs()};host.appendChild(row)})
  }
  function escapeHtml(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}

  function saveVersion(){
    const payload={at:new Date().toISOString(),text:$('textInput')?.value||'',scenes:getScenes().map(s=>({...s,url:null})),subtitles:subtitleRows,prefs:JSON.parse(JSON.stringify(scenePrefs))};
    versions.unshift(payload);versions.splice(12);localStorage.setItem(KEY,JSON.stringify(versions));status('Version saved','Studio snapshot stored locally')
  }
  function restoreVersion(){
    const v=versions[0];if(!v)return status('No saved version','Save a version first');
    if($('textInput'))$('textInput').value=v.text||'';window.scenes=(v.scenes||[]).map(s=>({...s,url:null}));subtitleRows=v.subtitles||[];Object.assign(scenePrefs,v.prefs||{});window.renderTimeline?.();renderSceneLab();renderSubs();window.updateCounter?.();status('Version restored','Latest studio snapshot loaded')
  }

  // Apply scene-specific voice/speed/pitch to /scene/generate without changing V9 generation code.
  const nativeFetch=window.fetch;
  window.fetch=async(...args)=>{
    const [u,o]=args;const url=typeof u==='string'?u:u?.url||'';
    if(o?.body&&typeof o.body==='string'&&url.includes('/scene/generate')){
      try{const b=JSON.parse(o.body),p=scenePrefs[b.scene_id]||{};if(p.voice)b.voice=p.voice;if(p.speed)b.speed=p.speed;if(p.pitch)b.pitch=p.pitch;o.body=JSON.stringify(b)}catch{}
    }
    return nativeFetch(...args)
  };

  function boot(){
    addPanel();
    renderSceneLab();
    const host=$('sceneTimeline');if(host)new MutationObserver(()=>renderSceneLab()).observe(host,{childList:true,subtree:true});
    window.addEventListener('beforeunload',()=>localStorage.setItem(KEY,JSON.stringify({versions,prefs:scenePrefs})))
  }
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot):boot();
})();
