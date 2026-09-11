"""Pluggable TTS engine adapters."""

from .kokoro import KokoroEngine, KOKORO_AVAILABLE

__all__ = ["KokoroEngine", "KOKORO_AVAILABLE"]
