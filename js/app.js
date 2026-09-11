const API_BASE = window.AI_VOICE_API || 'http://127.0.0.1:8000';
const $ = (id) => document.getElementById(id);
const textInput=$('textInput'), voiceSelect=$('voiceSelect'), engineSelect=$('engineSelect'), speed=$('speed'), pitch=$('pitch');
let voices=[]; let currentAudioUrl=null;

function setStatus(title, text){$('statusTitle').textContent=title;$('statusText').textContent=text}
function updateCounter(){ $('counter').textContent=`${textInput.value.length.toLocaleString()} / 12,000`; }
function browserVoices(){
  voices=speechSynthesis.getVoices().map((v,i)=>({id:`browser-${i}`,name:v.name,language:v.lang,local:true,voice:v}));
  voiceSelect.innerHTML='';
  voices.forEach(v=>{const o=document.createElement('option');o.value=v.id;o.textContent=`${v.name} · ${v.language}`;voiceSelect.appendChild(o)});
  if(!voices.length){const o=document.createElement('option');o.value='browser-default';o.textContent='Browser default';voiceSelect.appendChild(o)}
}
async function localVoices(){
  try{const r=await fetch(`${API_BASE}/voices`,{signal:AbortSignal.timeout(1200)});if(!r.ok)throw Error();const data=await r.json();return data.voices||[];}catch{return null}
}
async function detect(){
  const local=await localVoices();
  if(local?.length){
    voices=local;voiceSelect.innerHTML='';local.forEach(v=>{const o=document.createElement('option');o.value=v.id;o.textContent=`${v.name} · ${v.language}`;voiceSelect.appendChild(o)});
    $('engineBadge').textContent='Local neural engine';setStatus('Local engine ready','FastAPI TTS endpoint detected');return;
  }
  browserVoices();$('engineBadge').textContent='Browser fallback';setStatus('Ready','Browser speech available');
}
async function generate(){
  const text=textInput.value.trim();if(!text)return setStatus('Nothing to generate','Enter some text first');
  const requested=engineSelect.value;
  if(requested!=='browser'){
    try{
      setStatus('Generating…','Sending text to local neural engine');
      const r=await fetch(`${API_BASE}/generate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,voice:voiceSelect.value,speed:+speed.value,pitch:+pitch.value,format:'wav'})});
      if(!r.ok)throw Error();const blob=await r.blob();
      currentAudioUrl=URL.createObjectURL(blob);$('audioPlayer').src=currentAudioUrl;$('downloadBtn').disabled=false;$('outputMeta').textContent=`Generated WAV · ${(blob.size/1024).toFixed(1)} KB`;$('engineBadge').textContent='Local neural engine';setStatus('Generated','Audio is ready');return;
    }catch(e){if(requested==='local'){setStatus('Local engine unavailable','Start backend/app.py and try again');return}}
  }
  const utterance=new SpeechSynthesisUtterance(text);
  const selected=voices.find(v=>v.id===voiceSelect.value);if(selected?.voice)utterance.voice=selected.voice;
  utterance.rate=+speed.value;utterance.pitch=+pitch.value;
  utterance.onstart=()=>setStatus('Speaking…','Browser SpeechSynthesis');utterance.onend=()=>setStatus('Ready','Speech finished');utterance.onerror=()=>setStatus('Speech error','Try another browser voice');
  speechSynthesis.cancel();speechSynthesis.speak(utterance);$('outputMeta').textContent='Browser speech · download is unavailable in fallback mode';$('downloadBtn').disabled=true;
}
textInput.addEventListener('input',updateCounter);$('clearBtn').onclick=()=>{textInput.value='';updateCounter();};$('sampleBtn').onclick=()=>{textInput.value='Namaste everyone. Welcome to Laxman AI Voice. This is a local-first text to speech studio built with open technology.';updateCounter()};$('generateBtn').onclick=generate;
speed.oninput=()=>$('speedOut').textContent=`${(+speed.value).toFixed(2)}×`;pitch.oninput=()=>$('pitchOut').textContent=`${(+pitch.value).toFixed(2)}×`;
$('downloadBtn').onclick=()=>{if(!currentAudioUrl)return;const a=document.createElement('a');a.href=currentAudioUrl;a.download='laxman-ai-voice.wav';a.click()};
$('themeBtn').onclick=()=>document.documentElement.classList.toggle('light');
speechSynthesis.onvoiceschanged=browserVoices;updateCounter();browserVoices();detect();
