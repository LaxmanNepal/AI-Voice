# Laxman AI Voice

A local-first, open-source AI voice studio for creators with a Nepali-first neural workflow.

## Current capabilities

- Responsive glassmorphism voice studio
- Nepali-first neural VITS engine
- Kokoro ONNX multilingual engine path
- Browser SpeechSynthesis fallback
- Speed and pitch controls
- WAV generation + optional FFmpeg MP3 export
- Exact inline `[pause:500]` markers
- Emphasis-safe text cleanup
- Pronunciation dictionary with browser persistence and backend application
- Creator presets: Documentary, News, Emotional, Story, Shorts
- Scene timeline with per-scene generation and production controls
- Drag/drop scene ordering and scene copy/paste
- Browser waveform visualization
- Roman Nepali helper and smart punctuation pauses
- Local background-music/SFX preview mixer
- Project save/load via SQLite
- V8 local autosave + undo/redo + full-studio mode
- SRT/VTT subtitle generation
- Creator Batch ZIP with scene WAVs, combined narration, subtitles and manifest
- OpenAI-compatible `/v1/audio/speech` endpoint
- Safe voice-cloning boundary; cloning remains disabled until a compatible licensed model and consent workflow are verified

## Local neural setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Prepare the Nepali model from the UI or API:

```bash
curl -X POST http://127.0.0.1:8000/models/nepali/prepare
```

Then run the API:

```bash
uvicorn app:app --reload --port 8000
```

For a static frontend:

```bash
python -m http.server 5500
```

Open `http://127.0.0.1:5500` and keep the FastAPI service running on port 8000 for neural generation.

## API highlights

- `GET /health` — engine readiness and capabilities
- `GET /models` — model metadata
- `GET /voices` — voice registry
- `GET /presets` — creator presets
- `GET /pronunciations` — default pronunciation dictionary
- `POST /generate` — processed WAV generation
- `POST /scene/generate` — scene WAV with before/after pauses
- `POST /export/mp3` — optional FFmpeg MP3 generation
- `POST /batch/generate` — creator package ZIP
- `POST /v1/audio/speech` — OpenAI-style local speech endpoint
- `GET/POST/DELETE /projects` — SQLite project persistence

Generation requests may include:

```json
{
  "text": "नमस्ते! AI बारे कुरा गरौँ। [pause:500]",
  "language": "ne",
  "voice": "nepali-vits",
  "speed": 1.0,
  "pronunciations": {
    "AI": "ए आई"
  },
  "normalize": true
}
```

## Architecture

```text
Browser UI
   ├── V8 Creator Studio layer
   │     ├── waveform
   │     ├── scenes
   │     ├── presets
   │     ├── autosave / undo / redo
   │     └── browser mixer preview
   │
   ├── Browser SpeechSynthesis fallback
   │
   └── FastAPI
         ├── pronunciation normalization
         ├── text normalization
         ├── exact pause chunking
         ├── audio processing
         └── engine abstraction
               ├── Nepali VITS
               └── Kokoro ONNX
```

## Hosting note

GitHub Pages can host the UI but cannot run Python neural inference. The public static UI therefore needs `AI_VOICE_API` pointing to a running FastAPI service for real neural generation. Browser speech remains the fallback.

## Licensing policy

Model weights are not committed to this repository. Each model should retain its upstream license/source information. Voice cloning is intentionally disabled until model licensing, consent, ownership and anti-impersonation safeguards are verified.
