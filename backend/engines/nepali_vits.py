"""Nepali VITS adapter using an MIT-licensed Hugging Face checkpoint.

Default model: Dragneel/nepali-vits-tts.
The model is downloaded at runtime rather than committed to Git.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import torch

MODEL_ID = os.getenv("AI_VOICE_NEPALI_MODEL", "Dragneel/nepali-vits-tts")
CHECKPOINT = os.getenv("AI_VOICE_NEPALI_CHECKPOINT", "G_100000.pth")

class NepaliVITSEngine:
    name = "nepali-vits"

    def __init__(self) -> None:
        self.model = None
        self.config = None
        self.ready = False
        self.error = None
        self._load()

    def _load(self) -> None:
        try:
            from huggingface_hub import hf_hub_download
            root = Path(__file__).resolve().parent.parent / "models" / "nepali-vits"
            root.mkdir(parents=True, exist_ok=True)
            ckpt = hf_hub_download(MODEL_ID, CHECKPOINT, local_dir=root)
            config = hf_hub_download(MODEL_ID, "nepali_base.json", local_dir=root)
            sys.path.insert(0, str(root))
            from infer_vits1 import VITS  # type: ignore
            self.model = VITS(config, ckpt)
            self.ready = True
        except Exception as exc:
            self.error = str(exc)

    def voices(self) -> list[dict]:
        return [{"id":"nepali-vits-kathmandu","name":"Nepali Natural","language":"ne-NP","gender":"female","engine":self.name}] if self.ready else []

    def synthesize(self, text: str, voice: str, speed: float, pitch: float) -> bytes:
        if not self.ready:
            raise RuntimeError(f"Nepali VITS unavailable: {self.error or 'model not loaded'}")
        # The upstream inference implementation owns text normalization and
        # waveform generation; this adapter keeps the HTTP contract stable.
        audio = self.model.infer(text, speed=speed)
        import io, soundfile as sf
        out = io.BytesIO()
        sf.write(out, audio, 22050, format="WAV")
        return out.getvalue()
