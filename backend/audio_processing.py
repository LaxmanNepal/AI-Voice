"""Lightweight audio post-processing using NumPy + soundfile.

FFmpeg is optional and is used only for MP3 export.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf


def trim_silence(audio: np.ndarray, sr: int, threshold_db: float = -48.0, pad_ms: int = 35) -> np.ndarray:
    if audio.size == 0:
        return audio
    x = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(x)))
    if peak <= 1e-8:
        return x
    threshold = peak * (10.0 ** (threshold_db / 20.0))
    mask = np.abs(x) > threshold
    if not np.any(mask):
        return x
    pad = int(sr * max(0, pad_ms) / 1000)
    start = max(0, int(np.argmax(mask)) - pad)
    end = min(len(x), int(len(x) - np.argmax(mask[::-1])) + pad)
    return x[start:end]


def normalize_peak(audio: np.ndarray, target_dbfs: float = -1.0) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 1e-8:
        return x
    target = 10.0 ** (target_dbfs / 20.0)
    return np.clip(x * (target / peak), -1.0, 1.0)


def fade(audio: np.ndarray, sr: int, fade_in_ms: int = 0, fade_out_ms: int = 0) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32).copy()
    if not len(x):
        return x
    ni = min(len(x), int(sr * max(0, fade_in_ms) / 1000))
    no = min(len(x), int(sr * max(0, fade_out_ms) / 1000))
    if ni > 1:
        x[:ni] *= np.linspace(0.0, 1.0, ni, dtype=np.float32)
    if no > 1:
        x[-no:] *= np.linspace(1.0, 0.0, no, dtype=np.float32)
    return x


def process(audio: np.ndarray, sr: int, trim: bool = False, normalize: bool = False,
            fade_in_ms: int = 0, fade_out_ms: int = 0, target_dbfs: float = -1.0) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32)
    if trim:
        x = trim_silence(x, sr)
    if normalize:
        x = normalize_peak(x, target_dbfs)
    return fade(x, sr, fade_in_ms, fade_out_ms)


def wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    out = io.BytesIO()
    sf.write(out, np.asarray(audio, dtype=np.float32), sr, format="WAV", subtype="PCM_16")
    return out.getvalue()


def mp3_bytes(audio: np.ndarray, sr: int, bitrate: str = "192k") -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is not installed; MP3 export is unavailable. WAV export still works.")
    with tempfile.TemporaryDirectory(prefix="laxman-ai-voice-") as td:
        wav = Path(td) / "input.wav"
        mp3 = Path(td) / "output.mp3"
        wav.write_bytes(wav_bytes(audio, sr))
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", bitrate, str(mp3)]
        subprocess.run(cmd, check=True)
        return mp3.read_bytes()


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None
