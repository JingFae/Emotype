import io
import os
import json
import http.client
import tempfile
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from fastapi import FastAPI, UploadFile, File, Form, Header, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import transformers.utils as transformers_utils
from transformers import Wav2Vec2FeatureExtractor
from transformers.utils import import_utils as transformers_import_utils

transformers_import_utils._torchvision_available = False
transformers_import_utils.is_torchvision_available = lambda: False
transformers_utils.is_torchvision_available = lambda: False

from transformers.models.wav2vec2.modeling_wav2vec2 import (
    Wav2Vec2Model,
    Wav2Vec2PreTrainedModel,
)
import re
import librosa
from pydub import AudioSegment

try:
    from emotion_rec.va_mapper import (
        EMOTION_LEXICON,
        map_segments,
        map_va,
        normalize_vad,
        split_text_segments,
    )
    from emotion_rec.text_emotion import analyze_text_emotion
    from emotion_rec.storage import (
        create_diary_entry,
        export_all_csv,
        export_all_data,
        export_participant_csv,
        export_participant_data,
        get_or_create_participant,
        init_database,
        list_diary_entries,
        log_usage_event,
    )
except ModuleNotFoundError:
    from va_mapper import (  # type: ignore
        EMOTION_LEXICON,
        map_segments,
        map_va,
        normalize_vad,
        split_text_segments,
    )
    from text_emotion import analyze_text_emotion  # type: ignore
    from storage import (  # type: ignore
        create_diary_entry,
        export_all_csv,
        export_all_data,
        export_participant_csv,
        export_participant_data,
        get_or_create_participant,
        init_database,
        list_diary_entries,
        log_usage_event,
    )

# -----------------------------
# LLM Configuration
# -----------------------------
LLM_API_HOST = os.getenv("LLM_API_HOST", "api.chatanywhere.tech")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
VAD_SOURCE_RANGE = os.getenv("VAD_SOURCE_RANGE", "zero_one")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# -----------------------------
# Model definition
# -----------------------------
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

# -----------------------------
# App Setup
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SHARED_DIR = BASE_DIR / "shared"

app = FastAPI(title="EmoMirror API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if SHARED_DIR.exists():
    app.mount("/shared", StaticFiles(directory=str(SHARED_DIR)), name="shared")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")

# -----------------------------
# Globals
# -----------------------------
# 请确保路径正确指向你的本地模型
DEFAULT_MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Wav2vec-2.0")
)
MODEL_NAME_OR_PATH = os.getenv("MODEL_NAME_OR_PATH", DEFAULT_MODEL_PATH)
TARGET_SR = 16000
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

processor = None
model = None


class TextAnalysisRequest(BaseModel):
    text: str = Field(default="", max_length=6000)
    intensity: float = Field(default=0.8, ge=0.0, le=1.0)


class ParticipantSessionRequest(BaseModel):
    participant_code: str = Field(min_length=2, max_length=64)
    consent_version: str = Field(default="research-v1", max_length=64)


class DiaryEntryRequest(BaseModel):
    participant_code: str = Field(min_length=2, max_length=64)
    raw_text: str = Field(default="", max_length=20000)
    transcript_text: str = Field(default="", max_length=20000)
    original_valence: float | None = None
    original_arousal: float | None = None
    original_label: str | None = Field(default=None, max_length=128)
    final_valence: float | None = None
    final_arousal: float | None = None
    final_label: str | None = Field(default=None, max_length=128)
    final_color: str | None = Field(default=None, max_length=16)
    candidates_json: list | dict | None = None
    text_emotion_json: dict | None = None
    va_mapping_json: dict | None = None


class UsageEventRequest(BaseModel):
    participant_code: str = Field(min_length=2, max_length=64)
    event_type: str = Field(min_length=1, max_length=80)
    metadata_json: dict = Field(default_factory=dict)


@app.on_event("startup")
def _load():
    global processor, model
    try:
        init_database()
        print("Database initialized.")
    except Exception as e:
        print(f"Database initialization warning: {e}")

    print(f"Loading model from: {MODEL_NAME_OR_PATH} using {device}...")
    try:
        processor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME_OR_PATH)
        model = EmotionModel.from_pretrained(MODEL_NAME_OR_PATH).to(device)
        model.eval()
        print("Model loaded successfully!")
    except Exception as e:
        print(f"Error loading model: {e}")


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "device": str(device),
        "model_loaded": processor is not None and model is not None,
    }

# -----------------------------
# Helper Functions
# -----------------------------


def _llm_headers():
    token = LLM_API_KEY.strip()
    if not token:
        return None
    if not token.lower().startswith("bearer "):
        token = f"Bearer {token}"
    return {
        "Authorization": token,
        "Content-Type": "application/json",
    }


def _style_for_va_mapping(va_mapping: dict):
    quadrant = va_mapping.get("quadrant", "neutral")
    color = va_mapping.get("color", "#94A3B8")
    styles = {
        "high_negative": {"weight": 900, "scale": 1.72, "color": color, "animation": "shake-hard"},
        "high_positive": {"weight": 850, "scale": 1.62, "color": color, "animation": "pulse-scale"},
        "low_negative": {"weight": 420, "scale": 1.38, "color": color, "animation": "sad-droop"},
        "low_positive": {"weight": 720, "scale": 1.42, "color": color, "animation": "float-drift"},
        "neutral": {"weight": 560, "scale": 1.16, "color": color, "animation": "float-drift"},
    }
    return styles.get(quadrant, styles["neutral"])


def _standard_vad_from_mapping(va_mapping: dict):
    return {
        "valence": float(va_mapping.get("valence", 0.0)),
        "arousal": float(va_mapping.get("arousal", 0.0)),
        "dominance": 0.0,
    }


def build_fallback_typography_design(text: str, vad: dict, acoustics: dict):
    """Generate local typography using V-A mapping color only."""
    va_mapping = map_va(float(vad.get("valence", 0.0)), float(vad.get("arousal", 0.0)), vad.get("confidence"))
    style = _style_for_va_mapping(va_mapping)
    energy = float(acoustics.get("energy_norm", abs(va_mapping.get("arousal", 0.0))))
    style["scale"] = max(style["scale"], 1.16 + min(1.0, abs(energy)) * 0.45)

    matches = []
    for item in EMOTION_LEXICON:
        label = item["label"]
        start = text.find(label)
        if start != -1:
            matches.append((start, label))

    if not matches:
        matches = [(match.start(), match.group(0)) for match in re.finditer(r"[A-Za-z']{4,}|[\u4e00-\u9fff]{2,4}", text)]

    matches.sort(key=lambda item: item[0])
    limit = 1 if len(re.findall(r"[A-Za-z']+|[\u4e00-\u9fff]+", text.strip())) <= 5 else 3
    final_design_map = {}
    for start, word in matches[:limit]:
        for offset, char in enumerate(word):
            if char.strip():
                final_design_map[str(start + offset)] = dict(style)

    return final_design_map


def infer_text_emotion(text: str):
    text_emotion = analyze_text_emotion(text)
    va_mapping = map_segments(text_emotion["segments"])
    overall = va_mapping["overall"]
    nearby_labels = [
        item["label"]
        for item in overall.get("candidates", [])
        if item.get("label") and item["label"] != overall["label"]
    ]
    return {
        "primary": overall["label"],
        "key": overall["quadrant"],
        "secondary": nearby_labels[:6],
        "confidence": overall["confidence"],
        "color": overall["color"],
        "reflection": "",
        "prompts": [],
        "vad": _standard_vad_from_mapping(overall),
        "acoustics": {"pitch_norm": 0.5, "energy_norm": abs(float(overall["arousal"]))},
        "text_emotion": text_emotion,
        "va_mapping": va_mapping,
    }


def normalize_design_for_mapping(design: dict, va_mapping: dict):
    style = _style_for_va_mapping(va_mapping)
    normalized = {}
    for key, value in design.items():
        char_style = dict(value)
        char_style["color"] = style["color"]
        char_style.setdefault("animation", style["animation"])
        normalized[key] = char_style
    return normalized


def build_segment_typography_design(text: str, va_mapping: dict):
    design = {}
    cursor = 0
    for segment in va_mapping.get("segments", []):
        segment_text = str(segment.get("text", "")).strip()
        if not segment_text:
            continue
        start = text.find(segment_text, cursor)
        if start == -1:
            start = text.find(segment_text)
        if start == -1:
            continue
        cursor = start + len(segment_text)
        style = _style_for_va_mapping(segment)
        segment_style = {
            "weight": 580,
            "scale": 1.06,
            "color": style["color"],
            "backgroundColor": style["color"],
            "animation": "float-drift" if segment.get("quadrant") == "neutral" else style["animation"],
        }
        for offset, char in enumerate(segment_text):
            if char.strip():
                design[str(start + offset)] = dict(segment_style)
    return design


def normalize_design_for_segments(design: dict, text: str, va_mapping: dict):
    segment_design = build_segment_typography_design(text, va_mapping)
    overall_style = _style_for_va_mapping(va_mapping.get("overall", {}))
    normalized = dict(segment_design)

    for key, value in design.items():
        base_style = dict(segment_design.get(key, {}))
        char_style = {**base_style, **dict(value)}
        mapper_color = base_style.get("color", overall_style["color"])
        char_style["color"] = mapper_color
        char_style["backgroundColor"] = base_style.get("backgroundColor", mapper_color)
        char_style.setdefault("animation", base_style.get("animation", overall_style["animation"]))
        normalized[key] = char_style

    return normalized


def apply_feedback_intensity(design: dict, intensity: float):
    safe_intensity = max(0.0, min(1.0, float(intensity)))
    adjusted = {}
    for key, value in design.items():
        char_style = dict(value)
        if "scale" in char_style:
            char_style["scale"] = 1 + (float(char_style["scale"]) - 1) * safe_intensity
        if safe_intensity < 0.35:
            char_style.pop("animation", None)
        adjusted[key] = char_style
    return adjusted


def get_demo_design_happy():
    """
    场景: "Oh my god, I just WON the big LOTTERY!" (长句)
    设计: SYSTEM B (POP ART) - 极度兴奋
    Emoji: 😄 (HAPPY)
    """
    # 句子索引参考:
    # "Oh my god, I just WON the big LOTTERY!"
    # WON: 16(W), 17(O), 18(N)
    # LOTTERY: 28(L), 29(O), 30(T), 31(T), 32(E), 33(R), 34(Y)
    
    return {
        # "Oh my god" - 预热
        "0": {"char": "O", "weight": 700, "scale": 1.2, "color": "#f472b6", "animation": "pulse-scale"}, # Pink
        
        # "WON" - 核心爆发点 1
        "16": {"char": "W", "weight": 900, "scale": 2.0, "color": "#facc15", "animation": "shake-hard"}, # Yellow
        "17": {"char": "O", "weight": 900, "scale": 2.5, "color": "#facc15", "animation": "shake-hard", "emoji": "HAPPY"}, # O -> 😄
        "18": {"char": "N", "weight": 900, "scale": 2.0, "color": "#facc15", "animation": "shake-hard"},

        # "LOTTERY" - 核心爆发点 2 (多彩)
        "28": {"char": "L", "weight": 900, "scale": 1.8, "color": "#fb923c", "animation": "pulse-scale"}, # Orange
        "29": {"char": "O", "weight": 900, "scale": 2.5, "color": "#fb923c", "animation": "pulse-scale", "emoji": "HAPPY"}, # O -> 😄
        "30": {"char": "T", "weight": 900, "scale": 1.8, "color": "#f472b6", "animation": "pulse-scale"}, # Pink
        "31": {"char": "T", "weight": 900, "scale": 1.8, "color": "#22d3ee", "animation": "pulse-scale"}, # Cyan
        "32": {"char": "E", "weight": 900, "scale": 1.8, "color": "#fb923c", "animation": "pulse-scale"},
        "33": {"char": "R", "weight": 900, "scale": 1.8, "color": "#f472b6", "animation": "pulse-scale"},
        "34": {"char": "Y", "weight": 900, "scale": 2.2, "color": "#facc15", "animation": "pulse-scale"}
    }

def get_demo_design_sad():
    """
    场景: "He left me." (短句)
    设计: SYSTEM C (ETHEREAL) - 孤独、下沉
    Emoji: 😭 (SAD)
    """
    # 句子索引:
    # "He left me."
    # left: 3,4,5,6
    # me: 8,9
    return {
        # "left" - 蓝色，下垂
        "3": {"char": "l", "weight": 300, "scale": 1.0, "color": "#64748b", "animation": "sad-droop"},
        "4": {"char": "e", "weight": 300, "scale": 1.0, "color": "#64748b", "animation": "sad-droop"},
        "5": {"char": "f", "weight": 300, "scale": 1.0, "color": "#64748b", "animation": "sad-droop"},
        "6": {"char": "t", "weight": 300, "scale": 1.0, "color": "#64748b", "animation": "sad-droop", "emoji": "HAPPY"},

        # "me" - 核心悲伤点
        "8": {"char": "m", "weight": 400, "scale": 1.2, "color": "#334155", "animation": "float-drift", "emoji": "SAD"},
        # 🔥 视觉双关: e -> SAD (😭)
        "9": {"char": "e", "weight": 400, "scale": 2.0, "color": "#334155", "animation": "sad-droop", "emoji": "SAD"} 
    }

# --- 拦截器逻辑更新 ---

def check_demo_triggers(text: str):
    """
    检查文本是否命中 Demo 关键词。
    """
    clean_text = text.lower().strip()
    
    # Scene 1: Happy / Lottery (Match "won" and "lottery")
    if "my" in clean_text and "god" in clean_text:
        print("🎯 DEMO TRIGGERED: HAPPY/LOTTERY Scenario")
        return get_demo_design_happy()
    
    # Scene 2: Sad / Breakup (Match "left me")
    if "left me" in clean_text:
        print("🎯 DEMO TRIGGERED: SAD/BREAKUP Scenario")
        return get_demo_design_sad()
        
    # # 保留之前的逻辑 (如果有的话)
    # if "literally" in clean_text and "dead" in clean_text:
    #     # ... (Previous DEAD logic)
    #     pass 

    return None


def call_llm_typography_design(text: str, vad: dict, acoustics: dict):
    """
    Acts as a Multimodal Art Director.
    Core Philosophy: SEMANTICS FIRST, ACOUSTICS SECOND.
    Even if the voice is flat, if the text is dramatic, the design MUST be dramatic.
    """
    
    # 我们不再在 Python 里预判 Vibe，而是把原始数据给 LLM，让它做多模态融合
    prompt = f"""
    You are "EmoType", an expert Kinetic Typography Art Director.
    Your challenge: The user's voice might be calm, but their words might be intense.
    **Your Goal**: Visualize the **MEANING** and **EMOTION** of the text, using the audio only as a hint for energy.

    ### 1. INPUT ANALYSIS
    - **Script (Text)**: "{text}"
    - **Audio Signal**: Valence={vad['valence']:.2f}, Arousal={vad['arousal']:.2f}, Energy={acoustics['energy_norm']:.2f}

    ### 2. THE "SEMANTIC DOMINANCE" RULE (CRITICAL)
    **Do NOT rely solely on Audio Energy.**
    - If the user whispers "I have a bomb", the word "BOMB" must still be **HUGE (Scale 3.0)** and **RED**, even if Energy is low.
    - If the user calmly says "This is amazing", the word "AMAZING" must be **Pop Art style**, regardless of the flat voice.
    - **Logic**: Text Semantics determines the *Design System*. Audio Acoustics determines the *Animation Speed*.

    ### 3. CHOOSE A DESIGN SYSTEM (Based on TEXT MEANING)
    
    🎨 **SYSTEM A: BRUTALIST (Anger, Stop, No, Hate, Urgent)**
    - *Look*: Ultra Bold (Weight 900), Tight spacing.
    - *Colors*: Magma Spectrum (#450a0a <-> #dc2626).
    - *Key Motion*: 'shake-hard' (Simmering rage or explosive yelling).
    
    🎨 **SYSTEM B: POP ART (Joy, Wow, Amazing, Cool, Fun)**
    - *Look*: Bouncy, Varied sizes.
    - *Colors*: Sunset/Neon Spectrum (#d97706 <-> #be185d).
    - *Key Motion*: 'pulse-scale' or 'float-drift'.

    🎨 **SYSTEM C: ETHEREAL (Sad, Lonely, Tired, Dream, Space)**
    - *Look*: Thin (Weight 300), Wide spacing.
    - *Colors*: Deep Sea Spectrum (#1e3a8a <-> #0f766e).
    - *Key Motion*: 'sad-droop' or 'float-drift'.

    🎨 **SYSTEM D: SKEUOMORPHIC (Object-Heavy)**
    - *Use when*: Text contains specific objects (Pizza, Time, Coffee).

    ### 4. VISUAL PUNS & EMOJI SCAN (MANDATORY)
    **Scan the text for concepts. If found, REPLACE the target letter with the specific EMOJI KEY.**
     Remeber: the "smile" can be “HAPPY” (😄), "sad" can be "SAD" (😭),

    **A. Visual Puns (Shape-based Replacement)**
    * **"TIME" / "LATE" / "NOW"** -> replace 'o'/'i' -> **CLOCK** (⏰)
    * **"PIZZA" / "FOOD"** -> replace 'A'/'i' -> **PIZZA** (🍕)
    * **"IDEA" / "LIGHT" / "SMART"** -> replace 'i'/'l' -> **BULB** (💡)
    * **"FIRE" / "HOT" / "LIT"** -> replace 'i'/'l' -> **FIRE** (🔥)
    * **"COFFEE" / "TEA" / "DRINK"** -> replace 'o'/'u' -> **CUP** (☕)
    * **"BOOM" / "BANG" / "EXPLODE"** -> replace 'o' -> **BOMB** (💣)
    * **"NIGHT" / "SLEEP" / "DARK"** -> replace 'o' -> **MOON** (🌕)
    * **"DAY" / "SUN" / "BRIGHT"** -> replace 'o' -> **SUN** (☀️)
    * **"GAME" / "SPORT" / "PLAY"** -> replace 'o' -> **BALL** (⚽)
    * **"SWEET" / "DONUT"** -> replace 'o' -> **DONUT** (🍩)
    * **"POOP" / "CRAP" / "SHIT"** -> replace 'o'/'A' -> **POOP** (💩)
    * **"SING" / "TALK" / "MUSIC"** -> replace 'i'/'l' -> **MIC** (🎤)
    * **"CAMP" / "OUT"** -> replace 'A' -> **TENT** (⛺)

    **B. Emotional & Character Replacement (Sentiment-based)**
    * **"HAPPY" / "HAHA" / "FUN"** -> replace 'a'/'o' -> **HAPPY** (😄)
    * **"SAD" / "CRY" / "NO"** -> replace 'o'/'a' -> **SAD** (😭)
    * **"ANGRY" / "MAD" / "HATE"** -> replace 'o'/'a' -> **ANGRY** (🤬)
    * **"LOVE" / "HEART" / "LIKE"** -> replace 'o'/'v' -> **LOVE** (😍)
    * **"COOL" / "CHILL"** -> replace 'o' -> **COOL** (😎)
    * **"JOKE" / "WINK" / "FLIRT"** -> replace 'i'/'o' -> **WINK** (😉)
    * **"WOW" / "OMG" / "SHOCK"** -> replace 'o' -> **SHOCK** (😱)
    * **"EWW" / "SICK" / "GROSS"** -> replace 'i'/'o' -> **SICK** (🤢)
    * **"DEAD" / "KILL" / "DYING"** -> replace 'e'/'a' -> **DEAD** (💀)
    * **"GHOST" / "SCARY"** -> replace 'o' -> **GHOST** (👻)
    * **"CLOWN" / "FOOL"** -> replace 'o' -> **CLOWN** (🤡)
    * **"ALIEN" / "WEIRD" / "SPACE"** -> replace 'i'/'a' -> **ALIEN** (👽)
    * **"MAGIC" / "STAR" / "AMAZING"** -> replace 'i'/'a' -> **STAR** (🤩)
    * **"SLEEP" / "TIRED" / "ZZZ"** -> replace 'e' -> **SLEEP** (😴)
    * **"THINK" / "HMM" / "WHY"** -> replace 'i'/'m' -> **THINK** (🤔)
    * **"WHAT" / "HUH" / "CONFUSED"** -> replace 'a'/'u' -> **CONFUSED** (😵‍💫)

    ### 5. EXECUTION GUIDELINES (Sparse Output)
    - **Baseline**: Weight 400, Scale 1.0, Color #374151. **OMIT DEFAULTS.**
    - **Spotlight**: Pick 2-4 keywords. 
      - Make them **Scale 2.5 - 3.0**.
      - Use **Highlight Colors**.
      - Apply **Animation**.

    ### REQUIRED JSON KEYS
    ["weight", "width", "scale", "slant", "color", "glow", "animation"] + (Optional "emoji")

    ### 6. To clearly and easy to read the message, YOU can not adjust every character.
    Focus on the KEYWORDS that carry the EMOTION and MEANING. Logically select 2-4 words to emphasize. 
    For the facial expression of the words, you can only choose from the EMOJIS provided above. 
   

    Example JSON ("I am so angry", whispered audio):
    {{
      "design": {{
        "8": {{ "char": "a", "weight": 900, "scale": 2.5, "color": "#7F1D1D", "animation": "shake-hard" }},
        "9": {{ "char": "n", "weight": 900, "scale": 2.5, "color": "#991B1B", "animation": "shake-hard" }},
        "10": {{ "char": "g", "weight": 900, "scale": 2.8, "color": "#DC2626", "animation": "shake-hard", "emoji": "ANGRY" }},
        "11": {{ "char": "r", "weight": 900, "scale": 2.5, "color": "#EF4444", "animation": "shake-hard" }},
        "12": {{ "char": "y", "weight": 900, "scale": 3.0, "color": "#B91C1C", "animation": "shake-hard" }}
      }}
    }}
    """

    try:
        headers = _llm_headers()
        if not headers:
            return build_fallback_typography_design(text, vad, acoustics)

        conn = http.client.HTTPSConnection(LLM_API_HOST, timeout=LLM_TIMEOUT_SECONDS)
        payload = json.dumps({
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a Semantic Typography Expert. You trust the text's meaning over the audio's volume."},
                {"role": "user", "content": prompt}
            ],
            # 🔥 0.75 温度，保证它敢于根据语义进行夸张设计
            "temperature": 0.75, 
            "response_format": { "type": "json_object" }
        })
        conn.request("POST", "/v1/chat/completions", payload, headers)
        res = conn.getresponse()
        data = res.read()
        
        response_json = json.loads(data.decode("utf-8"))
        content = response_json['choices'][0]['message']['content']
        
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()
            
        parsed_result = json.loads(content)
        
        if "design" in parsed_result:
            return parsed_result["design"]
        else:
            return parsed_result
        
    except Exception as e:
        print(f"LLM Call Failed: {e}")
        return build_fallback_typography_design(text, vad, acoustics)


import json
import http.client
import re

def call_llm_typography_design_2(text: str, vad: dict, acoustics: dict):
    """
    V7.1: Emoji Parsing Fix.
    Correctly maps 'emoji_key' from LLM to 'emoji' in frontend JSON.
    """
    
    # 1. 动态数量约束
    word_count = len(text.strip().split())
    if word_count <= 5:
        quantity_rule = "The text is SHORT. You must select EXACTLY ONE (1) keyword."
    else:
        quantity_rule = "Select 1 to 3 keywords."

    # 2. Prompt: 明确要求 emoji_key 字段
    prompt = f"""
    You are "EmoType", an expert Kinetic Typography Art Director.
    
    ### GOAL
    Analyze the script "{text}" and Audio VAD (Valence={vad['valence']:.2f}, Arousal={vad['arousal']:.2f}).
    Return a design configuration for the **Most Important Keywords**.

    ### STEP 1: SELECT KEYWORDS
    * **Constraint**: {quantity_rule}
    * Select words that carry the strongest emotion or imagery.

    ### STEP 2: DEFINE STYLE (Per Word)
    For each selected word, define:
    * **Weight**: High Arousal -> 800-900; Low -> 400-700.
    * **Scale**: High Energy -> 1.5-2.0; Low -> 1.3-2.0.
    * **Color**: 
        - Joy/Fun -> #F59E0B, #EC4899, #10B981
        - Anger/Urgent -> #DC2626, #7F1D1D
        - Sad/Ethereal -> #64748B, #475569, #1E3A8A
    * **Animation**: `shake-hard`, `pulse-scale`, `sad-droop`, `float-drift`

    ### STEP 3: EMOJI TARGETING
    If a word matches a visual pun, specify the **Target Letter** and **Emoji Key**.
    * **Triggers**:
      - HAPPY -> emoji_key: "HAPPY", target_char: "a"
      - SAD -> emoji_key: "SAD", target_char: "a"
      - LOVE -> emoji_key: "LOVE", target_char: "o"
      - FIRE -> emoji_key: "FIRE", target_char: "i"
      - DEAD -> emoji_key: "DEAD", target_char: "e"
      - PIZZA -> emoji_key: "PIZZA", target_char: "a"
      - TIME -> emoji_key: "CLOCK", target_char: "o"
      - POOP -> emoji_key: "POOP", target_char: "o"

    ### STEP 4: OUTPUT FORMAT (JSON)
    Return a list under the key "styled_words".
    
    **Example**: Text "I am so happy"
    {{
      "styled_words": [
        {{
          "word": "happy",
          "style": {{ "weight": 800, "scale": 1.5, "color": "#F59E0B", "animation": "pulse-scale" }},
          "emoji_data": {{ "emoji_key": "HAPPY", "target_char": "a" }} 
        }}
      ]
    }}
    """

    try:
        headers = _llm_headers()
        if not headers:
            return build_fallback_typography_design(text, vad, acoustics)

        conn = http.client.HTTPSConnection(LLM_API_HOST, timeout=LLM_TIMEOUT_SECONDS)
        payload = json.dumps({
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a JSON-only Kinetic Typography generator."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5, 
            "response_format": { "type": "json_object" }
        })
        conn.request("POST", "/v1/chat/completions", payload, headers)
        res = conn.getresponse()
        data = res.read()
        
        response_json = json.loads(data.decode("utf-8"))
        content = response_json['choices'][0]['message']['content']
        
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()
            
        llm_output = json.loads(content)
        
        # --- PYTHON POST-PROCESSING (修复版) ---
        
        final_design_map = {}
        original_text_lower = text.lower()
        
        if "styled_words" in llm_output:
            for item in llm_output["styled_words"]:
                target_word = item.get("word", "").lower()
                if not target_word: continue
                
                style = item.get("style", {})
                emoji_data = item.get("emoji_data", None)
                
                search_start_index = 0
                while True:
                    idx = original_text_lower.find(target_word, search_start_index)
                    if idx == -1:
                        break
                    
                    for i in range(len(target_word)):
                        global_char_index = str(idx + i)
                        current_char = target_word[i]
                        
                        char_style = {
                            "weight": style.get("weight", 400),
                            "scale": style.get("scale", 1.0),
                            "color": style.get("color", "#000000"),
                            "animation": style.get("animation", "")
                        }
                        
                        # 🔥 修复逻辑：正确读取 emoji_key
                        if emoji_data:
                            target_char_req = emoji_data.get("target_char", "").lower()
                            
                            # 优先读取 emoji_key，兼容可能读取 key 的情况
                            emoji_key_val = emoji_data.get("emoji_key") or emoji_data.get("key") or ""
                            
                            if current_char == target_char_req and emoji_key_val:
                                char_style["emoji"] = emoji_key_val
                        
                        final_design_map[global_char_index] = char_style
                    
                    break # 只处理第一个匹配词，避免过度渲染

        return final_design_map
        
    except Exception as e:
        print(f"LLM Call Failed: {e}")
        return build_fallback_typography_design(text, vad, acoustics)

def convert_webm_to_wav(webm_path: str) -> str:
    try:
        audio = AudioSegment.from_file(webm_path)
        audio = audio.set_frame_rate(TARGET_SR).set_channels(1)
        wav_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = wav_tmp.name
        wav_tmp.close()
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"Format conversion failed: {e}")
        raise e

def _read_audio_to_mono_16k(file_bytes: bytes) -> tuple[np.ndarray, str]:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(file_bytes)
        webm_path = tmp.name
    
    wav_path = None
    try:
        wav_path = convert_webm_to_wav(webm_path)
        wav, _ = librosa.load(wav_path, sr=TARGET_SR, mono=True)
        return wav, wav_path
    except Exception as e:
        if wav_path and os.path.exists(wav_path): os.remove(wav_path)
        raise HTTPException(status_code=400, detail=f"Audio processing failed: {str(e)}")
    finally:
        if os.path.exists(webm_path): os.remove(webm_path)

def extract_acoustic_features(wav_path: str):
    try:
        y, sr = librosa.load(wav_path, sr=TARGET_SR)
        f0, _, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
        avg_pitch = np.nanmean(f0) if not np.isnan(f0).all() else 0.0
        rms = librosa.feature.rms(y=y)
        avg_energy = np.mean(rms)

        norm_pitch = min(max((avg_pitch - 80) / 200, 0), 1) 
        norm_energy = min(max(avg_energy * 10, 0), 1)       

        return {
            "pitch_raw": float(avg_pitch),
            "pitch_norm": float(norm_pitch),
            "energy_raw": float(avg_energy),
            "energy_norm": float(norm_energy)
        }
    except Exception as e:
        print(f"Feature extraction warning: {e}")
        return {"pitch_norm": 0.5, "energy_norm": 0.5}

# -----------------------------
# Main Endpoint
# -----------------------------


def _storage_error(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


def _check_admin_token(admin_token: str | None, x_admin_token: str | None):
    token = admin_token or x_admin_token
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured.")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token.")


@app.post("/participants/session")
async def participant_session(payload: ParticipantSessionRequest):
    try:
        participant = get_or_create_participant(payload.participant_code, payload.consent_version)
        log_usage_event(payload.participant_code, "session_start", {"consent_version": payload.consent_version})
        return {"status": "success", "participant": participant}
    except Exception as error:
        raise _storage_error(error)


@app.get("/participants/{participant_code}/diaries")
async def participant_diaries(participant_code: str):
    try:
        return {"status": "success", "diary_entries": list_diary_entries(participant_code)}
    except Exception as error:
        raise _storage_error(error)


@app.post("/diaries")
async def save_diary_entry(payload: DiaryEntryRequest):
    try:
        payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        entry = create_diary_entry(payload.participant_code, payload_data)
        return {"status": "success", "diary_entry": entry}
    except Exception as error:
        raise _storage_error(error)


@app.post("/usage-events")
async def save_usage_event(payload: UsageEventRequest):
    try:
        event = log_usage_event(payload.participant_code, payload.event_type, payload.metadata_json)
        return {"status": "success", "usage_event": event}
    except Exception as error:
        raise _storage_error(error)


@app.get("/participants/{participant_code}/export.json")
async def participant_export_json(participant_code: str):
    try:
        log_usage_event(participant_code, "participant_export_json", {})
        return export_participant_data(participant_code)
    except Exception as error:
        raise _storage_error(error)


@app.get("/participants/{participant_code}/export.csv")
async def participant_export_csv(participant_code: str):
    try:
        log_usage_event(participant_code, "participant_export_csv", {})
        csv_text = export_participant_csv(participant_code)
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="emomirror-{participant_code}.csv"'},
        )
    except Exception as error:
        raise _storage_error(error)


@app.get("/admin/export.json")
async def admin_export_json(
    admin_token: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
):
    _check_admin_token(admin_token, x_admin_token)
    return export_all_data()


@app.get("/admin/export.csv")
async def admin_export_csv(
    admin_token: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
):
    _check_admin_token(admin_token, x_admin_token)
    return Response(
        content=export_all_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="emomirror-export.csv"'},
    )


# --- 3. 核心路由控制器 (Controller) ---

def process_typography_request(text: str, vad: dict, acoustics: dict):
    """
    排版设计主入口函数。
    逻辑：
    1. 先检查是否命中 Demo 预设的触发词 (0延迟，100%准确)。
    2. 如果没命中，再调用 LLM 生成 (高智能，但在演示时可能慢/不可控)。
    """
    
    # Step 1: 检查 Demo 拦截器
    print(f"🔍 Checking triggers for: '{text}'")
    demo_design = check_demo_triggers(text)
    
    if demo_design:
        print("⚡️ HIT: Returning Hardcoded Demo Design")
        return demo_design

    # Step 2: 如果不是 Demo 句子，兜底调用大模型
    # 注意：确保 call_llm_typography_design 函数在你的代码中已经定义
    print("🤖 MISS: Handing over to LLM...")
    # return call_llm_typography_design(text, vad, acoustics)
    return call_llm_typography_design_2(text, vad, acoustics)


@app.post("/analyze-text")
async def analyze_text(payload: TextAnalysisRequest):
    text = payload.text.strip()
    emotion = infer_text_emotion(text)
    va_mapping = emotion["va_mapping"]
    overall_mapping = va_mapping["overall"]
    design = {}
    if text:
        design = process_typography_request(text, emotion["vad"], emotion["acoustics"])
        design = normalize_design_for_segments(design, text, va_mapping)
        design = apply_feedback_intensity(design, payload.intensity)

    return {
        "status": "success",
        "emotion": {
            "primary": emotion["primary"],
            "key": emotion["key"],
            "secondary": emotion["secondary"],
            "confidence": emotion["confidence"],
            "color": emotion["color"],
            "reflection": emotion["reflection"],
            "prompts": emotion["prompts"],
        },
        "vad": emotion["vad"],
        "acoustics": emotion["acoustics"],
        "text_emotion": emotion["text_emotion"],
        "va_mapping": va_mapping,
        "llm_design": design,
    }


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    text: str = Form(""), 
    return_embeddings: bool = Query(False),
):
    wav_path = None
    try:
        raw = await file.read()
        if len(raw) == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # 1. 音频处理
        wav_arr, wav_path = _read_audio_to_mono_16k(raw)

        if processor is None or model is None:
            raise HTTPException(status_code=503, detail="Emotion model is not loaded")
        
        # 2. VAD 推理 (Valence / Arousal / Dominance)
        inputs = processor(wav_arr[None, :], sampling_rate=TARGET_SR, return_tensors="pt")
        x = inputs["input_values"].to(device)
        with torch.inference_mode():
            pooled_states, logits = model(x)
            vad_scores = logits.detach().cpu().numpy()[0]
            embeddings_vec = pooled_states.detach().cpu().numpy()[0]
        
        vad_dict = {
            "arousal": float(vad_scores[0]),
            "dominance": float(vad_scores[1]),
            "valence": float(vad_scores[2]),
        }
        vad_standard = normalize_vad(vad_dict, source_range=VAD_SOURCE_RANGE)
        overall_mapping = map_va(vad_standard["valence"], vad_standard["arousal"])

        # 3. 声学特征提取 (Pitch, Energy)
        acoustics = extract_acoustic_features(wav_path)
        segment_inputs = [
            {
                "text": segment,
                "valence": vad_standard["valence"],
                "arousal": vad_standard["arousal"],
                "confidence": overall_mapping["confidence"],
            }
            for segment in split_text_segments(text)
        ]
        va_mapping = (
            map_segments(segment_inputs)
            if segment_inputs
            else {"segments": [], "overall": overall_mapping}
        )

        # 4. 🔥 视觉设计生成 (Demo 拦截 -> LLM)
        llm_design = {}
        if text and text.strip():
            print(f"🎨 Processing Request: '{text}' | VAD: {vad_dict}")
            
            # --- 关键修改：调用新的主控函数 ---
            # 这个函数会先检查是否命中 "won lottery", "left me" 等 Demo 关键词
            # 如果命中，直接返回预设 JSON；没命中才去调大模型。
            llm_design = process_typography_request(text, vad_standard, acoustics)
            llm_design = normalize_design_for_segments(llm_design, text, va_mapping)
            print(f"LLM Design: {llm_design}")
            
            print(f"✅ Design Generated. Keys: {list(llm_design.keys()) if llm_design else 'None'}")

        # 5. 构造响应
        response = {
            "vad": vad_dict,
            "vad_normalized": vad_standard,
            "acoustics": acoustics,
            "va_mapping": va_mapping,
            "llm_design": llm_design, 
            "status": "success"
        }

        if return_embeddings:
            response["embeddings"] = embeddings_vec.tolist()

        print("🚀 Prediction completed.", response)

        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if wav_path and os.path.exists(wav_path):
            try: os.remove(wav_path)
            except: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
