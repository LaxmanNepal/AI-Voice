"""Optional Kokoro ONNX adapter.

The adapter is intentionally optional: importing the backend does not require
model packages or model weights. Install the optional dependencies and provide
an explicitly licensed model before enabling it.
"""
from __future__ import annotations

import io
import wave
from pathlib import Path

KOKORO_AVAILABLE = False

try:
    import numpy as np  # type: ignore
    import onnxruntime as ort  # type: ignore
    KOKORO_AVAILABLE = True
except ImportError:
    np = None
    ort = None


class KokoroEngine:
    """Thin ONNX runtime adapter boundary for Kokoro-compatible models.

    Model-specific tokenization/voice handling belongs here rather than in the
    FastAPI routes, making future model replacement straightforward.
    """

    engine_id = "kokoro-onnx"

    def __init__(self, model_path: str | None = None):
        self.model_path = Path(model_path) if model_path else None
        self.session = None
        if KOKORO_AVAILABLE and self.model_path and self.model_path.exists():
            self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])

    @property
    def ready(self) -> bool:
        return self.session is not None

    def voices(self) -> list[dict]:
        return []

    def synthesize(self, text: str, voice: str, speed: float, pitch: float) -> bytes:
        if not self.ready:
            raise RuntimeError("Kokoro model is not installed or configured.")
        raise NotImplementedError(
            "The model-specific Kokoro tokenizer/vocoder adapter must be configured "
            "for the selected model package before synthesis is enabled."
        )


def pcm16_wav(samples: "np.ndarray", sample_rate: int) -> bytes:
    """Utility for adapters that return mono float PCM samples."""
    if np is None:
        raise RuntimeError("numpy is required for PCM conversion")
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return out.getvalue()
