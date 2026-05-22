# AGENTS.md

## Project Overview

Emotype is a Python-based speech emotion and kinetic typography project.
It uses a local Wav2Vec2 emotion model to infer VAD scores:

- `arousal`
- `dominance`
- `valence`

The main service also combines text, acoustic features, and an LLM-generated
typography design map for frontend rendering.

## Repository Layout

- `emotion_rec/`
  - Main FastAPI service.
  - `app.py` exposes `/predict` and returns VAD, acoustic features, and
    `llm_design`.
  - `static/` contains the production web UI served from `/`.
  - `start.sh` starts the service on port `8000`.
  - `cert.pem`, `key.pem`, logs, and cache files should be treated as local
    runtime artifacts.
- `emotion_computing/`
  - Smaller model inference demos and checks.
  - `demo.py` runs a local Wav2Vec2 inference example.
  - `check.py` exposes a simpler `/predict` API.
- `hmotiongpt-api-test/`
  - Minimal FastAPI upload test service on port `9001`.
- `Wav2vec-2.0/`
  - Local Hugging Face model files.
  - Do not rename or move this directory unless updating all model-path logic.
- `audio/`
  - Sample audio files for manual testing.
- `requirements.txt`
  - Python dependencies.
- `requirements-web.txt`
  - Runtime dependencies used by the Docker deployment after CPU PyTorch is
    installed separately.
- `render.yaml`
  - Render Blueprint for one public web service.
- `Dockerfile`
  - Reproducible production container for the FastAPI app, model, and static UI.
- `DEPLOYMENT.md`
  - Human-facing local run and Render deployment notes.

## Setup

Use Python 3.11+ if possible.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Audio conversion uses `pydub`, so `ffmpeg` may be required for WebM/MP3 input.
Make sure `ffmpeg` is available on `PATH` when testing uploads from browsers.

## Running The Main API

From the repository root:

```powershell
Set-Location emotion_rec
uvicorn app:app --host 0.0.0.0 --port 8000
```

Or on Unix-like shells:

```bash
cd emotion_rec
bash start.sh
```

Health and prediction behavior:

- Main endpoint: `POST /predict`
- Multipart fields:
  - `file`: uploaded audio file
  - `text`: optional transcript text
  - `return_embeddings`: optional query parameter
- Expected response keys:
  - `vad`
  - `acoustics`
  - `llm_design`
  - `status`

## Model Path

By default, services load the model from:

```text
Wav2vec-2.0/
```

Override with:

```powershell
$env:MODEL_NAME_OR_PATH="C:\path\to\model"
```

Keep path handling portable. Prefer paths relative to the current file or
`MODEL_NAME_OR_PATH`; avoid hard-coded personal absolute paths.

## Development Notes For Agents

- Preserve existing user edits. This repository may have local uncommitted
  changes, runtime logs, and cache files.
- Prefer small, targeted changes. Avoid broad rewrites unless requested.
- Use `rg`/`rg --files` for search.
- Use `python -m compileall <dir>` or targeted script execution for quick
  syntax checks after Python changes.
- Do not commit or print secrets. API keys, certificates, and private keys
  should be moved to environment variables when touching related code.
- Do not edit model weights or generated cache files unless explicitly asked.
- Keep API response shapes stable unless the user asks for a contract change.
- If changing audio input handling, test at least WAV and browser-recorded WebM
  where possible.
- If changing typography generation, keep `llm_design` as a character-indexed
  map because frontend consumers likely depend on that shape.

## Known Project Concerns

- Some source comments appear mojibake/encoding-corrupted. Do not mechanically
  rewrite all comments while making unrelated changes.
- `emotion_rec/app.py` currently contains LLM integration logic. Prefer reading
  secrets from environment variables before production use.
- Runtime artifacts such as `__pycache__/`, `uvicorn.*.log`, certificates, and
  private keys should not be treated as source changes.

## Useful Checks

Run a syntax check:

```powershell
python -m compileall emotion_rec emotion_computing hmotiongpt-api-test
```

Run the local model demo:

```powershell
python emotion_computing\demo.py
```

Start the main API and inspect docs:

```text
http://localhost:8000/docs
```

Open the web UI:

```text
http://localhost:8000/
```
