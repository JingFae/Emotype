FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV MODEL_NAME_OR_PATH=/app/Wav2vec-2.0

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgomp1 \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2,<3" "torchaudio>=2.2,<3"

COPY requirements-web.txt .
RUN python -m pip install -r requirements-web.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn emotion_rec.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
