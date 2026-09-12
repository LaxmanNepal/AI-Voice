import io
import os
import zipfile
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from engines.kokoro import KokoroEngine
from engines.nepali_vits import NepaliVITSEngine
from storage import delete_project, list_projects, save_project
from text_normalizer import normalize_text, split_scenes

app = FastAPI(title="Laxman AI Voice API", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "nepali-vits"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=1.5)
    format: str = "wav"

class BatchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    voice: str = "nepali-vits"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    max_chars: int = Field(default=900, ge=200, le=2000)

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

@app.get("/health")
def health():
    return {"ok": True, "version": "2.1.0", "engines": {"nepali_vits": {"ready": nepali_engine.adapter.ready, "loading": nepali_engine.adapter.loading, "error": nepali_engine.adapter.error}, "kokoro": kokoro_engine.adapter.ready}, "features": {"tts": True, "projects": True, "batch": True, "openai_compatible": True, "voice_cloning": False}}

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

@app.post("/batch/generate")
def batch_generate(request: BatchRequest):
    scenes = split_scenes(normalize_text(request.text, request.language.lower().split("-")[0]), request.max_chars)
    if not scenes: raise HTTPException(400, "No usable text found.")
    if len(scenes) > 120: raise HTTPException(400, "Batch limited to 120 scenes per request.")
    generated = []
    for i, scene in enumerate(scenes, 1):
        single = GenerateRequest(text=scene, voice=request.voice, language=request.language, speed=request.speed)
        try: audio = select_engine(single).synthesize(single).audio
        except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
        generated.append((f"scene-{i:03d}.wav", audio))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, audio in generated: archive.writestr(filename, audio)
        archive.writestr("scenes.txt", "\n\n".join(f"[{i:03d}] {s}" for i, s in enumerate(scenes, 1)))
    out.seek(0)
    return StreamingResponse(out, media_type="application/zip", headers={"Content-Disposition":"attachment; filename=laxman-ai-voice-batch.zip"})

@app.post("/v1/audio/speech")
def openai_speech(request: GenerateRequest):
    request.format = "wav"; return generate(request)

@app.get("/projects")
def projects(): return {"projects": list_projects()}
@app.post("/projects")
def create_project(request: ProjectRequest): return {"id": save_project(request.name, request.payload, request.id)}
@app.delete("/projects/{project_id}")
def remove_project(project_id: int): delete_project(project_id); return {"ok": True}
@app.get("/batch/status")
def batch_status(): return {"supported": True, "mode": "server-side-scene-queue", "max_text_per_job": 100000, "max_scenes": 120}
@app.post("/clone")
def clone_voice(): raise HTTPException(501, "Voice cloning is disabled until a compatible licensed model and consent workflow are enabled.")
