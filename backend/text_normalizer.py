"""Nepali-first text normalization for neural TTS."""
from __future__ import annotations
import re
import unicodedata

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def normalize_text(text: str, language: str = "ne") -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if language.startswith("ne"):
        text = text.translate(DEVANAGARI_DIGITS)
        for old, new in {"&":" र ", "%":" प्रतिशत ", "@":" एट ", "#":" ह्यासट्याग ", "+":" प्लस ", "=":" बराबर "}.items():
            text = text.replace(old, new)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return re.sub(r" +", " ", text).strip()


def split_scenes(text: str, max_chars: int = 900) -> list[str]:
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    scenes: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            scenes.append(paragraph)
            continue
        current = ""
        for sentence in re.split(r"(?<=[।.!?])\s+", paragraph):
            if not sentence:
                continue
            if current and len(current) + 1 + len(sentence) > max_chars:
                scenes.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            scenes.append(current)
    return scenes
