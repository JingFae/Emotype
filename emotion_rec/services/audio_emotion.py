"""Local Wav2Vec2 emotion inference and acoustic feature extraction."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import librosa
import numpy as np
import torch
import torch.nn as nn
import transformers.utils as transformers_utils
from pydub import AudioSegment
from transformers import Wav2Vec2FeatureExtractor
from transformers.utils import import_utils as transformers_import_utils

try:
    from emotion_rec.core.config import DEFAULT_MODEL_PATH
except ModuleNotFoundError:  # Support ``uvicorn app:app`` from emotion_rec/.
    from core.config import DEFAULT_MODEL_PATH  # type: ignore


# Wav2Vec2 inference does not need torchvision. Disabling the optional probe
# avoids environment-specific torchvision import failures on CPU deployments.
transformers_import_utils._torchvision_available = False
transformers_import_utils.is_torchvision_available = lambda: False
transformers_utils.is_torchvision_available = lambda: False

from transformers.models.wav2vec2.modeling_wav2vec2 import (  # noqa: E402
    Wav2Vec2Model,
    Wav2Vec2PreTrainedModel,
)


TARGET_SAMPLE_RATE = 16_000
MODEL_NAME_OR_PATH = os.getenv("MODEL_NAME_OR_PATH", str(DEFAULT_MODEL_PATH))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

processor = None
model = None


class AudioProcessingError(ValueError):
    """Raised when an uploaded audio payload cannot be normalized."""


class ModelUnavailableError(RuntimeError):
    """Raised when local Wav2Vec2 weights are not loaded."""


class RegressionHead(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = self.dropout(features)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        return self.out_proj(x)


class EmotionModel(Wav2Vec2PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = RegressionHead(config)
        self.post_init()

    def forward(self, input_values):
        outputs = self.wav2vec2(input_values)
        hidden_states = outputs[0]
        pooled = torch.mean(hidden_states, dim=1)
        logits = self.classifier(pooled)
        return pooled, logits


def load_model(model_path: str | Path | None = None) -> bool:
    """Load the feature extractor and local regression model once at startup."""
    global processor, model

    resolved_path = str(model_path or MODEL_NAME_OR_PATH)
    print(f"Loading model from: {resolved_path} using {DEVICE}...")
    try:
        processor = Wav2Vec2FeatureExtractor.from_pretrained(resolved_path)
        model = EmotionModel.from_pretrained(resolved_path).to(DEVICE)
        model.eval()
        print("Model loaded successfully!")
        return True
    except Exception as error:
        processor = None
        model = None
        print(f"Error loading model: {error}")
        return False


def model_loaded() -> bool:
    return processor is not None and model is not None


def predict_raw_vad(waveform: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return raw A-D-V logits and the pooled Wav2Vec2 embedding."""
    if processor is None or model is None:
        raise ModelUnavailableError("Emotion model is not loaded")

    inputs = processor(
        waveform[None, :],
        sampling_rate=TARGET_SAMPLE_RATE,
        return_tensors="pt",
    )
    input_values = inputs["input_values"].to(DEVICE)
    with torch.inference_mode():
        pooled_states, logits = model(input_values)
    return (
        logits.detach().cpu().numpy()[0],
        pooled_states.detach().cpu().numpy()[0],
    )


def convert_to_wav(source_path: str) -> str:
    """Convert browser or uploaded audio to mono 16 kHz WAV."""
    try:
        audio = AudioSegment.from_file(source_path)
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(1)
        wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = wav_tmp.name
        wav_tmp.close()
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as error:
        print(f"Format conversion failed: {error}")
        raise


def read_audio_to_mono_16k(file_bytes: bytes) -> tuple[np.ndarray, str]:
    """Normalize uploaded bytes and return waveform plus temporary WAV path."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
        temp_file.write(file_bytes)
        source_path = temp_file.name

    wav_path = None
    try:
        wav_path = convert_to_wav(source_path)
        waveform, _ = librosa.load(wav_path, sr=TARGET_SAMPLE_RATE, mono=True)
        return waveform, wav_path
    except Exception as error:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
        raise AudioProcessingError(f"Audio processing failed: {error}") from error
    finally:
        if os.path.exists(source_path):
            os.remove(source_path)


def extract_acoustic_features(wav_path: str) -> dict[str, float]:
    try:
        waveform, _ = librosa.load(wav_path, sr=TARGET_SAMPLE_RATE)
        f0, _, _ = librosa.pyin(
            waveform,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
        )
        average_pitch = np.nanmean(f0) if not np.isnan(f0).all() else 0.0
        average_energy = np.mean(librosa.feature.rms(y=waveform))

        normalized_pitch = min(max((average_pitch - 80) / 200, 0), 1)
        normalized_energy = min(max(average_energy * 10, 0), 1)
        return {
            "pitch_raw": float(average_pitch),
            "pitch_norm": float(normalized_pitch),
            "energy_raw": float(average_energy),
            "energy_norm": float(normalized_energy),
        }
    except Exception as error:
        print(f"Feature extraction warning: {error}")
        return {"pitch_norm": 0.5, "energy_norm": 0.5}

