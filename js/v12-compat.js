(()=>{
  // Bridge the original app's private scene state to the V10/V11/V12 studio modules.
  function sync(){
    const cards=[...document.querySelectorAll('.scene-card')];
    window.scenes=cards.map((card,i)=>{
      const audio=card.querySelector('.scene-audio');
      const text=card.querySelector('.scene-text')?.value||'';
      const speed=+(card.querySelector('.scene-speed')?.value||1);
      const before=+(card.querySelector('.scene-before')?.value||0);
      const after=+(card.querySelector('.scene-after')?.value||0);
      const old=window.scenes?.[i]||{};
      return {id:`scene-${String(i+1).padStart(3,'0')}`,text,url:audio?.src||old.url||null,duration:+(old.duration||audio?.duration||0),speed,before,after};
    });
    window.dispatchEvent(new CustomEvent('ai-voice-scenes-updated'));
  }
  function boot(){
    const host=document.getElementById('sceneTimeline');
    if(host){new MutationObserver(()=>setTimeout(sync,0)).observe(host,{childList:true,subtree:true});}
    document.addEventListener('input',e=>{if(e.target.closest('.scene-card'))setTimeout(sync,0)});
    setTimeout(sync,100);
  }
  document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot):boot();
})();
