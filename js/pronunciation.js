(() => {
  const KEY='laxman-ai-voice-pronunciations-v1';
  const defaults={AI:'ए आई',API:'ए पी आई',YouTube:'युट्युब',Facebook:'फेसबुक',TikTok:'टिकटक',Google:'गुगल',ChatGPT:'च्याट जीपीटी',OpenAI:'ओपन एआई',KWD:'कुवेती दिनार',NPR:'नेपाली रुपैयाँ'};
  let dictionary={...defaults,...JSON.parse(localStorage.getItem(KEY)||'{}')};
  const $=id=>document.getElementById(id);
  function save(){localStorage.setItem(KEY,JSON.stringify(dictionary));render()}
  function render(){const host=$('pronunciationList');if(!host)return;host.innerHTML='';Object.entries(dictionary).forEach(([from,to])=>{const row=document.createElement('div');row.className='pron-row';row.innerHTML=`<span>${from}</span><b>→</b><span>${to}</span><button type="button" class="ghost-btn">×</button>`;row.querySelector('button').onclick=()=>{delete dictionary[from];save()};host.appendChild(row)})}
  function add(){const from=$('pronFrom').value.trim(),to=$('pronTo').value.trim();if(!from||!to)return;dictionary[from]=to;$('pronFrom').value='';$('pronTo').value='';save()}
  const originalFetch=window.fetch;
  window.fetch=async(...args)=>{
    const input=args[0],init=args[1]||{};const url=typeof input==='string'?input:(input?.url||'');
    if(init.body&&typeof init.body==='string'&&/\/(generate|scene\/generate|export\/mp3|batch\/generate)$/.test(url)){
      try{const body=JSON.parse(init.body);body.pronunciations=dictionary;init.body=JSON.stringify(body);args[1]=init}catch{}
    }
    return originalFetch(...args);
  };
  document.addEventListener('DOMContentLoaded',()=>{render();$('addPronunciation')?.addEventListener('click',add);$('clearPronunciations')?.addEventListener('click',()=>{dictionary={};save()});});
})();
