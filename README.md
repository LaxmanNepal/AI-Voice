# Laxman AI Voice

A self-hosted, open-source text-to-speech platform designed to grow from browser/local TTS into a full AI voice studio.

## Goal

Build an ElevenLabs-style experience without depending on a paid TTS API:

- Text to speech
- Local/browser inference where practical
- Pluggable open-source TTS engines
- Voice library and presets
- WAV/MP3 export
- History and projects
- Multilingual architecture
- Optional voice cloning only with models whose licenses permit the intended use
- YouTube narration workflow
- Nepali-first expansion

## Roadmap

### Phase 0 — Foundation
- Responsive web application
- Accessible editor and audio player
- Engine abstraction
- Health/status system
- Configuration and model registry
- GitHub Pages-ready frontend

### Phase 1 — Working TTS
- Browser SpeechSynthesis fallback
- Local FastAPI engine endpoint
- Engine adapter interface
- Voice discovery endpoint
- Audio generation/download pipeline
- WAV-first output

### Phase 2 — Local neural inference
- Add a redistributable ONNX-compatible TTS model
- Web/ONNX inference path where model size and browser support allow it
- Python local inference path for stronger models
- Model manifest with license, size, language and checksum metadata

### Phase 3 — Voice studio
- Voice presets
- Speed/pitch/style controls where the selected model supports them
- Paragraph/scene editor
- Per-scene voice assignment
- Regenerate individual scene
- Project save/load
- Generation history

### Phase 4 — Multilingual
- Language-aware voice registry
- Nepali/Hindi/English/Arabic architecture
- Pronunciation dictionary
- SSML-like pause and emphasis abstraction
- Automatic text segmentation

### Phase 5 — Voice cloning
- Reference-audio upload
- Speaker embedding pipeline where supported
- Consent/ownership UX
- Clone management
- Model-specific safety and licensing checks
- No impersonation presets or deceptive defaults

### Phase 6 — Creator Studio
- YouTube narration mode
- Timeline/scenes
- Batch generation
- Long-form text processing
- Subtitle/caption timing metadata
- Export presets

### Phase 7 — Production hardening
- PWA
- Offline caching for browser-compatible engines
- IndexedDB project storage
- Rate/size limits for hosted deployments
- Observability and error reporting
- Automated tests
- Model checksum verification

## Repository structure

```text
AI-Voice/
├── index.html
├── assets/
├── css/
│   └── styles.css
├── js/
│   └── app.js
├── backend/
│   ├── app.py
│   └── requirements.txt
├── config/
│   └── voices.json
├── models/
│   └── README.md
├── .github/workflows/
│   └── pages.yml
└── README.md
```

## Important architecture decision

GitHub Pages hosts the frontend. It does not provide GPU inference. The application therefore has three engine modes:

1. Browser fallback — zero server cost, dependent on the browser's installed voices.
2. Local neural engine — FastAPI + a locally installed open-source model.
3. Hosted neural engine — optional deployment elsewhere; the frontend remains independent of the provider.

This prevents the UI from being locked to one model or one hosting provider.

## Licensing

Do not add model weights to this repository until their redistribution license has been verified. Keep model metadata in `config/voices.json` and place large model artifacts in an appropriate model store or local filesystem.

## Local backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

The frontend automatically tries the local endpoint and falls back to browser speech when it is unavailable.
