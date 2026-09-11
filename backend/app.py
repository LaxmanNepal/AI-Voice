import io
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from engines.kokoro import KokoroEngine

app = FastAPI(title="Laxman AI Voice API", version="0.2.0")
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
    name = "null"
    def voices(self) -> list[dict[str, Any]]:
        return []
    def synthesize(self, request: GenerateRequest) -> TTSResult:
        raise NotImplementedError

class NullEngine(TTSEngine):
    def synthesize(self, request: GenerateRequest) -> TTSResult:
        raise RuntimeError("No neural TTS model is installed. Configure a licensed engine in backend/engines.")

class KokoroAdapter(TTSEngine):
    name = "kokoro-onnx"
    def __init__(self) -> None:
        self.adapter = KokoroEngine(os.getenv("AI_VOICE_KOKORO_MODEL"))
    def voices(self) -> list[dict[str, Any]]:
        return self.adapter.voices()
    def synthesize(self, request: GenerateRequest) -> TTSResult:
        return TTSResult(self.adapter.synthesize(request.text, request.voice, request.speed, request.pitch))

def build_engine() -> TTSEngine:
    selected = os.getenv("AI_VOICE_ENGINE", "auto").lower()
    if selected in {"kokoro", "kokoro-onnx"}:
        return KokoroAdapter()
    if selected == "null":
        return NullEngine()
    candidate = KokoroAdapter()
    return candidate if candidate.adapter.ready else NullEngine()

engine = build_engine()

@app.get("/health")
def health():
    return {"ok": True, "engine": engine.name, "neural_model_installed": engine.name != "null" and getattr(getattr(engine, "adapter", None), "ready", False)}

@app.get("/voices")
def voices():
    return {"engine": engine.name, "voices": engine.voices()}

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.format.lower() not in {"wav", "wave"}:
        raise HTTPException(400, "V1 backend output is WAV. MP3 encoding will be added as a separate export stage.")
    try:
        result = engine.synthesize(request)
    except (NotImplementedError, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    return StreamingResponse(io.BytesIO(result.audio), media_type=result.media_type, headers={"Content-Disposition": "attachment; filename=laxman-ai-voice.wav"})
