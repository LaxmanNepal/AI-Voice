from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
import io

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Laxman AI Voice API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str = "default"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=1.5)
    format: str = "wav"

class TTSResult:
    def __init__(self, audio: bytes, media_type: str = "audio/wav"):
        self.audio = audio
        self.media_type = media_type

class TTSEngine:
    """Engine interface. Replace NullEngine with a licensed local neural adapter."""
    name = "null"

    def voices(self):
        return []

    def synthesize(self, request: GenerateRequest) -> TTSResult:
        raise NotImplementedError

class NullEngine(TTSEngine):
    name = "null"

    def voices(self):
        return []

    def synthesize(self, request: GenerateRequest) -> TTSResult:
        raise RuntimeError("No neural TTS model is installed. Add a licensed engine adapter in backend/engines.")

engine: TTSEngine = NullEngine()

@app.get("/health")
def health():
    return {"ok": True, "engine": engine.name, "neural_model_installed": engine.name != "null"}

@app.get("/voices")
def voices():
    return {"engine": engine.name, "voices": engine.voices()}

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.format.lower() not in {"wav", "wave"}:
        raise HTTPException(400, "V1 backend output is WAV. MP3 encoding will be added as a separate export stage.")
    try:
        result = engine.synthesize(request)
    except NotImplementedError:
        raise HTTPException(503, "No TTS engine is configured.")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return StreamingResponse(io.BytesIO(result.audio), media_type=result.media_type, headers={"Content-Disposition": "attachment; filename=laxman-ai-voice.wav"})
