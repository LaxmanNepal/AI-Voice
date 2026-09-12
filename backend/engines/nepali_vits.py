"""Real Nepali VITS inference adapter.

Model: Dragneel/nepali-vits-tts (MIT). G_100000.pth is the recommended
checkpoint in its model card. We download it at runtime; no weights are stored
in this repository.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download

MODEL_ID = os.getenv("AI_VOICE_NEPALI_MODEL", "Dragneel/nepali-vits-tts")
CHECKPOINT = os.getenv("AI_VOICE_NEPALI_CHECKPOINT", "G_100000.pth")

class NepaliVITSEngine:
    name = "nepali-vits"

    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parent.parent / "models" / "nepali-vits-runtime"
        self.vits_dir = self.root / "vits"
        self.net_g = None
        self.hps = None
        self.text_to_sequence = None
        self.ready = False
        self.error = None
        self._load()

    def _load(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if not self.vits_dir.exists():
                subprocess.run(["git", "clone", "--depth", "1", "https://github.com/jaywalnut310/vits", str(self.vits_dir)], check=True)
                subprocess.run([sys.executable, "-m", "pip", "install", "cython", "librosa", "unidecode"], check=True)
                subprocess.run([sys.executable, "setup.py", "build_ext", "--inplace"], cwd=str(self.vits_dir / "monotonic_align"), check=True)

            config = hf_hub_download(MODEL_ID, "nepali_base.json", local_dir=str(self.root))
            symbols = hf_hub_download(MODEL_ID, "nepali_symbols.py", local_dir=str(self.root))
            cleaners = hf_hub_download(MODEL_ID, "nepali_cleaners.py", local_dir=str(self.root))
            checkpoint = hf_hub_download(MODEL_ID, CHECKPOINT, local_dir=str(self.root))
            text_dir = self.vits_dir / "text"
            config_dir = self.vits_dir / "configs"
            text_dir.mkdir(exist_ok=True)
            config_dir.mkdir(exist_ok=True)
            (text_dir / "symbols.py").write_bytes(Path(symbols).read_bytes())
            (text_dir / "cleaners.py").write_bytes(Path(cleaners).read_bytes())
            (config_dir / "nepali_base.json").write_bytes(Path(config).read_bytes())

            sys.path.insert(0, str(self.vits_dir))
            import commons
            import utils
            from models import SynthesizerTrn
            from text import text_to_sequence, symbols
            self._commons = commons
            self.text_to_sequence = text_to_sequence
            self.hps = utils.get_hparams_from_file(str(config))
            self.net_g = SynthesizerTrn(len(symbols), self.hps.data.filter_length // 2 + 1, self.hps.train.segment_size // self.hps.data.hop_length, **self.hps.model)
            self.net_g.eval()
            utils.load_checkpoint(checkpoint, self.net_g, None)
            self.ready = True
        except Exception as exc:
            self.error = str(exc)

    def voices(self) -> list[dict]:
        if not self.ready:
            return []
        return [{"id":"nepali-vits-female","name":"Nepali Natural","language":"ne-NP","gender":"female","engine":self.name,"quality":"natural"}]

    def synthesize(self, text: str, voice: str, speed: float, pitch: float) -> bytes:
        if not self.ready:
            raise RuntimeError(f"Nepali VITS unavailable: {self.error or 'model not loaded'}")
        text = unicodedata.normalize("NFC", text.strip())
        sequence = self.text_to_sequence(text, self.hps.data.text_cleaners)
        sequence = self._commons.intersperse(sequence, 0)
        x = torch.LongTensor(sequence).unsqueeze(0)
        xl = torch.LongTensor([len(sequence)])
        with torch.no_grad():
            audio = self.net_g.infer(x, xl, noise_scale=0.667, noise_scale_w=0.8, length_scale=max(0.5, min(2.0, 1.0 / speed)))[0][0, 0].cpu().numpy()
        out = io.BytesIO()
        sf.write(out, np.asarray(audio), self.hps.data.sampling_rate, format="WAV")
        return out.getvalue()
