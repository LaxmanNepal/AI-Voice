"""Real Nepali VITS inference adapter with lazy model loading."""
from __future__ import annotations
import io, os, subprocess, sys, unicodedata
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from text_normalizer import normalize_text

MODEL_ID = os.getenv("AI_VOICE_NEPALI_MODEL", "Dragneel/nepali-vits-tts")
CHECKPOINT = os.getenv("AI_VOICE_NEPALI_CHECKPOINT", "G_100000.pth")

class NepaliVITSEngine:
    name = "nepali-vits"
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parent.parent / "models" / "nepali-vits-runtime"
        self.vits_dir = self.root / "vits"
        self.net_g = None; self.hps = None; self.text_to_sequence = None
        self.ready = False; self.loading = False; self.error = None

    def load(self) -> bool:
        if self.ready: return True
        if self.loading: return False
        self.loading = True; self.error = None
        try:
            self._load()
            return self.ready
        except Exception as exc:
            self.error = str(exc); self.ready = False; return False
        finally:
            self.loading = False

    def _load(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.vits_dir.exists():
            subprocess.run(["git", "clone", "--depth", "1", "https://github.com/jaywalnut310/vits", str(self.vits_dir)], check=True)
            subprocess.run([sys.executable, "-m", "pip", "install", "cython", "librosa", "unidecode"], check=True)
            subprocess.run([sys.executable, "setup.py", "build_ext", "--inplace"], cwd=str(self.vits_dir / "monotonic_align"), check=True)
        config = hf_hub_download(MODEL_ID, "nepali_base.json", local_dir=str(self.root))
        symbols = hf_hub_download(MODEL_ID, "nepali_symbols.py", local_dir=str(self.root))
        cleaners = hf_hub_download(MODEL_ID, "nepali_cleaners.py", local_dir=str(self.root))
        checkpoint = hf_hub_download(MODEL_ID, CHECKPOINT, local_dir=str(self.root))
        text_dir, config_dir = self.vits_dir / "text", self.vits_dir / "configs"
        text_dir.mkdir(exist_ok=True); config_dir.mkdir(exist_ok=True)
        (text_dir / "symbols.py").write_bytes(Path(symbols).read_bytes())
        (text_dir / "cleaners.py").write_bytes(Path(cleaners).read_bytes())
        (config_dir / "nepali_base.json").write_bytes(Path(config).read_bytes())
        if str(self.vits_dir) not in sys.path: sys.path.insert(0, str(self.vits_dir))
        import commons, utils
        from models import SynthesizerTrn
        from text import text_to_sequence, symbols
        self._commons = commons; self.text_to_sequence = text_to_sequence
        self.hps = utils.get_hparams_from_file(str(config))
        self.net_g = SynthesizerTrn(len(symbols), self.hps.data.filter_length // 2 + 1, self.hps.train.segment_size // self.hps.data.hop_length, **self.hps.model)
        self.net_g.eval(); utils.load_checkpoint(checkpoint, self.net_g, None); self.ready = True

    def prepare(self) -> dict:
        ok = self.load()
        return {"ready": ok, "loading": self.loading, "error": self.error, "model": MODEL_ID, "checkpoint": CHECKPOINT}

    def voices(self) -> list[dict]:
        return [{"id":"nepali-vits","name":"Nepali Natural","language":"ne-NP","gender":"female","engine":self.name,"quality":"natural","installed":self.ready}]

    def synthesize(self, text: str, voice: str, speed: float, pitch: float) -> bytes:
        if not self.load(): raise RuntimeError(f"Nepali VITS unavailable: {self.error or 'model is still loading'}")
        text = normalize_text(text, "ne")
        sequence = self.text_to_sequence(text, self.hps.data.text_cleaners)
        sequence = self._commons.intersperse(sequence, 0)
        x = torch.LongTensor(sequence).unsqueeze(0); xl = torch.LongTensor([len(sequence)])
        with torch.no_grad():
            audio = self.net_g.infer(x, xl, noise_scale=0.667, noise_scale_w=0.8, length_scale=max(0.5, min(2.0, 1.0 / speed)))[0][0, 0].cpu().numpy()
        out = io.BytesIO(); sf.write(out, np.asarray(audio), self.hps.data.sampling_rate, format="WAV"); return out.getvalue()
