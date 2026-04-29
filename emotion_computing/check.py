import io
import numpy as np
import torch
import torch.nn as nn
import librosa
from fastapi import FastAPI, UploadFile, File, HTTPException
from transformers import Wav2Vec2Processor
from transformers.models.wav2vec2.modeling_wav2vec2 import (
    Wav2Vec2Model,
    Wav2Vec2PreTrainedModel,
)
import uvicorn

# ==========================================
# 1. 模型定义 (保持官方代码原样)
# ==========================================

class RegressionHead(nn.Module):
    r"""Classification head."""
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = features
        x = self.dropout(x)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        x = self.out_proj(x)
        return x

class EmotionModel(Wav2Vec2PreTrainedModel):
    r"""Speech emotion classifier."""
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = RegressionHead(config)
        self.init_weights()

    def forward(self, input_values):
        outputs = self.wav2vec2(input_values)
        hidden_states = outputs[0]
        hidden_states = torch.mean(hidden_states, dim=1)
        logits = self.classifier(hidden_states)
        return hidden_states, logits

# ==========================================
# 2. 全局初始化 (加载模型)
# ==========================================

app = FastAPI(title="VibeType Emotion API", description="Audio to Valence-Arousal API")

# 配置
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
# 注意：请确保服务器上这个路径是可访问的，或者换成相对路径
MODEL_PATH = '/public/home/202320163218/dong/models/wav2vec' 
TARGET_SAMPLING_RATE = 16000

print(f"Loading model from {MODEL_PATH} on {DEVICE}...")

try:
    processor = Wav2Vec2Processor.from_pretrained(MODEL_PATH)
    model = EmotionModel.from_pretrained(MODEL_PATH).to(DEVICE)
    model.eval() # 设置为评估模式
    print("Model loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}")
    # 在实际部署中，这里可能需要抛出错误或退出

# ==========================================
# 3. 核心处理逻辑
# ==========================================

def process_audio(audio_array: np.ndarray, sr: int):
    """
    处理音频数据并进行推理
    """
    # 1. 预处理 (Processor handles normalization)
    #Processor expects (batch_size, sequence_length) or (sequence_length,)
    y = processor(audio_array, sampling_rate=sr, return_tensors="pt")
    
    # 2. 移动到设备
    input_values = y['input_values'].to(DEVICE)
    
    # 3. 推理
    with torch.no_grad():
        # model returns (hidden_states, logits)
        _, logits = model(input_values)
    
    # 4. 转回 CPU numpy
    scores = logits.cpu().numpy()[0] # 取 batch 中的第一个
    return scores

# ==========================================
# 4. API 接口定义
# ==========================================

@app.get("/")
def health_check():
    return {"status": "running", "device": DEVICE}

@app.post("/predict")
async def predict_emotion(file: UploadFile = File(...)):
    """
    上传音频文件 (WAV/MP3)，返回 Arousal, Dominance, Valence
    """
    # 1. 读取上传的文件内容
    try:
        contents = await file.read()
        # 使用 io.BytesIO 将字节流转换为 librosa 可读的格式
        # 强制重采样到 16000Hz (Wav2Vec2 的硬性要求)
        audio_array, _ = librosa.load(io.BytesIO(contents), sr=TARGET_SAMPLING_RATE)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio file: {e}")

    # 2. 调用模型
    try:
        # 模型输出顺序通常是 [Arousal, Dominance, Valence]
        # 需要确认你的训练数据的 label 顺序，这里假设是 A, D, V
        scores = process_audio(audio_array, TARGET_SAMPLING_RATE)
        
        # 3. 构造返回结果
        return {
            "filename": file.filename,
            "emotions": {
                "arousal": float(scores[0]),
                "dominance": float(scores[1]),
                "valence": float(scores[2])
            },
            # 为了方便前端调试，可以返回原始数组
            "raw_scores": scores.tolist()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)