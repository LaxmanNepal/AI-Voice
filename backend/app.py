import io
import os
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from engines.kokoro import KokoroEngine
from engines.nepali_vits import NepaliVITSEngine
from storage import delete_project, list_projects, save_project

app = FastAPI(title="Laxman AI Voice API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "nepali-vits-female"
    language: str = "ne"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=1.5)
    format: str = "wav"

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

class NullEngine(TTSEngine):
    def synthesize(self, request):
        raise RuntimeError("No neural TTS engine is ready. Start the backend and allow the model to download on first use.")

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

def build_default_engine():
    selected = os.getenv("AI_VOICE_ENGINE", "nepali").lower()
    if selected in {"nepali", "nepali-vits", "auto"} and nepali_engine.adapter.ready:
        return nepali_engine
    if selected in {"kokoro", "kokoro-onnx", "auto"} and kokoro_engine.adapter.ready:
        return kokoro_engine
    return NullEngine()


def select_engine(request: GenerateRequest):
    lang = request.language.lower().split("-")[0]
    if lang == "ne" or request.voice.startswith("nepali-"):
        if nepali_engine.adapter.ready: return nepali_engine
        raise RuntimeError(nepali_engine.adapter.error or "Nepali VITS model is not ready")
    if kokoro_engine.adapter.ready: return kokoro_engine
    raise RuntimeError("No compatible multilingual engine is ready")

@app.get("/health")
def health():
    return {"ok": True, "version": "2.0.0", "engines": {"nepali_vits": nepali_engine.adapter.ready, "kokoro": kokoro_engine.adapter.ready}, "features": {"tts": nepali_engine.adapter.ready or kokoro_engine.adapter.ready, "projects": True, "batch": True, "openai_compatible": True, "voice_cloning": False}}

@app.get("/voices")
def voices():
    return {"voices": nepali_engine.voices() + kokoro_engine.voices()}

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.format.lower() not in {"wav", "wave"}: raise HTTPException(400, "Local V1/V2 output is WAV.")
    try: result = select_engine(request).synthesize(request)
    except (NotImplementedError, RuntimeError) as exc: raise HTTPException(503, str(exc)) from exc
    return StreamingResponse(io.BytesIO(result.audio), media_type=result.media_type, headers={"Content-Disposition": "attachment; filename=laxman-ai-voice.wav"})

# OpenAI-compatible local endpoint: existing TTS clients can point to this server.
@app.post("/v1/audio/speech")
def openai_speech(request: GenerateRequest):
    request.format = "wav"
    return generate(request)

@app.get("/projects")
def projects(): return {"projects": list_projects()}

@app.post("/projects")
def create_project(request: ProjectRequest): return {"id": save_project(request.name, request.payload, request.id)}

@app.delete("/projects/{project_id}")
def remove_project(project_id: int):
    delete_project(project_id)
    return {"ok": True}

@app.get("/batch/status")
def batch_status(): return {"supported": True, "mode": "local-project-orchestration", "max_text_per_job": 12000}

@app.post("/clone")
def clone_voice():
    raise HTTPException(501, "Voice cloning is disabled until a compatible licensed model and consent workflow are enabled.")
