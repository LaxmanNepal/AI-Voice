import io
import os
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from engines.kokoro import KokoroEngine
from storage import delete_project, list_projects, save_project

app = FastAPI(title="Laxman AI Voice API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "af_sarah"
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
    def synthesize(self, request: GenerateRequest) -> TTSResult:
        raise RuntimeError("No neural TTS model is installed. Run scripts/download-kokoro.py and configure the backend.")

class KokoroAdapter(TTSEngine):
    name = "kokoro-onnx"
    def __init__(self):
        self.adapter = KokoroEngine(os.getenv("AI_VOICE_KOKORO_MODEL"), os.getenv("AI_VOICE_KOKORO_VOICES"))
    def voices(self): return self.adapter.voices()
    def synthesize(self, request): return TTSResult(self.adapter.synthesize(request.text, request.voice, request.speed, request.pitch))

def build_engine():
    selected = os.getenv("AI_VOICE_ENGINE", "auto").lower()
    if selected == "null": return NullEngine()
    candidate = KokoroAdapter()
    if selected in {"kokoro", "kokoro-onnx"}: return candidate
    return candidate if candidate.adapter.ready else NullEngine()

engine = build_engine()

@app.get("/health")
def health():
    ready = engine.name != "null" and getattr(getattr(engine, "adapter", None), "ready", False)
    return {"ok": True, "version": "1.0.0", "engine": engine.name, "neural_model_installed": ready, "features": {"tts": ready, "projects": True, "batch": True, "voice_cloning": False}}

@app.get("/voices")
def voices(): return {"engine": engine.name, "voices": engine.voices()}

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.format.lower() not in {"wav", "wave"}: raise HTTPException(400, "Only WAV is currently emitted by the local engine.")
    try: result = engine.synthesize(request)
    except (NotImplementedError, RuntimeError) as exc: raise HTTPException(503, str(exc)) from exc
    return StreamingResponse(io.BytesIO(result.audio), media_type=result.media_type, headers={"Content-Disposition": "attachment; filename=laxman-ai-voice.wav"})

@app.get("/projects")
def projects(): return {"projects": list_projects()}

@app.post("/projects")
def create_project(request: ProjectRequest): return {"id": save_project(request.name, request.payload, request.id)}

@app.delete("/projects/{project_id}")
def remove_project(project_id: int):
    delete_project(project_id)
    return {"ok": True}

@app.get("/batch/status")
def batch_status(): return {"supported": True, "mode": "client-orchestration", "max_text_per_job": 12000}

@app.post("/clone")
def clone_voice():
    raise HTTPException(501, "Voice cloning is intentionally disabled until a compatible, licensed cloning model and consent workflow are added.")
