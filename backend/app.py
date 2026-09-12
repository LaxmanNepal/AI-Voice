import io
import os
import zipfile
import json
from typing import Any
import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from engines.kokoro import KokoroEngine
from engines.nepali_vits import NepaliVITSEngine
from storage import delete_project, list_projects, save_project
from text_normalizer import normalize_text, split_scenes

app = FastAPI(title="Laxman AI Voice API", version="2.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "nepali-vits"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=1.5)
    format: str = "wav"

class SceneRequest(GenerateRequest):
    scene_id: str = Field(default="scene-001", min_length=1, max_length=80)

class BatchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    voice: str = "nepali-vits"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    max_chars: int = Field(default=900, ge=200, le=2000)
    silence_ms: int = Field(default=350, ge=0, le=3000)

class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    payload: dict = {}
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
    if lang == "ne" or request.voice.startswith("nepali"):
        return nepali_engine
    if kokoro_engine.adapter.ready: return kokoro_engine
    raise RuntimeError("Kokoro model is not installed for this language.")

def fmt_srt_time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def fmt_vtt_time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def timeline_files(timeline):
    srt = "\n\n".join(f"{i}\n{fmt_srt_time(start)} --> {fmt_srt_time(end)}\n{scene}" for i,(start,end,scene) in enumerate(timeline,1)) + "\n"
    vtt = "WEBVTT\n\n" + "\n\n".join(f"{i}\n{fmt_vtt_time(start)} --> {fmt_vtt_time(end)}\n{scene}" for i,(start,end,scene) in enumerate(timeline,1)) + "\n"
    return srt, vtt

@app.get("/health")
def health():
    return {"ok": True, "version": "2.3.0", "engines": {"nepali_vits": {"ready": nepali_engine.adapter.ready, "loading": nepali_engine.adapter.loading, "error": nepali_engine.adapter.error}, "kokoro": kokoro_engine.adapter.ready}, "features": {"tts": True, "projects": True, "batch": True, "scene_generate": True, "srt": True, "vtt": True, "combined_wav": True, "openai_compatible": True, "voice_cloning": False}}

@app.get("/models")
def models():
    return {"models": [{"id":"nepali-vits","type":"tts","language":"ne-NP","license":"MIT","checkpoint":"G_100000.pth","ready":nepali_engine.adapter.ready,"loading":nepali_engine.adapter.loading,"error":nepali_engine.adapter.error},{"id":"kokoro-onnx","type":"tts","languages":["en","fr","it","ja","cmn"],"license":"MIT package / Apache-2.0 model","ready":kokoro_engine.adapter.ready}]}

@app.post("/models/nepali/prepare")
def prepare_nepali(): return nepali_engine.adapter.prepare()

@app.get("/voices")
def voices(): return {"voices": nepali_engine.voices() + kokoro_engine.voices()}

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.format.lower() not in {"wav", "wave"}: raise HTTPException(400, "Local output is WAV.")
    request.text = normalize_text(request.text, request.language.lower().split("-")[0])
    try: result = select_engine(request).synthesize(request)
    except (NotImplementedError, RuntimeError) as exc: raise HTTPException(503, str(exc)) from exc
    return StreamingResponse(io.BytesIO(result.audio), media_type=result.media_type, headers={"Content-Disposition": "attachment; filename=laxman-ai-voice.wav"})

@app.post("/scene/generate")
def scene_generate(request: SceneRequest):
    request.text = normalize_text(request.text, request.language.lower().split("-")[0])
    if not request.text: raise HTTPException(400, "Scene has no usable text.")
    try: result = select_engine(request).synthesize(request)
    except (NotImplementedError, RuntimeError) as exc: raise HTTPException(503, str(exc)) from exc
    data, sr = sf.read(io.BytesIO(result.audio), dtype="float32", always_2d=False)
    duration = len(data) / sr if len(data) else 0
    return StreamingResponse(io.BytesIO(result.audio), media_type="audio/wav", headers={"Content-Disposition": f"attachment; filename={request.scene_id}.wav", "X-Audio-Duration": f"{duration:.3f}", "X-Sample-Rate": str(sr), "Access-Control-Expose-Headers": "X-Audio-Duration,X-Sample-Rate"})

@app.post("/batch/generate")
def batch_generate(request: BatchRequest):
    scenes = split_scenes(normalize_text(request.text, request.language.lower().split("-")[0]), request.max_chars)
    if not scenes: raise HTTPException(400, "No usable text found.")
    if len(scenes) > 120: raise HTTPException(400, "Batch limited to 120 scenes per request.")
    generated: list[tuple[str, bytes]] = []
    timeline: list[tuple[float,float,str]] = []
    combined_parts=[]; sample_rate=None; elapsed=0.0
    for i, scene in enumerate(scenes, 1):
        single=GenerateRequest(text=scene, voice=request.voice, language=request.language, speed=request.speed)
        try: audio=select_engine(single).synthesize(single).audio
        except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
        generated.append((f"scene-{i:03d}.wav", audio))
        data, sr=sf.read(io.BytesIO(audio), dtype="float32", always_2d=False); data=np.asarray(data)
        if data.ndim>1: data=data.mean(axis=1)
        sample_rate=sample_rate or sr; duration=len(data)/sr
        timeline.append((elapsed, elapsed+duration, scene)); combined_parts.append(data); elapsed += duration
        if i < len(scenes) and request.silence_ms:
            combined_parts.append(np.zeros(int(sr*request.silence_ms/1000),dtype=np.float32)); elapsed += request.silence_ms/1000
    full=io.BytesIO(); sf.write(full,np.concatenate(combined_parts),sample_rate,format="WAV"); full.seek(0)
    srt, vtt = timeline_files(timeline)
    scenes_txt="\n\n".join(f"[{i:03d}] {s}" for i,s in enumerate(scenes,1))
    manifest={"version":"2.3","scenes":len(scenes),"silence_ms":request.silence_ms,"language":request.language,"voice":request.voice,"total_duration_seconds":round(elapsed,3),"timeline":[{"id":i,"start":round(a,3),"end":round(b,3),"text":s} for i,(a,b,s) in enumerate(timeline,1)]}
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("full-narration.wav",full.getvalue())
        for filename,audio in generated: archive.writestr(filename,audio)
        archive.writestr("subtitles.srt",srt); archive.writestr("subtitles.vtt",vtt); archive.writestr("scenes.txt",scenes_txt); archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    out.seek(0)
    return StreamingResponse(out,media_type="application/zip",headers={"Content-Disposition":"attachment; filename=laxman-ai-voice-creator-batch.zip"})

@app.post("/v1/audio/speech")
def openai_speech(request: GenerateRequest): request.format="wav"; return generate(request)
@app.get("/projects")
def projects(): return {"projects": list_projects()}
@app.post("/projects")
def create_project(request: ProjectRequest): return {"id": save_project(request.name, request.payload, request.id)}
@app.delete("/projects/{project_id}")
def remove_project(project_id: int): delete_project(project_id); return {"ok": True}
@app.get("/batch/status")
def batch_status(): return {"supported": True, "mode": "server-side-scene-queue", "max_text_per_job": 100000, "max_scenes": 120, "outputs":["full-narration.wav","scene-wavs","subtitles.srt","subtitles.vtt","scenes.txt","manifest.json"]}
@app.post("/clone")
def clone_voice(): raise HTTPException(501, "Voice cloning is disabled until a compatible licensed model and consent workflow are enabled.")
