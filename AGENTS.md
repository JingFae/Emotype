# AGENTS.md

## Project Overview

Emotype is a Python-based speech emotion and kinetic typography project.
It uses a local Wav2Vec2 emotion model to infer VAD scores:

- `arousal`
- `dominance`
- `valence`

The main service also combines text, acoustic features, and an LLM-generated
typography design map for frontend rendering.

Text emotion handling is intentionally separated from typography generation:

- `/analyze-text` uses `emotion_rec/text_emotion.py` to estimate segment-level
  V-A values, explicit/implicit labels, confidence, and evidence. The module can
  load `Johnson8187/Chinese-Emotion-Small` for explicit emotion classification,
  fuse it with deterministic implicit-emotion rules, and later load
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` plus a trained
  regression head when `TEXT_EMOTION_HEAD_PATH` is available.
- The LLM is not the source of truth for text emotion classification. It is used
  only to generate the character-indexed kinetic typography design map.
- `/predict` uses the local Wav2Vec2 model for audio emotion VAD inference, then
  normalizes and maps those values through the same V-A mapper.

## Repository Layout

- `emotion_rec/`
  - Main FastAPI service.
  - `app.py` exposes `/predict` and returns VAD, acoustic features, and
    `va_mapping` plus `llm_design`.
  - `va_mapper.py` maps already inferred valence/arousal values to colors,
    nearest labels, quadrants, confidence, and segment summaries. It must not
    call ASR, LLMs, or emotion inference models.
  - `text_emotion.py` owns text semantic emotion inference. It returns
    `text_emotion.segments` with `text`, `valence`, `arousal`, `confidence`,
    `explicit_label`, `implicit_label`, `evidence`, and `source`.
    Default `auto` mode tries a trained regression head first, then
    `Johnson8187/Chinese-Emotion-Small`, and finally deterministic rules.
  - `shared/emotion_lexicon.json` contains the canonical 80-label V-A lexicon
    used by both backend and frontend fallbacks.
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
  - `vad_normalized`
  - `acoustics`
  - `text_emotion`
  - `va_mapping`
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

## Text Emotion And Semantic V-A Strategy

Current text emotion logic:

- The active `/analyze-text` endpoint calls `analyze_text_emotion(...)`, then
  passes the returned segments into `map_segments(...)`.
- If a trained text emotion regression head is not present, the module uses
  `Johnson8187/Chinese-Emotion-Small` for explicit emotion classification and
  fuses it with deterministic implicit-emotion rules for body cues, denial,
  minimizers, contrast markers, relationship cues, action impulses, shame,
  suppressed anger, overwhelm, loneliness, lexicon matches, and English hints.
- If the classifier cannot be loaded, the same deterministic rules remain the
  fallback so the UI can still render `text_emotion` and `va_mapping`.
- This fallback is suitable as a deterministic demo path. Robust semantic
  recognition requires training and shipping the regression head.
- LLM calls are currently for typography design only. Always keep an explicit
  timeout and local fallback for LLM calls so `/analyze-text` cannot hang if the
  external API is slow, blocked, or missing credentials.

Recommended semantic V-A upgrade path:

1. Keep `va_mapper.py` as the stable mapping layer and do not put model
   inference inside it.
2. Keep `text_emotion.py` as the semantic inference module that accepts text
   segments and returns `{valence, arousal, confidence, explicit_label,
   implicit_label, evidence}` for each segment.
3. For lightweight deployment, prefer a multilingual or Chinese-capable
   transformer encoder fine-tuned or calibrated to V-A outputs:
   - First choice for Chinese/English balance: `BAAI/bge-small-zh-v1.5` or
     `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` with a small
     regression head.
   - If Chinese-only and stronger nuance is required:
     `hfl/chinese-macbert-base` is stronger but heavier; consider distillation
     or ONNX quantization before production.
   - Avoid using a large generative LLM as the primary V-A classifier for every
     keystroke because latency and cost will hurt the live typing experience.
4. For tonight-scale development, `Chinese-Emotion-Small + label-to-V-A mapping
   + implicit rules` is the preferred online path. Store a future trained
   regression head at `emotion_rec/models/text_emotion_head.pt` or set
   `TEXT_EMOTION_HEAD_PATH`. The main API should continue to return the same
   `text_emotion` and `va_mapping` shapes.
5. Keep browser fallback deterministic by reusing
   `shared/emotion_lexicon.json` or generated equivalent data.

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
