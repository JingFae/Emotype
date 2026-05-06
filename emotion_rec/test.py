import numpy as np
import torch
import torch.nn as nn
from transformers import Wav2Vec2Processor
from transformers.models.wav2vec2.modeling_wav2vec2 import (
    Wav2Vec2Model,
    Wav2Vec2PreTrainedModel,
)


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
        self.init_weights()

    def forward(self, input_values):
        outputs = self.wav2vec2(input_values)
        hidden_states = outputs[0]                 # (B, T, H)
        hidden_states = torch.mean(hidden_states, dim=1)  # (B, H)
        logits = self.classifier(hidden_states)    # (B, 3)
        return hidden_states, logits


# ===== GPU 设置 =====
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
use_amp = (device.type == "cuda")  # GPU 时启用 AMP

model_name = "D:\\论文撰写\\VibeType\\Wav2vec-2.0"
processor = Wav2Vec2Processor.from_pretrained(model_name)

model = EmotionModel.from_pretrained(model_name).to(device)
model.eval()  # 推理一定要 eval()

# dummy signal
sampling_rate = 16000
signal = np.zeros((1, sampling_rate), dtype=np.float32)


def process_func(
    x: np.ndarray,
    sampling_rate: int,
    embeddings: bool = False,
) -> np.ndarray:
    # processor 输出是 list/np；这里保证 float32
    y = processor(x, sampling_rate=sampling_rate, return_tensors="pt")
    y = y["input_values"].to(device)  # (B, L) 直接上 GPU

    with torch.inference_mode():
        # AMP 可选：更快更省显存（一般不会影响这类回归输出太多）
        if use_amp:
            with torch.cuda.amp.autocast(dtype=torch.float16):
                out = model(y)[0 if embeddings else 1]
        else:
            out = model(y)[0 if embeddings else 1]

    return out.detach().cpu().numpy()


print(process_func(signal, sampling_rate))
# [[arousal, dominance, valence]]

print(process_func(signal, sampling_rate, embeddings=True))
# pooled hidden states
