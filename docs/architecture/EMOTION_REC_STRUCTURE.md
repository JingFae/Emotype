# `emotion_rec` architecture and interface map

This document is the source-of-truth map for the main FastAPI service. The
refactor keeps every existing HTTP route, response contract, public static URL,
database location, and ASGI entry point stable while separating implementation
responsibilities.

## Dependency direction

```text
api/application.py + api/routes/
        |
        +--> api/schemas.py
        +--> services/
        +--> domain/emotion/
        +--> persistence/repository.py
        +--> integrations/

services/ --> domain/emotion/ + persistence/ + integrations/
domain/emotion/mapping.py --> shared/emotion_lexicon.json
integrations/ --> external provider SDKs
persistence/ --> SQLAlchemy + SQLite/PostgreSQL
```

`domain/emotion/mapping.py` remains a pure V-A mapping layer. It must not call
ASR, generative LLMs, persistence, or emotion-inference models.

## Backend modules

| Path | Responsibility | Main public interface |
| --- | --- | --- |
| `emotion_rec/app.py` | Stable compatibility entry point | `app`; supports `emotion_rec.app:app` and `app:app` from `emotion_rec/` |
| `emotion_rec/api/application.py` | FastAPI assembly, middleware, static mounts, startup, and API route implementations | `app` |
| `emotion_rec/api/routes/pages.py` | HTML entry-page routes | `router` |
| `emotion_rec/api/schemas.py` | Pydantic HTTP request contracts | `*Request` models |
| `emotion_rec/core/config.py` | Stable project/package paths and environment parsing | `PROJECT_ROOT`, `STATIC_DIR`, `SHARED_DIR`, `MODELS_DIR`, `DEFAULT_*` |
| `emotion_rec/core/security.py` | JWT creation and verification | `create_access_token`, `verify_token` |
| `emotion_rec/domain/emotion/mapping.py` | Pure V-A normalization, labels, colors, candidates, and segment aggregation | `normalize_vad`, `map_va`, `map_segments`, `split_text_segments` |
| `emotion_rec/domain/emotion/text.py` | Semantic text emotion inference and deterministic fallback rules | `analyze_text_emotion` |
| `emotion_rec/integrations/llm.py` | DeepSeek/OpenAI-compatible text generation adapter with timeout/fallback behavior | `llm_enabled`, `chat`, `chat_json` |
| `emotion_rec/integrations/vision.py` | Gemini image understanding adapter | `gemini_enabled`, `analyze_image`, `chat`, `chat_json` |
| `emotion_rec/persistence/repository.py` | SQLAlchemy models, schema compatibility, CRUD, review aggregation, export, auth persistence, and Echo storage | repository functions imported by the API/services |
| `emotion_rec/services/audio_emotion.py` | Wav2Vec2 model lifecycle, upload normalization, VAD inference, and acoustic features | `load_model`, `model_loaded`, `predict_raw_vad`, `read_audio_to_mono_16k`, `extract_acoustic_features` |
| `emotion_rec/services/body_sensation.py` | Body-sensation normalization, safety rules, emotion context, LLM/fallback advice, and event logging | `generate_body_sensation_advice` |
| `emotion_rec/shared/emotion_lexicon.json` | Canonical 80-label V-A lexicon shared with the browser | mounted at `/shared/emotion_lexicon.json` |
| `emotion_rec/tools/audio_model_demo.py` | Standalone Wav2Vec2 regression experiment | developer-only functions/classes |
| `emotion_rec/tools/gpu_check.py` | PyTorch/CUDA diagnostic | `python -m emotion_rec.tools.gpu_check` |
| `emotion_rec/tools/check_contracts.py` | Dependency-free route/static compatibility check | `python -m emotion_rec.tools.check_contracts` |
| `emotion_rec/start.sh` | Unix service launcher | starts `uvicorn app:app` on port 8000 |
| `emotion_rec/README_body_sensation_api.md` | Body-sensation endpoint notes and payload examples | documentation only |
| package `__init__.py` files | Declare Python package boundaries | no runtime behavior |

### Compatibility modules

The following small modules intentionally remain at their old paths. They
re-export the canonical implementation so existing scripts and deployments do
not break during the migration.

| Stable old path | Canonical implementation |
| --- | --- |
| `emotion_rec/va_mapper.py` | `emotion_rec/domain/emotion/mapping.py` |
| `emotion_rec/text_emotion.py` | `emotion_rec/domain/emotion/text.py` |
| `emotion_rec/storage.py` | `emotion_rec/persistence/repository.py` |
| `emotion_rec/llm_client.py` | `emotion_rec/integrations/llm.py` |
| `emotion_rec/gemini_client.py` | `emotion_rec/integrations/vision.py` |
| `emotion_rec/body_sensation.py` | `emotion_rec/services/body_sensation.py` |
| `emotion_rec/gpu_test.py` | `emotion_rec/tools/gpu_check.py` |
| `emotion_rec/test.py` | `emotion_rec/tools/audio_model_demo.py` |

New code should import the canonical implementation paths.

## HTTP interfaces

### Pages

| Method | Path(s) | Static entry |
| --- | --- | --- |
| GET/HEAD | `/` | `index.html` |
| GET/HEAD | `/essay` | `essay.html` |
| GET/HEAD | `/diary` | `diary.html` |
| GET/HEAD | `/review` | `review.html` |
| GET/HEAD | `/records`, `/history` | `records.html` |
| GET/HEAD | `/historyreview` | `historyreview.html` |
| GET/HEAD | `/emo-echo` | `emo_echo.html` |
| GET/HEAD | `/body`, `/body-sensation`, `/body_sensation` | `body_sensation.html` |
| GET | `/login` | `login.html` |
| GET | `/profile` | `profile.html` |

### Analysis and generation

| Method | Path | Input | Main output |
| --- | --- | --- | --- |
| GET | `/healthz` | none | device/model/LLM status |
| POST | `/analyze-text` | JSON text + intensity | `text_emotion`, `va_mapping`, `llm_design` |
| POST | `/predict` | multipart audio + optional text | raw/normalized VAD, acoustics, mapping, design, optional embedding |
| POST | `/api/transcribe` | multipart audio | transcript text |
| POST | `/api/uploads` | multipart image + context | Gemini image analysis or fallback status |
| POST | `/api/analyze-combined` | text + image analysis JSON | fused `combined_emotion` |
| POST | `/body-sensation/advice` | `BodySensationAdviceRequest` | context, links, advice, safety, logging status |
| POST | `/api/emo-echo/chat` | message/session/history | assistant reply and persisted session |
| GET | `/api/emo-echo/sessions` | participant scope | conversation sessions |

### Account, records, diary, and review

| Group | Paths |
| --- | --- |
| Authentication/profile | `POST /api/auth/register`, `POST /api/auth/login`, `GET/PUT /api/auth/me`, `PUT /api/auth/me/password`, `GET/PUT /api/auth/me/settings` |
| Admin users | `GET /api/admin/users`, `GET /api/admin/users/{username}` |
| Participant/session | `POST /participants/session`, `GET /participants/{participant_code}/diaries`, `DELETE /participants/{participant_code}/all-data` |
| Journal/event writes | `POST /diaries`, `POST /usage-events` |
| Formal diary | `GET /api/diary`, `GET /api/diary/context`, `PUT /api/diary/by-date/{diary_date}`, `POST /api/diary/by-date/{diary_date}/reflect` |
| Review/records | `GET /api/review/overview`, `GET /api/review/report`, `POST /api/review/reflect`, `GET /api/records` |
| Admin review/records | `GET /api/admin/review/overview`, `GET /api/admin/records` |
| Export | participant `/export.json` + `/export.csv`; admin `/admin/export.json` + `/admin/export.csv` |

## Frontend modules

The frontend intentionally remains under one mounted `static/` root because
its public URL is a deployment contract. See `emotion_rec/static/README.md` for
the page-to-file map. A future bundler migration may reorganize physical asset
paths, but it should be a separate change with browser-level regression tests.

## Runtime artifacts

The following are not source modules and must not be moved into the package
layers: `emomirror_data.sqlite3`, `*.log`, `*.pem`, `*.key`, `__pycache__/`, and
model/cache output. The local SQLite default deliberately remains
`emotion_rec/emomirror_data.sqlite3` after the repository module move.

Files that may exist locally under `emotion_rec/` include `cert.pem`, `key.pem`,
`uvicorn.*.log`, `static-preview.*.log`, cache directories, and the SQLite file.
They are runtime artifacts rather than application modules. Certificates and
private keys must be supplied through deployment secrets and must not be added
to new source modules.
