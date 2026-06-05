import io
import os
import json
import tempfile
from datetime import date as date_cls, timedelta
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from fastapi import Response, FastAPI, UploadFile, File, Form, Header, Query, HTTPException
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
    from emotion_rec import llm_client
    from emotion_rec.storage import (
        create_diary_entry,
        export_all_csv,
        export_all_data,
        export_participant_csv,
        export_participant_data,
        get_emotion_review_report,
        get_formal_diary_by_date,
        get_or_create_participant,
        get_review_overview,
        get_review_overview_all,
        init_database,
        list_records,
        list_records_all,
        list_diary_context,
        list_diary_entries,
        log_usage_event,
        normalize_diary_date,
        normalize_review_range,
        review_period_type,
        update_formal_diary_reflection,
        upsert_emotion_review_report,
        upsert_formal_diary_by_date,
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
    import llm_client  # type: ignore
    from storage import (  # type: ignore
        create_diary_entry,
        export_all_csv,
        export_all_data,
        export_participant_csv,
        export_participant_data,
        get_emotion_review_report,
        get_formal_diary_by_date,
        get_or_create_participant,
        get_review_overview,
        get_review_overview_all,
        init_database,
        list_records,
        list_records_all,
        list_diary_context,
        list_diary_entries,
        log_usage_event,
        normalize_diary_date,
        normalize_review_range,
        review_period_type,
        update_formal_diary_reflection,
        upsert_emotion_review_report,
        upsert_formal_diary_by_date,
    )

# -----------------------------
# LLM Configuration
# -----------------------------
# All LLM traffic goes through emotion_rec/llm_client.py, which uses the OpenAI
# SDK pointed at DeepSeek. Configure via DEEPSEEK_API_KEY/DEEPSEEK_MODEL, or the
# legacy LLM_API_KEY/LLM_MODEL aliases. Default model is deepseek-v4-flash.
try:
    LLM_TYPOGRAPHY_TEMPERATURE = float(os.getenv("LLM_TYPOGRAPHY_TEMPERATURE", "0.6"))
except ValueError:
    LLM_TYPOGRAPHY_TEMPERATURE = 0.6
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


@app.head("/", include_in_schema=False)
async def index_head():
    return Response(status_code=200, media_type="text/html")


@app.get("/diary", include_in_schema=False)
async def diary_page():
    return FileResponse(STATIC_DIR / "diary.html")


@app.head("/diary", include_in_schema=False)
async def diary_page_head():
    return Response(status_code=200, media_type="text/html")


@app.get("/review", include_in_schema=False)
async def review_page():
    return FileResponse(STATIC_DIR / "review.html")


@app.head("/review", include_in_schema=False)
async def review_page_head():
    return Response(status_code=200, media_type="text/html")


@app.get("/records", include_in_schema=False)
@app.get("/history", include_in_schema=False)
async def records_page():
    return FileResponse(STATIC_DIR / "records.html")


@app.head("/records", include_in_schema=False)
@app.head("/history", include_in_schema=False)
async def records_page_head():
    return Response(status_code=200, media_type="text/html")

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


class FormalDiaryUpsertRequest(BaseModel):
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)
    title: str = Field(default="", max_length=240)
    content: str = Field(default="", max_length=50000)
    physical_weather: str = Field(default="sunny", max_length=16)
    mood_weather: str = Field(default="sunny", max_length=16)
    source_entry_ids_json: list = Field(default_factory=list)
    save_type: str = Field(default="autosave", max_length=20)
    auto_analyze: bool = False
    is_draft: bool | None = None


class DiaryReflectRequest(BaseModel):
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)


class ReviewReflectRequest(BaseModel):
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)
    start_date: str = Field(..., max_length=10)
    end_date: str = Field(..., max_length=10)


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


def _strip_llm_content(content: str) -> str:
    return llm_client.strip_content(content)


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


DIARY_WEATHER_VALUES = {"sunny", "cloudy", "overcast", "rainy", "stormy", "snowy", "windy", "foggy"}
DIARY_WEATHER_LABELS = {
    "sunny": "晴朗",
    "cloudy": "多云",
    "overcast": "阴天",
    "rainy": "下雨",
    "stormy": "暴风雨",
    "snowy": "下雪",
    "windy": "有风",
    "foggy": "有雾",
}
DIARY_ANALYSIS_VERSION = "diary-reflection-v1"


def _diary_participant_code(participant_code: str | None) -> str:
    return (participant_code or "local").strip() or "local"


def _validate_diary_weather(value: str, field_name: str) -> str:
    weather = str(value or "sunny").strip().lower()
    if weather not in DIARY_WEATHER_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be one of: {', '.join(sorted(DIARY_WEATHER_VALUES))}.",
        )
    return weather


def _diary_color_name(va_mapping: dict) -> str:
    names = {
        "high_positive": "明亮暖色",
        "low_positive": "柔和浅绿",
        "high_negative": "红紫高能量",
        "low_negative": "蓝灰低能量",
        "neutral": "雾灰中性",
    }
    return names.get(va_mapping.get("quadrant"), names["neutral"])


def _json_from_llm_content(content: str) -> dict | None:
    content = _strip_llm_content(content)
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _safe_list(value, limit: int = 8) -> list:
    def normalize_item(item):
        if isinstance(item, dict):
            item = (
                item.get("label")
                or item.get("name")
                or item.get("emotion")
                or item.get("question")
                or item.get("text")
                or item.get("summary")
            )
        text_value = str(item or "").strip()
        return text_value or None

    if isinstance(value, list):
        normalized = [normalize_item(item) for item in value]
        return [item for item in normalized if item][:limit]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _diary_body_signals(text: str, text_emotion: dict, raw_signals=None) -> list[str]:
    signals = [str(item).strip() for item in _safe_list(raw_signals, 8) if str(item).strip()]
    seen = set(signals)
    body_terms = [
        "胸口", "心慌", "心跳", "喉咙", "胃", "肚子", "头疼", "头痛", "头晕",
        "肩颈", "紧绷", "疲惫", "乏力", "睡不着", "出汗", "手抖", "呼吸",
    ]
    for term in body_terms:
        if term in text and term not in seen:
            seen.add(term)
            signals.append(term)
    for segment in text_emotion.get("segments", []) if isinstance(text_emotion, dict) else []:
        for evidence in segment.get("evidence", []) or []:
            evidence_text = str(evidence)
            if "身体" in evidence_text and evidence_text not in seen:
                seen.add(evidence_text)
                signals.append(evidence_text)
    return signals[:8]


def _diary_text_preview(text: str, fallback: str = "今天的日记内容还不多。") -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return fallback
    first = re.split(r"[。！？!?\n]", clean, maxsplit=1)[0].strip() or clean
    return first[:180] + ("..." if len(first) > 180 else "")


def _build_diary_emotion_context(content: str) -> dict:
    text_emotion = analyze_text_emotion(content)
    va_mapping = map_segments(text_emotion.get("segments", []))
    overall = va_mapping.get("overall") or map_va(0.0, 0.0, 0.0)
    candidate_emotions = [
        item.get("label")
        for item in overall.get("candidates", [])
        if isinstance(item, dict) and item.get("label")
    ]
    return {
        "text_emotion": text_emotion,
        "va_mapping": va_mapping,
        "overall": overall,
        "primary_emotion": overall.get("label", "中性"),
        "candidate_emotions": candidate_emotions[:8],
        "valence": float(overall.get("valence", 0.0)),
        "arousal": float(overall.get("arousal", 0.0)),
        "confidence": float(overall.get("confidence", 0.0)),
        "emotion_color": overall.get("color", "#94A3B8"),
        "emotion_color_name": _diary_color_name(overall),
    }


def _filter_diary_context_for_sources(context_items: list[dict], source_ids: list) -> list[dict]:
    if not source_ids:
        return context_items
    selected = {str(item) for item in source_ids}
    filtered = []
    for item in context_items:
        key = f"{item.get('source')}:{item.get('id')}"
        if key in selected or str(item.get("id")) in selected:
            filtered.append(item)
    return filtered or context_items


def _fallback_diary_reflection(diary: dict, emotion_context: dict, context_items: list[dict]) -> dict:
    overall = emotion_context.get("overall", {})
    primary = emotion_context.get("primary_emotion") or overall.get("label") or "中性"
    candidates = [label for label in emotion_context.get("candidate_emotions", []) if label and label != primary]
    physical = diary.get("physical_weather") or "sunny"
    mood = diary.get("mood_weather") or "sunny"
    physical_label = DIARY_WEATHER_LABELS.get(physical, physical)
    mood_label = DIARY_WEATHER_LABELS.get(mood, mood)
    context_hint = ""
    if context_items:
        context_hint = f" 今天还参考了 {len(context_items)} 条随手记或身体感受素材。"

    return {
        "event_summary": _diary_text_preview(diary.get("content", "")),
        "gentle_reflection": (
            f"看起来，今天更靠近“{primary}”这类感受。{context_hint}"
            "这里的复盘只是帮你把线索放在一起看，不急着给它下结论。"
        ),
        "primary_emotion": primary,
        "secondary_emotions": candidates[:4],
        "fine_grained_emotions": candidates[:5],
        "body_signals": _diary_body_signals(diary.get("content", ""), emotion_context.get("text_emotion", {})),
        "valence": float(emotion_context.get("valence", 0.0)),
        "arousal": float(emotion_context.get("arousal", 0.0)),
        "emotion_color": emotion_context.get("emotion_color") or overall.get("color") or "#94A3B8",
        "emotion_color_name": emotion_context.get("emotion_color_name") or _diary_color_name(overall),
        "weather_reflection": (
            f"现实天气是{physical_label}，心情天气是{mood_label}。天气可以作为背景被看见，"
            "但不需要把今天的情绪强行归因到天气上。"
        ),
        "possible_trigger": "可能和今天反复出现的事件、关系、任务或身体消耗有关；还需要你自己的感受来确认。",
        "possible_need": "也许需要一点停顿、被理解，或把今天最耗力的部分从脑子里放下来。",
        "reflection_questions": [
            "今天哪一刻最明显地改变了你的情绪天气？",
            "有没有一个感受，是你写完以后才发现它一直在？",
            "如果只保留一个小需求，它会是什么？",
        ],
        "small_action_suggestion": "可以先离开屏幕两分钟，喝一点水，把今天最重的一件事用一句话写在旁边。",
    }


def _normalize_diary_reflection(raw: dict | None, diary: dict, emotion_context: dict, context_items: list[dict]) -> dict:
    fallback = _fallback_diary_reflection(diary, emotion_context, context_items)
    raw = raw if isinstance(raw, dict) else {}
    result = dict(fallback)
    for key in (
        "event_summary", "gentle_reflection", "weather_reflection", "possible_trigger",
        "possible_need", "small_action_suggestion",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()

    for key in ("secondary_emotions", "fine_grained_emotions", "reflection_questions"):
        values = _safe_list(raw.get(key), 8)
        if values:
            result[key] = values

    body_signals = _diary_body_signals(diary.get("content", ""), emotion_context.get("text_emotion", {}), raw.get("body_signals"))
    if body_signals:
        result["body_signals"] = body_signals

    overall = emotion_context.get("overall", {})
    result["primary_emotion"] = emotion_context.get("primary_emotion") or overall.get("label") or result["primary_emotion"]
    result["valence"] = float(emotion_context.get("valence", overall.get("valence", 0.0)))
    result["arousal"] = float(emotion_context.get("arousal", overall.get("arousal", 0.0)))
    result["emotion_color"] = emotion_context.get("emotion_color") or overall.get("color") or "#94A3B8"
    result["emotion_color_name"] = emotion_context.get("emotion_color_name") or _diary_color_name(overall)
    return result


def _call_diary_reflection_llm(diary: dict, emotion_context: dict, context_items: list[dict]) -> dict | None:
    if not llm_client.llm_enabled():
        return None

    model_name = os.getenv("DIARY_REFLECTION_LLM_MODEL", "").strip() or None
    try:
        temperature = float(os.getenv("DIARY_REFLECTION_LLM_TEMPERATURE", "0.18"))
    except ValueError:
        temperature = 0.18
    try:
        max_tokens = int(os.getenv("DIARY_REFLECTION_LLM_MAX_TOKENS", "4096"))
    except ValueError:
        max_tokens = 4096

    system_prompt = """你是 EmoBridge 的正式日记复盘助手，不是诊断系统。
你的任务是基于用户写完的一天日记、当天可参考的随手记/身体感受素材、现实天气和心情天气，生成温柔、克制、结构化的复盘。

规则：
- 只输出合法 JSON，不要 Markdown，不要 <think>。
- 不要使用诊断式语言，不要说“你就是焦虑/抑郁/有问题”。
- 多使用“可能”“看起来”“也许”“更像是”。
- 不要强行解释用户，也不要强行把情绪归因于天气。
- 天气只能作为背景线索，不能被写成情绪原因。
- valence、arousal、primary_emotion 已由系统的文本情绪识别给出，你可以参考，但不要另写一套分类逻辑。
- emotion_color 由系统代码统一映射；如果你输出颜色，后端也会用系统颜色覆盖。

必须输出这些顶层字段：
event_summary, gentle_reflection, primary_emotion, secondary_emotions, fine_grained_emotions, body_signals, valence, arousal, emotion_color, emotion_color_name, weather_reflection, possible_trigger, possible_need, reflection_questions, small_action_suggestion。"""

    user_payload = {
        "diary": {
            "date": diary.get("diary_date"),
            "title": diary.get("title"),
            "content": diary.get("content"),
            "physical_weather": diary.get("physical_weather"),
            "physical_weather_label": DIARY_WEATHER_LABELS.get(diary.get("physical_weather"), diary.get("physical_weather")),
            "mood_weather": diary.get("mood_weather"),
            "mood_weather_label": DIARY_WEATHER_LABELS.get(diary.get("mood_weather"), diary.get("mood_weather")),
        },
        "emotion_context_from_system": {
            "valence": emotion_context.get("valence"),
            "arousal": emotion_context.get("arousal"),
            "primary_emotion": emotion_context.get("primary_emotion"),
            "candidate_emotions": emotion_context.get("candidate_emotions"),
            "confidence": emotion_context.get("confidence"),
            "emotion_color": emotion_context.get("emotion_color"),
            "emotion_color_name": emotion_context.get("emotion_color_name"),
        },
        "context_records": context_items[:12],
        "output_schema": {
            "event_summary": "string",
            "gentle_reflection": "string",
            "primary_emotion": "string",
            "secondary_emotions": [],
            "fine_grained_emotions": [],
            "body_signals": [],
            "valence": -0.5,
            "arousal": 0.7,
            "emotion_color": "#xxxxxx",
            "emotion_color_name": "string",
            "weather_reflection": "string",
            "possible_trigger": "string",
            "possible_need": "string",
            "reflection_questions": [],
            "small_action_suggestion": "string",
        },
    }

    try:
        parsed = llm_client.chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parsed if isinstance(parsed, dict) else None
    except Exception as error:
        print(f"[diary] reflection LLM skipped: {error}")
        return None


REVIEW_ANALYSIS_VERSION = "emotion-review-v1"


def _review_default_dates() -> tuple[str, str]:
    end = date_cls.today()
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _review_participant_code(participant_code: str | None) -> str:
    return _diary_participant_code(participant_code)


def _review_soften_text(text: str) -> str:
    softened = str(text or "")
    replacements = {
        "你就是焦虑": "你可能正在经历一些不安和紧绷",
        "你就是抑郁": "这段时间看起来可能有些低落",
        "你很焦虑": "你可能有些不安",
        "你很抑郁": "你可能有些低落",
        "你有焦虑症": "你可能有一些持续的不安感",
        "你有抑郁症": "你可能有一些持续的低落感",
        "焦虑症": "不安感",
        "抑郁症": "持续低落感",
    }
    for source, target in replacements.items():
        softened = softened.replace(source, target)
    return softened.strip()


def _review_soften_json(value):
    if isinstance(value, dict):
        return {key: _review_soften_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_review_soften_json(item) for item in value]
    if isinstance(value, str):
        return _review_soften_text(value)
    return value


def _review_named_notes(value, fallback_labels: list[dict] | None = None, limit: int = 6) -> list[dict]:
    notes = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("emotion") or item.get("name") or "").strip()
                note = str(item.get("note") or item.get("summary") or item.get("description") or "").strip()
            else:
                label = str(item or "").strip()
                note = ""
            if label:
                notes.append({"label": label, "note": _review_soften_text(note)})
            if len(notes) >= limit:
                break
    if notes:
        return notes
    return (fallback_labels or [])[:limit]


def _fallback_review_reflection(stats: dict) -> dict:
    total = int(stats.get("total_records") or 0)
    top_primary = (stats.get("primary_emotions") or [])[:3]
    top_fine = (stats.get("fine_emotions") or [])[:5]
    top_triggers = (stats.get("triggers") or [])[:5]
    top_body = (stats.get("body_signals") or [])[:5]
    top_colors = (stats.get("colors") or [])[:4]
    primary_text = "、".join(item.get("label", "") for item in top_primary if item.get("label")) or "尚不明显的情绪"
    trigger_text = "、".join(item.get("label", "") for item in top_triggers if item.get("label")) or "日常事件和身体状态"
    body_text = "、".join(item.get("label", "") for item in top_body if item.get("label")) or "暂时不明显"

    return {
        "period_summary": (
            f"{stats.get('start_date')} 到 {stats.get('end_date')} 之间共整理到 {total} 条记录。"
            f"看起来，这段时间较常出现的情绪线索包括“{primary_text}”。"
        ),
        "emotional_pattern": (
            "这些结果更像是一组阶段性线索，而不是定论。"
            "你可以先观察哪些情绪反复出现、哪些日子能量更高或更低。"
        ),
        "color_story": (
            "颜色色板显示了这段时间情绪落点的分布。"
            + (f"较常出现的颜色有 {len(top_colors)} 种，可以把它们当作情绪天气的提示。" if top_colors else "目前颜色样本还不多。")
        ),
        "main_emotions": [
            {
                "label": item.get("label"),
                "note": f"出现 {item.get('count')} 次，可能是这段时间较容易被记录下来的感受。",
            }
            for item in top_primary
        ],
        "fine_grained_emotions": [item.get("label") for item in top_fine if item.get("label")],
        "possible_triggers": [
            f"{item.get('label')}：可能和这段时间反复出现的事件或背景有关。"
            for item in top_triggers
        ] or [f"可能和{trigger_text}有关，但还需要结合你自己的感受确认。"],
        "body_signal_summary": f"身体信号里较常被看见的是：{body_text}。这些只是身体线索，不等同于医学判断。",
        "gentle_observations": [
            "看起来，把随手记、正式日记和身体感受放在一起后，情绪变化会比单条记录更容易被看见。",
            "也许可以留意：哪些事件之后 V-A 坐标更容易偏向高能量，哪些时段更容易变低。",
        ],
        "reflection_questions": [
            "这段时间哪一天的情绪转折最明显？",
            "有没有一种感受，其实是通过身体信号先出现的？",
            "如果只照顾一个最常出现的需求，它可能是什么？",
        ],
        "small_steps": [
            "选一条最有代表性的记录，补一句当时真正需要什么。",
            "给高能量或低能量的日子各标一个关键词，看看它们是否有共同背景。",
        ],
        "non_diagnostic_note": "这份复盘只是帮助整理线索，不用于诊断，也不能替代专业支持。",
    }


def _normalize_review_reflection(raw: dict | None, stats: dict) -> dict:
    fallback = _fallback_review_reflection(stats)
    raw = _review_soften_json(raw if isinstance(raw, dict) else {})
    result = dict(fallback)

    for key in (
        "period_summary",
        "emotional_pattern",
        "color_story",
        "body_signal_summary",
        "non_diagnostic_note",
    ):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = _review_soften_text(value)

    result["main_emotions"] = _review_named_notes(raw.get("main_emotions"), fallback["main_emotions"], 6)

    for key in (
        "fine_grained_emotions",
        "possible_triggers",
        "gentle_observations",
        "reflection_questions",
        "small_steps",
    ):
        values = _safe_list(raw.get(key), 8)
        if values:
            result[key] = [_review_soften_text(item) for item in values]

    return _review_soften_json(result)


def _call_review_reflection_llm(stats: dict) -> dict | None:
    if not llm_client.llm_enabled():
        return None

    model_name = os.getenv("REVIEW_REFLECTION_LLM_MODEL", "").strip() or None
    try:
        temperature = float(os.getenv("REVIEW_REFLECTION_LLM_TEMPERATURE", "0.2"))
    except ValueError:
        temperature = 0.2
    try:
        max_tokens = int(os.getenv("REVIEW_REFLECTION_LLM_MAX_TOKENS", "4096"))
    except ValueError:
        max_tokens = 4096

    system_prompt = """你是 EmoBridge 的阶段性情绪复盘助手，不是诊断系统。
你的任务是基于一段日期范围内的随手记、正式日记、身体感受、V-A 坐标和情绪颜色，生成温柔、克制、结构化的阶段性复盘。

规则：
- 只输出合法 JSON，不要 Markdown，不要 <think>。
- 不要使用诊断式语言，不要说“你就是焦虑/抑郁/有问题”。
- 多使用“可能”“看起来”“也许”“更像是”。
- 不要把统计相关写成因果定论。
- 身体信号只能作为线索，不能写成医学判断。
- 不要建议用户停止用药、不要做医疗诊断。

必须输出这些顶层字段：
period_summary, emotional_pattern, color_story, main_emotions, fine_grained_emotions, possible_triggers, body_signal_summary, gentle_observations, reflection_questions, small_steps, non_diagnostic_note。

main_emotions 必须是对象数组，每个对象包含 label 和 note。其余列表字段输出字符串数组。"""

    compact_stats = {
        "participant_code": stats.get("participant_code"),
        "start_date": stats.get("start_date"),
        "end_date": stats.get("end_date"),
        "total_records": stats.get("total_records"),
        "source_counts": stats.get("source_counts"),
        "averages": stats.get("averages"),
        "days": stats.get("days"),
        "colors": stats.get("colors", [])[:12],
        "primary_emotions": stats.get("primary_emotions", [])[:12],
        "fine_emotions": stats.get("fine_emotions", [])[:16],
        "triggers": stats.get("triggers", [])[:12],
        "body_signals": stats.get("body_signals", [])[:12],
        "records": stats.get("records", [])[-60:],
    }

    try:
        parsed = llm_client.chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(compact_stats, ensure_ascii=False)},
            ],
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parsed if isinstance(parsed, dict) else None
    except Exception as error:
        print(f"[review] reflection LLM skipped: {error}")
        return None


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
        if not llm_client.llm_enabled():
            return build_fallback_typography_design(text, vad, acoustics)

        parsed_result = llm_client.chat_json(
            [
                {"role": "system", "content": "You are a Semantic Typography Expert. You trust the text's meaning over the audio's volume."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.75,
            max_tokens=2048,
        )

        if not isinstance(parsed_result, dict):
            return build_fallback_typography_design(text, vad, acoustics)

        if "design" in parsed_result:
            return parsed_result["design"]
        return parsed_result
        
    except Exception as e:
        print(f"LLM Call Failed: {e}")
        return build_fallback_typography_design(text, vad, acoustics)


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
        if not llm_client.llm_enabled():
            return build_fallback_typography_design(text, vad, acoustics)

        llm_output = llm_client.chat_json(
            [
                {"role": "system", "content": "You are a JSON-only Kinetic Typography generator."},
                {"role": "user", "content": prompt},
            ],
            temperature=LLM_TYPOGRAPHY_TEMPERATURE,
            max_tokens=2048,
        )

        if not isinstance(llm_output, dict):
            return build_fallback_typography_design(text, vad, acoustics)
        
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


def _check_api_admin_token(admin_token: str | None, x_admin_token: str | None):
    token = admin_token or x_admin_token
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN is not configured.")
    if not token:
        raise HTTPException(status_code=401, detail="Admin token is required.")
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



@app.get("/api/diary")
async def get_diary_by_date(
    date: str = Query(..., description="Diary date in YYYY-MM-DD"),
    participant_code: str | None = Query(default=None),
):
    try:
        diary_date = normalize_diary_date(date)
        code = _diary_participant_code(participant_code)
        return {"status": "success", "diary": get_formal_diary_by_date(code, diary_date)}
    except Exception as error:
        raise _storage_error(error)


@app.get("/api/diary/context")
async def get_diary_context_by_date(
    date: str = Query(..., description="Diary date in YYYY-MM-DD"),
    participant_code: str | None = Query(default=None),
):
    try:
        diary_date = normalize_diary_date(date)
        code = _diary_participant_code(participant_code)
        records = list_diary_context(code, diary_date)
        return {"status": "success", "date": diary_date, "records": records}
    except Exception as error:
        raise _storage_error(error)


@app.put("/api/diary/by-date/{diary_date}")
async def put_diary_by_date(diary_date: str, payload: FormalDiaryUpsertRequest):
    try:
        date_text = normalize_diary_date(diary_date)
        payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        payload_data["physical_weather"] = _validate_diary_weather(payload_data.get("physical_weather"), "physical_weather")
        payload_data["mood_weather"] = _validate_diary_weather(payload_data.get("mood_weather"), "mood_weather")
        code = _diary_participant_code(payload_data.pop("participant_code", None))
        diary = upsert_formal_diary_by_date(code, date_text, payload_data)
        return {
            "status": "success",
            "save_type": payload_data.get("save_type", "autosave"),
            "auto_analyze": False,
            "diary": diary,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise _storage_error(error)


@app.post("/api/diary/by-date/{diary_date}/reflect")
async def reflect_diary_by_date(diary_date: str, payload: DiaryReflectRequest | None = None):
    try:
        date_text = normalize_diary_date(diary_date)
        code = _diary_participant_code(payload.participant_code if payload else None)
        diary = get_formal_diary_by_date(code, date_text)
        content = str(diary.get("content") or "")
        if not content.strip():
            raise HTTPException(status_code=400, detail="Diary content is empty.")
        emotion_context = _build_diary_emotion_context(content)
        context_items = list_diary_context(code, date_text)
        context_items = _filter_diary_context_for_sources(context_items, diary.get("source_entry_ids_json") or [])
        llm_reflection = _call_diary_reflection_llm(diary, emotion_context, context_items)
        reflection = _normalize_diary_reflection(llm_reflection, diary, emotion_context, context_items)
        saved_diary = update_formal_diary_reflection(
            code,
            date_text,
            {
                "valence": reflection["valence"],
                "arousal": reflection["arousal"],
                "primary_emotion": reflection["primary_emotion"],
                "secondary_emotions_json": reflection.get("secondary_emotions", []),
                "fine_emotions_json": reflection.get("fine_grained_emotions", []),
                "body_signals_json": reflection.get("body_signals", []),
                "emotion_color": reflection["emotion_color"],
                "emotion_color_name": reflection["emotion_color_name"],
                "reflection_json": reflection,
                "analysis_version": DIARY_ANALYSIS_VERSION,
                "is_draft": False,
            },
        )
        return {
            "status": "success",
            "diary": saved_diary,
            "reflection": reflection,
            "text_emotion": emotion_context.get("text_emotion"),
            "va_mapping": emotion_context.get("va_mapping"),
            "context_records_used": context_items,
            "llm_used": isinstance(llm_reflection, dict),
        }
    except HTTPException:
        raise
    except Exception as error:
        raise _storage_error(error)


@app.get("/api/review/overview")
async def review_overview(
    start_date: str | None = Query(default=None, description="Start date in YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="End date in YYYY-MM-DD"),
    participant_code: str | None = Query(default=None),
):
    try:
        default_start, default_end = _review_default_dates()
        start_text, end_text = normalize_review_range(start_date or default_start, end_date or default_end)
        code = _review_participant_code(participant_code)
        stats = get_review_overview(code, start_text, end_text)
        return {
            "status": "success",
            "participant_code": code,
            "start_date": start_text,
            "end_date": end_text,
            "period_type": review_period_type(start_text, end_text),
            "stats": stats,
        }
    except Exception as error:
        raise _storage_error(error)


@app.get("/api/review/report")
async def review_report(
    start_date: str | None = Query(default=None, description="Start date in YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="End date in YYYY-MM-DD"),
    participant_code: str | None = Query(default=None),
):
    try:
        default_start, default_end = _review_default_dates()
        start_text, end_text = normalize_review_range(start_date or default_start, end_date or default_end)
        code = _review_participant_code(participant_code)
        report = get_emotion_review_report(
            code,
            start_text,
            end_text,
            review_period_type(start_text, end_text),
        )
        return {
            "status": "success",
            "participant_code": code,
            "start_date": start_text,
            "end_date": end_text,
            "report": report,
        }
    except Exception as error:
        raise _storage_error(error)


@app.post("/api/review/reflect")
async def review_reflect(payload: ReviewReflectRequest):
    try:
        payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        start_text, end_text = normalize_review_range(payload_data.get("start_date"), payload_data.get("end_date"))
        code = _review_participant_code(payload_data.get("participant_code"))
        period = review_period_type(start_text, end_text)
        stats = get_review_overview(code, start_text, end_text)
        llm_report = _call_review_reflection_llm(stats)
        report_json = _normalize_review_reflection(llm_report, stats)
        saved_report = upsert_emotion_review_report(
            code,
            start_text,
            end_text,
            period,
            stats,
            report_json,
            REVIEW_ANALYSIS_VERSION,
        )
        return {
            "status": "success",
            "participant_code": code,
            "start_date": start_text,
            "end_date": end_text,
            "period_type": period,
            "stats": stats,
            "report": saved_report,
            "report_json": report_json,
            "llm_used": isinstance(llm_report, dict),
        }
    except Exception as error:
        raise _storage_error(error)


@app.get("/api/records")
async def records_api(
    participant_code: str | None = Query(default=None),
    start_date: str | None = Query(default=None, description="Start date in YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="End date in YYYY-MM-DD"),
    source: str = Query(default="all"),
):
    try:
        default_start, default_end = _review_default_dates()
        start_text, end_text = normalize_review_range(start_date or default_start, end_date or default_end)
        code = _review_participant_code(participant_code)
        result = list_records(code, start_text, end_text, source)
        return {"status": "success", **result}
    except Exception as error:
        raise _storage_error(error)


@app.get("/api/admin/review/overview")
async def admin_review_overview(
    start_date: str | None = Query(default=None, description="Start date in YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="End date in YYYY-MM-DD"),
    participant_code: str = Query(default="all"),
    admin_token: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
):
    try:
        _check_api_admin_token(admin_token, x_admin_token)
        default_start, default_end = _review_default_dates()
        start_text, end_text = normalize_review_range(start_date or default_start, end_date or default_end)
        if str(participant_code or "all").strip().lower() == "all":
            stats = get_review_overview_all(start_text, end_text)
        else:
            code = _review_participant_code(participant_code)
            stats = get_review_overview(code, start_text, end_text)
        return {
            "status": "success",
            "participant_code": participant_code,
            "start_date": start_text,
            "end_date": end_text,
            "period_type": review_period_type(start_text, end_text),
            "stats": stats,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise _storage_error(error)


@app.get("/api/admin/records")
async def admin_records_api(
    start_date: str | None = Query(default=None, description="Start date in YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="End date in YYYY-MM-DD"),
    participant_code: str = Query(default="all"),
    source: str = Query(default="all"),
    admin_token: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
):
    try:
        _check_api_admin_token(admin_token, x_admin_token)
        default_start, default_end = _review_default_dates()
        start_text, end_text = normalize_review_range(start_date or default_start, end_date or default_end)
        result = list_records_all(start_text, end_text, source, participant_code)
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as error:
        raise _storage_error(error)


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



class BodySensationAdviceRequest(BaseModel):
    participant_code: str | None = Field(default=None, max_length=64)
    journal_text: str = Field(default="", max_length=20000)
    selected_regions: list[dict] = Field(default_factory=list)
    symptoms: list[dict] = Field(default_factory=list)
    free_text: str = Field(default="", max_length=12000)
    include_recent_diaries: bool = True
    recent_diary_limit: int = Field(default=3, ge=0, le=10)



@app.get("/body")
@app.get("/body-sensation")
@app.get("/body_sensation")
async def body_sensation_page():
    page_path = Path(__file__).resolve().parent / "static" / "body_sensation.html"
    return FileResponse(page_path)


@app.head("/body")
@app.head("/body-sensation")
@app.head("/body_sensation")
async def body_sensation_page_head():
    return Response(status_code=200, media_type="text/html")

@app.post("/body-sensation/advice")
async def body_sensation_advice(payload: BodySensationAdviceRequest):
    try:
        from emotion_rec.body_sensation import generate_body_sensation_advice
    except ModuleNotFoundError:
        from body_sensation import generate_body_sensation_advice  # type: ignore

    try:
        payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        result = generate_body_sensation_advice(payload_data)
        return Response(
            content=json.dumps(result, ensure_ascii=False),
            media_type="application/json; charset=utf-8",
        )
    except Exception as error:
        print(f"[body_sensation] endpoint failed: {error}")
        return {
            "status": "error",
            "message": str(error),
            "body_sensation": {
                "selected_regions": [],
                "symptoms": [],
            },
            "emotion_context": {},
            "possible_links": [],
            "advice": {
                "source": "error_fallback",
                "title": "暂时无法生成身体感受建议",
                "summary": "后端处理时遇到问题，但这不影响你继续记录情绪日记。",
                "steps": [
                    "先记录症状出现的时间、持续多久、强度变化。",
                    "如果症状明显或持续加重，请优先寻求专业医疗帮助。",
                ],
                "reflection_prompt": "可以稍后再试一次，或补充更多关于睡眠、饮食、咖啡因和压力事件的信息。",
                "when_to_seek_help": [
                    "胸痛、呼吸困难、晕厥、剧烈头痛、麻木无力、血便或高烧时，请及时就医。"
                ],
                "not_medical_diagnosis": True,
            },
            "safety": {
                "risk_level": "unknown",
                "red_flags": [],
                "not_medical_diagnosis": True,
            },
            "logged": False,
        }


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
