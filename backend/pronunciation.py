"""Project-safe text pronunciation replacements for TTS.

This intentionally uses text replacement rather than claiming phoneme-level control.
Users can map a written form to a form the selected model pronounces better.
"""
from __future__ import annotations
import re

DEFAULTS = {
    "AI": "ए आई",
    "API": "ए पी आई",
    "YouTube": "युट्युब",
    "Facebook": "फेसबुक",
    "TikTok": "टिकटक",
    "Google": "गुगल",
    "ChatGPT": "च्याट जीपीटी",
    "OpenAI": "ओपन एआई",
    "KWD": "कुवेती दिनार",
    "NPR": "नेपाली रुपैयाँ",
}


def normalize_dictionary(items: dict[str, str] | None) -> dict[str, str]:
    out = dict(DEFAULTS)
    if items:
        for key, value in items.items():
            key, value = str(key).strip(), str(value).strip()
            if key and value:
                out[key] = value
    return out


def apply_pronunciations(text: str, items: dict[str, str] | None = None) -> str:
    result = text or ""
    dictionary = normalize_dictionary(items)
    for source, replacement in sorted(dictionary.items(), key=lambda pair: len(pair[0]), reverse=True):
        result = re.sub(re.escape(source), replacement, result, flags=re.I)
    return result
