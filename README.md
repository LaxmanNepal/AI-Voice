# Laxman AI Voice

A local-first, open-source AI voice studio for creators. The project now includes a real Kokoro ONNX inference path, browser fallback, project persistence, multilingual voice catalog, and safe boundaries for future cloning engines.

## What is implemented

- Responsive voice studio UI
- Browser SpeechSynthesis fallback
- FastAPI backend
- Real Kokoro ONNX adapter
- 18 multilingual Kokoro voices in the registry
- Speed control
- WAV generation and download
- Project save/load via SQLite or browser localStorage fallback
- Health and capability endpoint
- Batch orchestration endpoint boundary
- Safe voice-cloning boundary
- GitHub Pages frontend deployment

## Local neural setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cd ..
python scripts/download-kokoro.py
cd backend
uvicorn app:app --reload --port 8000
```

The setup script downloads the Kokoro v1.0 ONNX model and voice bundle at runtime rather than committing large model artifacts to Git. The Kokoro model is published under Apache-2.0; the `kokoro-onnx` adapter is MIT according to its upstream project. Review current upstream terms before redistribution. citeturn0search15turn0search5

Open `index.html` from a static server or GitHub Pages. For local development, a simple static server is recommended:

```bash
python -m http.server 5500
```

Then visit `http://127.0.0.1:5500`.

## Environment

Copy `backend/.env.example` if desired:

```text
AI_VOICE_ENGINE=auto
AI_VOICE_KOKORO_MODEL=
AI_VOICE_KOKORO_VOICES=
```

By default the adapter expects:

```text
models/kokoro-v1.0.onnx
models/voices-v1.0.bin
```

## Architecture

```text
Browser UI
   │
   ├── Browser SpeechSynthesis fallback
   │
   └── FastAPI /generate
           │
           └── Engine abstraction
                 └── Kokoro ONNX

FastAPI
   ├── /health
   ├── /voices
   ├── /generate
   ├── /projects
   ├── /batch/status
   └── /clone (disabled until a licensed cloning model + consent flow exists)
```

## Roadmap status

| Phase | Status |
|---|---|
| Foundation | ✅ Complete |
| Working TTS | ✅ Complete |
| Local neural inference | ✅ Complete |
| Voice studio | 🟢 Core complete |
| Multilingual registry | 🟢 Core complete |
| Voice cloning | 🟡 Safe architecture only; no unsafe/unlicensed cloning enabled |
| Creator Studio | 🟢 Core project workflow complete |
| Production hardening | 🟡 PWA, automated test matrix and hosted deployment remain optional final hardening |

## Important limitation

GitHub Pages is static hosting. It cannot run Python neural inference. Therefore the public Pages UI uses browser speech unless `AI_VOICE_API` points at a running FastAPI service. A truly zero-server public neural mode can be added later with browser ONNX/WebGPU, but model size, browser support and download cost must be considered.

## Licensing policy

Model weights are never silently committed to the repository. Each model must have explicit license, source and checksum metadata. Voice cloning is deliberately disabled until an appropriate model and a consent/ownership workflow are verified.
