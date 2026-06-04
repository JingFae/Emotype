# EmoMirror Deployment

EmoMirror is served as one Dockerized FastAPI web service:

- `/` serves the EmoMirror web app.
- `/analyze-text` returns text-based emotion mirror feedback for journaling.
- `/predict` keeps the existing audio emotion API.
- `/participants/session`, `/diaries`, and `/usage-events` store research sessions,
  diary entries, and interaction logs.
- `/healthz` is used for deployment health checks.

## Local Run

```powershell
pip install -r requirements.txt
uvicorn emotion_rec.app:app --host 0.0.0.0 --port 8000
```

Without `DATABASE_URL`, the app stores research data in
`emotion_rec/emomirror_data.sqlite3` for local development.

Open:

```text
http://localhost:8000/
```

## Render Blueprint

`render.yaml` is configured for one public Docker web service named `emomirror`.

1. Commit and push:

```powershell
git add .gitignore .dockerignore AGENTS.md DEPLOYMENT.md Dockerfile render.yaml requirements-web.txt emotion_rec/app.py emotion_rec/__init__.py emotion_rec/static requirements.txt
git commit -m "Build EmoMirror journal interface"
git push origin main
```

2. Open the Blueprint:

```text
https://dashboard.render.com/blueprint/new?repo=https://github.com/JingFae/Emotype
```

3. Set these secrets in Render:

```text
DEEPSEEK_API_KEY
DATABASE_URL
ADMIN_TOKEN
```

All generative LLM calls go through `emotion_rec/llm_client.py`, which uses the
OpenAI SDK pointed at DeepSeek. The default model is `deepseek-v4-flash`; set
`DEEPSEEK_MODEL` to override it. If `DEEPSEEK_API_KEY` is empty, EmoMirror still
runs with local fallback emotion labels and typography styles. Audio emotion
(`/predict`) stays on the local Wav2Vec2 model.

`DATABASE_URL` should point to your Render Postgres internal connection string.
`ADMIN_TOKEN` protects the full research export endpoints:

```text
/admin/export.json
/admin/export.csv
```

Participants can export their own diary and usage data from the web UI after
entering their experiment code.

## Docker Run

Use Docker when you want the same environment locally and in production:

```powershell
docker build -t emomirror .
docker run --rm -p 8000:8000 -e DEEPSEEK_API_KEY="$env:DEEPSEEK_API_KEY" emomirror
```

The Docker image installs CPU-only PyTorch wheels plus system audio dependencies such as `ffmpeg`.

## Notes

- `Wav2vec-2.0/model.safetensors` is large and should stay on Git LFS.
- Torch plus Wav2Vec2 may need more memory than a free instance can provide. If `/healthz` shows `model_loaded: false`, inspect deploy logs first; if logs show OOM or killed workers, upgrade the instance.
- Browser speech-to-text uses the user's browser SpeechRecognition support and does not require server-side audio transcription.
