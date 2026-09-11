"""Kokoro ONNX engine used for local, offline neural speech generation."""
from __future__ import annotations

import io
from pathlib import Path

KOKORO_AVAILABLE = False
try:
    import soundfile as sf
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    Kokoro = None
    sf = None

VOICE_CATALOG = [
    ("af_sarah", "Sarah", "en-us"), ("af_bella", "Bella", "en-us"),
    ("af_nicole", "Nicole", "en-us"), ("af_sky", "Sky", "en-us"),
    ("am_adam", "Adam", "en-us"), ("am_michael", "Michael", "en-us"),
    ("bf_emma", "Emma", "en-gb"), ("bf_isabella", "Isabella", "en-gb"),
    ("bm_george", "George", "en-gb"), ("bm_lewis", "Lewis", "en-gb"),
    ("ff_siwis", "Siwis", "fr-fr"), ("if_sara", "Sara", "it"),
    ("im_nicola", "Nicola", "it"), ("jf_alpha", "Alpha", "ja"),
    ("jf_gongitsune", "Gongitsune", "ja"), ("zf_xiaobei", "Xiaobei", "cmn"),
    ("zf_xiaoni", "Xiaoni", "cmn"), ("zm_yunjian", "Yunjian", "cmn"),
]

LANGS = {"en-us": "en-us", "en-gb": "en-gb", "fr-fr": "fr-fr", "it": "it", "ja": "ja", "cmn": "cmn"}

class KokoroEngine:
    engine_id = "kokoro-onnx"

    def __init__(self, model_path: str | None = None, voices_path: str | None = None):
        self.model_path = Path(model_path) if model_path else Path("models/kokoro-v1.0.onnx")
        self.voices_path = Path(voices_path) if voices_path else Path("models/voices-v1.0.bin")
        self.engine = None
        if KOKORO_AVAILABLE and self.model_path.exists() and self.voices_path.exists():
            self.engine = Kokoro(str(self.model_path), str(self.voices_path))

    @property
    def ready(self) -> bool:
        return self.engine is not None

    def voices(self) -> list[dict]:
        return [{"id": i, "name": n, "language": l, "engine": self.engine_id} for i, n, l in VOICE_CATALOG]

    def synthesize(self, text: str, voice: str, speed: float, pitch: float) -> bytes:
        if not self.ready:
            raise RuntimeError("Kokoro model files are missing. Run scripts/download-kokoro.py first.")
        item = next((x for x in VOICE_CATALOG if x[0] == voice), VOICE_CATALOG[0])
        samples, sample_rate = self.engine.create(text, voice=item[0], speed=speed, lang=LANGS[item[2]])
        out = io.BytesIO()
        sf.write(out, samples, sample_rate, format="WAV")
        return out.getvalue()
