import io
import os
import zipfile
import json
import re
from typing import Any
import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from engines.kokoro import KokoroEngine
from engines.nepali_vits import NepaliVITSEngine
from storage import delete_project, list_projects, save_project
from text_normalizer import normalize_text, split_scenes
from audio_processing import process as process_audio, wav_bytes, mp3_bytes, ffmpeg_available
from pronunciation import apply_pronunciations, normalize_dictionary

app = FastAPI(title="Laxman AI Voice API", version="2.6.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "nepali-vits"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=1.5)
    format: str = "wav"
    trim_silence: bool = False
    normalize: bool = True
    fade_in_ms: int = Field(default=0, ge=0, le=3000)
    fade_out_ms: int = Field(default=0, ge=0, le=3000)
    target_dbfs: float = Field(default=-1.0, ge=-12.0, le=-0.1)
    pronunciations: dict[str, str] = Field(default_factory=dict)

class SceneRequest(GenerateRequest):
    scene_id: str = Field(default="scene-001", min_length=1, max_length=80)
    pause_before_ms: int = Field(default=0, ge=0, le=5000)
    pause_after_ms: int = Field(default=0, ge=0, le=5000)

class BatchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    voice: str = "nepali-vits"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    max_chars: int = Field(default=900, ge=200, le=2000)
    silence_ms: int = Field(default=350, ge=0, le=3000)
    preset: str = Field(default="documentary", max_length=40)
    trim_silence: bool = True
    normalize: bool = True
    fade_in_ms: int = Field(default=0, ge=0, le=3000)
    fade_out_ms: int = Field(default=0, ge=0, le=3000)
    target_dbfs: float = Field(default=-1.0, ge=-12.0, le=-0.1)
    export_mp3: bool = False
    pronunciations: dict[str, str] = Field(default_factory=dict)

class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    id: int | None = None

class TTSResult:
    def __init__(self, audio: bytes, media_type: str = "audio/wav"):
        self.audio, self.media_type = audio, media_type

class TTSEngine:
    name = "null"
    def voices(self) -> list[dict[str, Any]]: return []
    def synthesize(self, request: GenerateRequest) -> TTSResult: raise NotImplementedError

class NepaliVITSAdapter(TTSEngine):
    name = "nepali-vits"
    def __init__(self): self.adapter = NepaliVITSEngine()
    def voices(self): return self.adapter.voices()
    def synthesize(self, request): return TTSResult(self.adapter.synthesize(request.text, request.voice, request.speed, request.pitch))

class KokoroAdapter(TTSEngine):
    name = "kokoro-onnx"
    def __init__(self): self.adapter = KokoroEngine(os.getenv("AI_VOICE_KOKORO_MODEL"), os.getenv("AI_VOICE_KOKORO_VOICES"))
    def voices(self): return self.adapter.voices()
    def synthesize(self, request): return TTSResult(self.adapter.synthesize(request.text, request.voice, request.speed, request.pitch))

nepali_engine = NepaliVITSAdapter()
kokoro_engine = KokoroAdapter()

def select_engine(request: GenerateRequest):
    lang = request.language.lower().split("-")[0]
    if lang == "ne" or request.voice.startswith("nepali"): return nepali_engine
    if kokoro_engine.adapter.ready: return kokoro_engine
    raise RuntimeError("Kokoro model is not installed for this language.")

def marker_chunks(text: str):
    pattern = re.compile(r"\[pause\s*:\s*(\d{1,4})\]", re.I)
    tokens=[]; pos=0
    for match in pattern.finditer(text):
        if match.start()>pos: tokens.append(("text", text[pos:match.start()]))
        tokens.append(("pause", int(match.group(1))))
        pos=match.end()
    if pos<len(text): tokens.append(("text", text[pos:]))
    return tokens or [("text", text)]

def strip_emphasis(text: str): return re.sub(r"\[/?emphasis\]", "", text, flags=re.I)

def fmt_time(seconds: float, comma: bool = True) -> str:
    ms=max(0,int(round(seconds*1000))); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"

def timeline_files(timeline):
    srt="\n\n".join(f"{i}\n{fmt_time(a)} --> {fmt_time(b)}\n{s}" for i,(a,b,s) in enumerate(timeline,1))+"\n"
    vtt="WEBVTT\n\n"+"\n\n".join(f"{i}\n{fmt_time(a,False)} --> {fmt_time(b,False)}\n{s}" for i,(a,b,s) in enumerate(timeline,1))+"\n"
    return srt,vtt

def make_silence(sr,ms): return np.zeros(max(0,int(sr*ms/1000)),dtype=np.float32)

def synth_text(text,voice,language,speed,pitch,pronunciations=None):
    cleaned=strip_emphasis(text).strip()
    if not cleaned:return None,None
    cleaned=apply_pronunciations(cleaned,pronunciations)
    request=GenerateRequest(text=cleaned,voice=voice,language=language,speed=speed,pitch=pitch,normalize=False,pronunciations={})
    request.text=normalize_text(cleaned,language.lower().split("-")[0])
    result=select_engine(request).synthesize(request)
    data,sr=sf.read(io.BytesIO(result.audio),dtype="float32",always_2d=False)
    data=np.asarray(data); data=data.mean(axis=1) if data.ndim>1 else data
    return data,sr

def synth_scene(text,voice,language,speed,pitch,trim=False,normalize=True,fade_in_ms=0,fade_out_ms=0,target_dbfs=-1.0,pronunciations=None):
    chunks=[]; sr=None
    for kind,value in marker_chunks(text):
        if kind=="pause":
            if sr is None: continue
            chunks.append(make_silence(sr,value)); continue
        data,chunk_sr=synth_text(value,voice,language,speed,pitch,pronunciations)
        if data is None: continue
        sr=sr or chunk_sr
        if chunk_sr!=sr: raise RuntimeError("Scene sample rates do not match.")
        chunks.append(data)
    if sr is None:return np.zeros(0,dtype=np.float32),22050
    audio=np.concatenate(chunks) if chunks else np.zeros(0,dtype=np.float32)
    return process_audio(audio,sr,trim,normalize,fade_in_ms,fade_out_ms,target_dbfs),sr

@app.get("/health")
def health():
    return {"ok":True,"version":"2.6.0","engines":{"nepali_vits":{"ready":nepali_engine.adapter.ready,"loading":nepali_engine.adapter.loading,"error":nepali_engine.adapter.error},"kokoro":kokoro_engine.adapter.ready},"features":{"tts":True,"projects":True,"batch":True,"scene_generate":True,"audio_processing":True,"trim_silence":True,"loudness_normalization":True,"fade":True,"mp3":ffmpeg_available(),"pause_markers":True,"emphasis_markers":True,"presets":True,"srt":True,"vtt":True,"combined_wav":True,"openai_compatible":True,"pronunciation_dictionary":True,"voice_cloning":False}}

@app.get("/models")
def models():
    return {"models":[{"id":"nepali-vits","type":"tts","language":"ne-NP","license":"MIT","checkpoint":"G_100000.pth","ready":nepali_engine.adapter.ready,"loading":nepali_engine.adapter.loading,"error":nepali_engine.adapter.error},{"id":"kokoro-onnx","type":"tts","languages":["en","fr","it","ja","cmn"],"license":"MIT package / Apache-2.0 model","ready":kokoro_engine.adapter.ready}]}

@app.get("/presets")
def presets():
    return {"presets":[{"id":"documentary","name":"Documentary","speed":0.95,"silence_ms":500},{"id":"news","name":"News","speed":1.08,"silence_ms":280},{"id":"youtube","name":"YouTube","speed":1.0,"silence_ms":350},{"id":"shorts","name":"Shorts / Reels","speed":1.18,"silence_ms":180},{"id":"education","name":"Education","speed":0.92,"silence_ms":450},{"id":"emotional","name":"Emotional","speed":0.88,"silence_ms":550},{"id":"story","name":"Story","speed":0.92,"silence_ms":450}]}

@app.get("/pronunciations")
def pronunciations(): return {"pronunciations":normalize_dictionary(None)}
@app.get("/voices")
def voices(): return {"voices":nepali_engine.voices()+kokoro_engine.voices()}
@app.post("/models/nepali/prepare")
def prepare_nepali(): return nepali_engine.adapter.prepare()

@app.post("/generate")
def generate(request:GenerateRequest):
    if request.format.lower() not in {"wav","wave"}: raise HTTPException(400,"Local output is WAV; use /export/mp3 for MP3.")
    try:
        audio,sr=synth_scene(request.text,request.voice,request.language,request.speed,request.pitch,request.trim_silence,request.normalize,request.fade_in_ms,request.fade_out_ms,request.target_dbfs,request.pronunciations)
        if not len(audio): raise HTTPException(400,"No usable text found.")
        return StreamingResponse(io.BytesIO(wav_bytes(audio,sr)),media_type="audio/wav",headers={"Content-Disposition":"attachment; filename=laxman-ai-voice.wav","X-Audio-Duration":f"{len(audio)/sr:.3f}","X-Sample-Rate":str(sr),"Access-Control-Expose-Headers":"X-Audio-Duration,X-Sample-Rate"})
    except HTTPException: raise
    except (NotImplementedError,RuntimeError) as exc: raise HTTPException(503,str(exc)) from exc

@app.post("/scene/generate")
def scene_generate(request:SceneRequest):
    try: data,sr=synth_scene(request.text,request.voice,request.language,request.speed,request.pitch,request.trim_silence,request.normalize,request.fade_in_ms,request.fade_out_ms,request.target_dbfs,request.pronunciations)
    except (NotImplementedError,RuntimeError) as exc: raise HTTPException(503,str(exc)) from exc
    parts=[]
    if request.pause_before_ms: parts.append(make_silence(sr,request.pause_before_ms))
    parts.append(data)
    if request.pause_after_ms: parts.append(make_silence(sr,request.pause_after_ms))
    audio=np.concatenate(parts) if parts else data
    out=io.BytesIO(wav_bytes(audio,sr)); duration=len(audio)/sr if len(audio) else 0
    return StreamingResponse(out,media_type="audio/wav",headers={"Content-Disposition":f"attachment; filename={request.scene_id}.wav","X-Audio-Duration":f"{duration:.3f}","X-Sample-Rate":str(sr),"Access-Control-Expose-Headers":"X-Audio-Duration,X-Sample-Rate"})

@app.post("/export/mp3")
def export_mp3(request:GenerateRequest):
    if not ffmpeg_available(): raise HTTPException(503,"FFmpeg is not installed; WAV export remains available.")
    try:
        audio,sr=synth_scene(request.text,request.voice,request.language,request.speed,request.pitch,request.trim_silence,request.normalize,request.fade_in_ms,request.fade_out_ms,request.target_dbfs,request.pronunciations)
        return StreamingResponse(io.BytesIO(mp3_bytes(audio,sr)),media_type="audio/mpeg",headers={"Content-Disposition":"attachment; filename=laxman-ai-voice.mp3"})
    except (NotImplementedError,RuntimeError) as exc: raise HTTPException(503,str(exc)) from exc

@app.post("/batch/generate")
def batch_generate(request:BatchRequest):
    presets={"documentary":(.95,500),"news":(1.08,280),"youtube":(1.0,350),"shorts":(1.18,180),"education":(.92,450),"emotional":(.88,550),"story":(.92,450)}
    if request.preset in presets:
        preset_speed,preset_pause=presets[request.preset]
        if request.speed==1.0: request.speed=preset_speed
        if request.silence_ms==350: request.silence_ms=preset_pause
    raw_scenes=split_scenes(normalize_text(request.text,request.language.lower().split("-")[0]),request.max_chars)
    if not raw_scenes: raise HTTPException(400,"No usable text found.")
    if len(raw_scenes)>120: raise HTTPException(400,"Batch limited to 120 scenes per request.")
    generated=[]; timeline=[]; combined=[]; sr=None; elapsed=0.0
    for i,scene in enumerate(raw_scenes,1):
        try: data,scene_sr=synth_scene(scene,request.voice,request.language,request.speed,1.0,request.trim_silence,request.normalize,request.fade_in_ms,request.fade_out_ms,request.target_dbfs,request.pronunciations)
        except (NotImplementedError,RuntimeError) as exc: raise HTTPException(503,str(exc)) from exc
        sr=sr or scene_sr
        if scene_sr!=sr: raise HTTPException(500,"Scene sample rates do not match.")
        duration=len(data)/sr; generated.append((f"scene-{i:03d}.wav",wav_bytes(data,sr))); timeline.append((elapsed,elapsed+duration,scene)); combined.append(data); elapsed+=duration
        if i<len(raw_scenes) and request.silence_ms: combined.append(make_silence(sr,request.silence_ms)); elapsed+=request.silence_ms/1000
    full_audio=np.concatenate(combined); full=wav_bytes(full_audio,sr); srt,vtt=timeline_files(timeline)
    manifest={"version":"2.6","preset":request.preset,"scenes":len(raw_scenes),"silence_ms":request.silence_ms,"language":request.language,"voice":request.voice,"speed":request.speed,"pronunciations":normalize_dictionary(request.pronunciations),"audio_processing":{"trim_silence":request.trim_silence,"normalize":request.normalize,"fade_in_ms":request.fade_in_ms,"fade_out_ms":request.fade_out_ms,"target_dbfs":request.target_dbfs},"total_duration_seconds":round(elapsed,3),"timeline":[{"id":i,"start":round(a,3),"end":round(b,3),"text":s} for i,(a,b,s) in enumerate(timeline,1)]}
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("full-narration.wav",full)
        if request.export_mp3 and ffmpeg_available(): archive.writestr("full-narration.mp3",mp3_bytes(full_audio,sr))
        for filename,audio in generated: archive.writestr(filename,audio)
        archive.writestr("subtitles.srt",srt); archive.writestr("subtitles.vtt",vtt); archive.writestr("scenes.txt","\n\n".join(f"[{i:03d}] {s}" for i,s in enumerate(raw_scenes,1))); archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    out.seek(0); return StreamingResponse(out,media_type="application/zip",headers={"Content-Disposition":"attachment; filename=laxman-ai-voice-creator-batch.zip"})

@app.post("/v1/audio/speech")
def openai_speech(request:GenerateRequest): request.format="wav"; return generate(request)
@app.get("/projects")
def projects(): return {"projects":list_projects()}
@app.post("/projects")
def create_project(request:ProjectRequest): return {"id":save_project(request.name,request.payload,request.id)}
@app.delete("/projects/{project_id}")
def remove_project(project_id:int): delete_project(project_id); return {"ok":True}
@app.get("/batch/status")
def batch_status(): return {"supported":True,"mode":"server-side-scene-queue","max_text_per_job":100000,"max_scenes":120,"outputs":["full-narration.wav","full-narration.mp3 (if FFmpeg)","scene-wavs","subtitles.srt","subtitles.vtt","scenes.txt","manifest.json"]}
@app.post("/clone")
def clone_voice(): raise HTTPException(501,"Voice cloning is disabled until a compatible licensed model and consent workflow are enabled.")
