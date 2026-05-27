"""Text emotion inference for implicit Valence-Arousal signals.

The V-A mapper remains a pure mapping layer. This module owns text semantics:
it segments journal text, detects implicit affect cues, optionally uses a
Chinese emotion classifier for explicit affect, and can later use a
sentence-transformers encoder plus a trained regression head.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from emotion_rec.va_mapper import EMOTION_LEXICON, clamp, split_text_segments
except ModuleNotFoundError:
    from va_mapper import EMOTION_LEXICON, clamp, split_text_segments  # type: ignore


DEFAULT_TEXT_EMOTION_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_TEXT_EMOTION_CLASSIFIER = "Johnson8187/Chinese-Emotion-Small"
DEFAULT_HEAD_PATH = Path(__file__).resolve().parent / "models" / "text_emotion_head.pt"

TEXT_EMOTION_MODEL_NAME = os.getenv("TEXT_EMOTION_MODEL_NAME", DEFAULT_TEXT_EMOTION_MODEL)
TEXT_EMOTION_CLASSIFIER_NAME = os.getenv("TEXT_EMOTION_CLASSIFIER_NAME", DEFAULT_TEXT_EMOTION_CLASSIFIER)
TEXT_EMOTION_HEAD_PATH = Path(os.getenv("TEXT_EMOTION_HEAD_PATH", str(DEFAULT_HEAD_PATH)))
TEXT_EMOTION_BACKEND = os.getenv("TEXT_EMOTION_BACKEND", "auto").lower()
TEXT_EMOTION_ALLOW_UNTRAINED_HEAD = os.getenv("TEXT_EMOTION_ALLOW_UNTRAINED_HEAD", "0") == "1"
TEXT_EMOTION_LOCAL_FILES_ONLY = os.getenv("TEXT_EMOTION_LOCAL_FILES_ONLY", "0") == "1"

CHINESE_EMOTION_LABELS = {
    0: "平淡語氣",
    1: "關切語調",
    2: "開心語調",
    3: "憤怒語調",
    4: "悲傷語調",
    5: "疑問語調",
    6: "驚奇語調",
    7: "厭惡語調",
}

CLASSIFIER_LABEL_TO_VA = {
    "平淡語氣": (0.0, 0.0, "中性", "未明确"),
    "平淡语气": (0.0, 0.0, "中性", "未明确"),
    "neutral": (0.0, 0.0, "中性", "未明确"),
    "關切語調": (-0.15, 0.35, "担心", "关切"),
    "关切语调": (-0.15, 0.35, "担心", "关切"),
    "concerned tone": (-0.15, 0.35, "担心", "关切"),
    "concern": (-0.15, 0.35, "担心", "关切"),
    "開心語調": (0.65, 0.55, "开心", "开心"),
    "开心语调": (0.65, 0.55, "开心", "开心"),
    "happy tone": (0.65, 0.55, "开心", "开心"),
    "joy": (0.65, 0.55, "开心", "开心"),
    "憤怒語調": (-0.75, 0.75, "愤怒", "愤怒"),
    "愤怒语调": (-0.75, 0.75, "愤怒", "愤怒"),
    "angry tone": (-0.75, 0.75, "愤怒", "愤怒"),
    "anger": (-0.75, 0.75, "愤怒", "愤怒"),
    "悲傷語調": (-0.65, -0.45, "悲伤", "悲伤"),
    "悲伤语调": (-0.65, -0.45, "悲伤", "悲伤"),
    "sad tone": (-0.65, -0.45, "悲伤", "悲伤"),
    "sadness": (-0.65, -0.45, "悲伤", "悲伤"),
    "疑問語調": (-0.1, 0.25, "困惑", "困惑"),
    "疑问语调": (-0.1, 0.25, "困惑", "困惑"),
    "questioning tone": (-0.1, 0.25, "困惑", "困惑"),
    "confuse": (-0.1, 0.25, "困惑", "困惑"),
    "驚奇語調": (0.2, 0.75, "惊讶", "惊讶"),
    "驚訝語調": (0.2, 0.75, "惊讶", "惊讶"),
    "惊奇语调": (0.2, 0.75, "惊讶", "惊讶"),
    "惊讶语调": (0.2, 0.75, "惊讶", "惊讶"),
    "surprised tone": (0.2, 0.75, "惊讶", "惊讶"),
    "surprise": (0.2, 0.75, "惊讶", "惊讶"),
    "厭惡語調": (-0.75, 0.35, "厌恶", "厌恶"),
    "厌恶语调": (-0.75, 0.35, "厌恶", "厌恶"),
    "disgusted tone": (-0.75, 0.35, "厌恶", "厌恶"),
    "disgust": (-0.75, 0.35, "厌恶", "厌恶"),
}


@dataclass
class SegmentEmotion:
    text: str
    valence: float
    arousal: float
    confidence: float
    explicit_label: str
    implicit_label: str
    evidence: list[str]
    source: str = "rules"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "valence": clamp(self.valence),
            "arousal": clamp(self.arousal),
            "confidence": max(0.0, min(1.0, float(self.confidence))),
            "explicit_label": self.explicit_label,
            "implicit_label": self.implicit_label,
            "evidence": self.evidence,
            "source": self.source,
        }


def _contains_any(text: str, terms: list[str] | set[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


NEGATION_PREFIXES = (
    "不",
    "没",
    "沒",
    "没有",
    "沒有",
    "未",
    "无",
    "無",
    "并不",
    "並不",
    "不是",
    "别",
    "別",
)


def _is_negated_match(text: str, label: str, index: int) -> bool:
    prefix = text[max(0, index - 4):index].lower()
    return any(prefix.endswith(term.lower()) for term in NEGATION_PREFIXES)


def _contains_unnegated_any(text: str, terms: list[str] | set[str]) -> bool:
    lower = text.lower()
    for term in sorted(terms, key=len, reverse=True):
        term_lower = term.lower()
        start = 0
        while True:
            index = lower.find(term_lower, start)
            if index == -1:
                break
            if not _is_negated_match(text, term, index):
                return True
            start = index + len(term_lower)
    return False


def _lexicon_matches(text: str) -> list[dict[str, Any]]:
    lower = text.lower()
    matches: list[dict[str, Any]] = []
    for item in sorted(EMOTION_LEXICON, key=lambda value: len(str(value.get("label", ""))), reverse=True):
        label = str(item.get("label", ""))
        if not label:
            continue
        label_lower = label.lower()
        start = 0
        while True:
            index = lower.find(label_lower, start)
            if index == -1:
                break
            if float(item.get("valence", 0.0)) <= 0 or not _is_negated_match(text, label, index):
                matches.append(item)
                break
            start = index + len(label_lower)
    return matches


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


class TextEmotionRegressionHead:
    """Small MLP regression head loaded lazily when model weights exist."""

    def __init__(self, input_dim: int, hidden_dim: int = 256):
        import torch
        import torch.nn as nn

        self.torch = torch
        self.model = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 3),
        )

    def load(self, checkpoint_path: Path, device: str):
        checkpoint = self.torch.load(checkpoint_path, map_location=device)
        state_dict = checkpoint.get("state_dict", checkpoint)
        self.model.load_state_dict(state_dict)
        self.model.to(device)
        self.model.eval()

    def predict(self, embedding, device: str) -> dict[str, float]:
        with self.torch.no_grad():
            tensor = self.torch.tensor(embedding, dtype=self.torch.float32, device=device).unsqueeze(0)
            raw = self.model(tensor)[0]
            valence = self.torch.tanh(raw[0]).item()
            arousal = self.torch.tanh(raw[1]).item()
            confidence = self.torch.sigmoid(raw[2]).item()
        return {"valence": valence, "arousal": arousal, "confidence": confidence}


class TextEmotionAnalyzer:
    def __init__(
        self,
        model_name: str = TEXT_EMOTION_MODEL_NAME,
        classifier_name: str = TEXT_EMOTION_CLASSIFIER_NAME,
        head_path: Path = TEXT_EMOTION_HEAD_PATH,
        backend: str = TEXT_EMOTION_BACKEND,
    ):
        self.model_name = model_name
        self.classifier_name = classifier_name
        self.head_path = head_path
        self.backend = backend
        self.encoder = None
        self.head = None
        self.classifier_tokenizer = None
        self.classifier_model = None
        self.classifier_id2label: dict[int, str] = {}
        self.device = "cpu"
        self.model_error = None
        self.model_errors: list[str] = []

        if backend in {"auto", "model", "regression"}:
            self._load_model_backend(required=backend in {"model", "regression"})
        if self.encoder is None and backend in {"auto", "classifier", "hf_classifier"}:
            self._load_classifier_backend(required=backend in {"classifier", "hf_classifier"})

    def _load_model_backend(self, required: bool = False):
        if not self.head_path.exists() and not TEXT_EMOTION_ALLOW_UNTRAINED_HEAD:
            self.model_error = (
                f"Missing text emotion regression head: {self.head_path}. "
                "Using rules backend."
            )
            self.model_errors.append(self.model_error)
            if required:
                raise FileNotFoundError(self.model_error)
            return

        try:
            import torch
            from sentence_transformers import SentenceTransformer

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.encoder = SentenceTransformer(self.model_name, device=self.device)
            input_dim = int(self.encoder.get_sentence_embedding_dimension())
            self.head = TextEmotionRegressionHead(input_dim=input_dim)
            if self.head_path.exists():
                self.head.load(self.head_path, self.device)
            self.backend = "model"
        except Exception as exc:
            self.encoder = None
            self.head = None
            self.model_error = str(exc)
            self.model_errors.append(f"regression backend: {exc}")
            if required:
                raise

    def _load_classifier_backend(self, required: bool = False):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.classifier_tokenizer = AutoTokenizer.from_pretrained(
                self.classifier_name,
                local_files_only=TEXT_EMOTION_LOCAL_FILES_ONLY,
            )
            self.classifier_model = AutoModelForSequenceClassification.from_pretrained(
                self.classifier_name,
                local_files_only=TEXT_EMOTION_LOCAL_FILES_ONLY,
            ).to(self.device)
            self.classifier_model.eval()
            config_labels = getattr(self.classifier_model.config, "id2label", {}) or {}
            self.classifier_id2label = {
                int(index): str(label)
                for index, label in config_labels.items()
            }
            self.backend = "classifier"
        except Exception as exc:
            self.classifier_tokenizer = None
            self.classifier_model = None
            self.model_error = str(exc)
            self.model_errors.append(f"classifier backend: {exc}")
            if required:
                raise

    def analyze(self, text: str) -> dict[str, Any]:
        segments = split_text_segments(text)
        if not segments:
            segments = [""]

        analyzed = [self.analyze_segment(segment).to_dict() for segment in segments]
        backend = "rules"
        model_name = None
        if self.encoder is not None and self.head is not None:
            backend = "regression"
            model_name = self.model_name
        elif self.classifier_model is not None:
            backend = "classifier+rules"
            model_name = self.classifier_name

        return {
            "segments": analyzed,
            "backend": backend,
            "model": model_name,
            "model_error": self.model_error,
            "model_errors": self.model_errors,
        }

    def analyze_segment(self, segment_text: str) -> SegmentEmotion:
        rule_result = self._analyze_segment_rules(segment_text)
        if not segment_text.strip():
            return rule_result

        if self.encoder is not None and self.head is not None:
            try:
                embedding = self.encoder.encode(segment_text, normalize_embeddings=True)
                model_result = self.head.predict(embedding, self.device)
                blended_confidence = max(rule_result.confidence, model_result["confidence"])
                blend = model_result["confidence"]
                valence = rule_result.valence * (1 - blend) + model_result["valence"] * blend
                arousal = rule_result.arousal * (1 - blend) + model_result["arousal"] * blend
                return SegmentEmotion(
                    text=segment_text,
                    valence=valence,
                    arousal=arousal,
                    confidence=blended_confidence,
                    explicit_label=rule_result.explicit_label,
                    implicit_label=rule_result.implicit_label,
                    evidence=_unique([*rule_result.evidence, "语义模型回归"]),
                    source="regression+rules",
                )
            except Exception as exc:
                self.model_error = str(exc)
                self.model_errors.append(f"regression predict: {exc}")

        classifier_result = self._predict_classifier(segment_text)
        if classifier_result is None:
            return rule_result
        return self._fuse_rule_and_classifier(rule_result, classifier_result)

    def _analyze_segment_rules(self, segment_text: str) -> SegmentEmotion:
        text = segment_text.strip()
        if not text:
            return SegmentEmotion("", 0.0, 0.0, 0.0, "中性", "未明确", [], "rules")

        evidence: list[str] = []
        explicit_label = "中性"
        implicit_label = "未明确"
        valence = 0.0
        arousal = 0.0
        confidence = 0.2

        denial_terms = {
            "没事", "沒事", "还好", "還好", "没什么", "沒什麼", "无所谓", "無所謂",
            "不在意", "算了", "都行", "随便", "隨便", "不要紧", "不要緊", "没关系", "沒關係",
        }
        minimizer_terms = {
            "只是", "有点", "有一點", "一点", "一點", "可能", "也许", "也許", "大概",
            "还可以", "還可以", "还行", "還行", "不算", "没那么", "沒那麼", "just", "maybe",
        }
        contrast_terms = {
            "但是", "可是", "其实", "其實", "不过", "不過", "虽然", "雖然", "只是",
            "但", "可", "然而", "but", "actually", "although",
        }
        body_tension_terms = {
            "胸口", "喘不过气", "喘不過氣", "呼吸不过来", "呼吸不過來", "心跳",
            "心慌", "心悸", "手抖", "发抖", "發抖", "紧", "緊", "僵", "胃",
            "胃疼", "胃痛", "反胃", "出汗", "发麻", "發麻", "坐立不安",
            "睡不着", "睡不著", "失眠", "头皮发麻", "頭皮發麻",
        }
        sadness_body_terms = {
            "眼眶酸", "想哭", "哭不出来", "哭不出來", "很重", "没力气", "沒力氣",
            "没劲", "沒勁", "空空的", "麻木", "累到", "疲惫", "疲憊", "提不起劲",
        }
        relation_terms = {
            "被忽视", "被忽視", "被否定", "被误解", "被誤解", "没人听", "沒人聽",
            "不被需要", "批评", "批評", "被批", "被骂", "被罵", "不重要",
            "没人懂", "沒人懂", "没人理", "沒人理", "被冷落", "被比较", "被比較",
        }
        action_terms = {
            "想逃", "不想回复", "不想回覆", "删掉", "刪掉", "大喊", "什么都不想做",
            "什麼都不想做", "不想见人", "不想見人", "躲起来", "躲起來", "消失",
        }
        shame_terms = {
            "丢脸", "丟臉", "尴尬", "尷尬", "羞耻", "羞恥", "自责", "自責",
            "对不起", "對不起", "我太差", "我不配", "都是我的错", "都是我的錯",
        }
        suppressed_anger_terms = {
            "憋", "忍住", "不想吵", "懒得吵", "懶得吵", "火大", "气死", "氣死",
            "受不了", "烦死", "煩死", "很烦", "很煩",
        }
        overwhelm_terms = {
            "撑不住", "撐不住", "崩溃", "崩潰", "压力", "壓力", "压力大", "壓力大",
            "压力很大", "壓力很大", "压力非常大", "壓力非常大", "学习压力", "學習壓力",
            "太多了", "喘不过来", "喘不過來", "快不行", "顶不住", "頂不住",
        }
        uncertainty_terms = {
            "不知道该怎么办", "不知道該怎麼辦", "怎么办", "怎麼辦", "纠结", "糾結",
            "要不要", "拿不准", "拿不準", "犹豫", "猶豫", "不知道选", "不知道選",
        }
        loneliness_terms = {
            "一个人", "一個人", "孤单", "孤單", "孤独", "孤獨", "没人陪",
            "沒人陪", "不被需要", "没有位置", "沒有位置",
        }
        positive_calm_terms = {
            "安心", "放松", "放鬆", "松了口气", "鬆了口氣", "舒服", "平静", "平靜",
            "安全", "稳定", "穩定",
        }
        positive_energy_terms = {
            "开心", "開心", "高兴", "高興", "期待", "兴奋", "興奮", "惊喜", "驚喜",
            "喜欢", "喜歡", "有希望",
        }
        negated_mood_rules = [
            ("很不开心", -0.52, -0.18, 0.78, "不高兴", "低落", "否定情绪词：很不开心"),
            ("非常不开心", -0.56, -0.2, 0.8, "不高兴", "低落", "否定情绪词：非常不开心"),
            ("不开心", -0.46, -0.16, 0.72, "不高兴", "低落", "否定情绪词：不开心"),
            ("不高兴", -0.42, 0.15, 0.7, "不高兴", "不满", "否定情绪词：不高兴"),
            ("不舒服", -0.4, 0.22, 0.66, "不安", "身体不适", "否定身体感受：不舒服"),
            ("不满意", -0.36, 0.2, 0.64, "不高兴", "不满", "否定评价：不满意"),
            ("不喜欢", -0.42, 0.18, 0.66, "不高兴", "抗拒", "否定偏好：不喜欢"),
            ("不安全", -0.42, 0.48, 0.68, "不安", "警觉", "否定安全感：不安全"),
        ]

        if _contains_any(text, contrast_terms):
            evidence.append("转折表达")
        if _contains_any(text, minimizer_terms):
            evidence.append("弱化表达")

        negated_mood = next((rule for rule in negated_mood_rules if rule[0].lower() in text.lower()), None)

        if negated_mood:
            _, valence, arousal, confidence, explicit_label, implicit_label, reason = negated_mood
            evidence.append(reason)
        elif _contains_any(text, body_tension_terms):
            valence, arousal, confidence = -0.45, 0.65, 0.78
            explicit_label, implicit_label = "不安", "焦虑"
            evidence.append("身体紧绷")
        elif _contains_any(text, overwhelm_terms):
            valence, arousal, confidence = -0.62, 0.72, 0.76
            explicit_label, implicit_label = "紧绷", "压力过载"
            evidence.append("压力过载")
        elif _contains_any(text, uncertainty_terms):
            valence, arousal, confidence = -0.36, 0.48, 0.66
            explicit_label, implicit_label = "不安", "纠结"
            evidence.append("决策不确定")
        elif _contains_any(text, suppressed_anger_terms):
            valence, arousal, confidence = -0.68, 0.68, 0.74
            explicit_label, implicit_label = "恼火", "压抑的愤怒"
            evidence.append("压抑愤怒")
        elif _contains_any(text, sadness_body_terms):
            valence, arousal, confidence = -0.55, -0.45, 0.72
            explicit_label, implicit_label = "低落", "悲伤"
            evidence.append("身体下沉")
        elif _contains_any(text, shame_terms):
            valence, arousal, confidence = -0.58, 0.28, 0.7
            explicit_label, implicit_label = "不安", "羞耻/自责"
            evidence.append("羞耻或自责线索")
        elif _contains_any(text, loneliness_terms):
            valence, arousal, confidence = -0.62, -0.48, 0.7
            explicit_label, implicit_label = "孤独", "孤独"
            evidence.append("孤独线索")
        elif _contains_any(text, relation_terms):
            valence, arousal, confidence = -0.52, 0.42, 0.68
            explicit_label, implicit_label = "不高兴", "委屈"
            evidence.append("关系评价线索")
        elif _contains_any(text, action_terms):
            valence, arousal, confidence = -0.5, 0.55, 0.66
            explicit_label, implicit_label = "不安", "逃避冲动"
            evidence.append("行为冲动")
        elif _contains_any(text, denial_terms):
            valence, arousal, confidence = -0.15, 0.25, 0.42
            explicit_label, implicit_label = "中性", "回避"
            evidence.append("否认式表达")
        elif _contains_unnegated_any(text, positive_calm_terms):
            valence, arousal, confidence = 0.48, -0.48, 0.62
            explicit_label, implicit_label = "平静", "放松"
            evidence.append("积极低唤醒线索")
        elif _contains_unnegated_any(text, positive_energy_terms):
            valence, arousal, confidence = 0.62, 0.52, 0.62
            explicit_label, implicit_label = "开心", "开心"
            evidence.append("积极高唤醒线索")
        else:
            lexicon_matches = _lexicon_matches(text)
            if lexicon_matches:
                weight = 1 / len(lexicon_matches)
                valence = sum(float(item["valence"]) * weight for item in lexicon_matches)
                arousal = sum(float(item["arousal"]) * weight for item in lexicon_matches)
                confidence = min(0.9, 0.48 + 0.12 * len(lexicon_matches))
                explicit_label = lexicon_matches[0]["label"]
                implicit_label = lexicon_matches[0]["label"]
                evidence.extend([f"显性情绪词：{item['label']}" for item in lexicon_matches[:3]])
            else:
                english_result = self._english_hint(text)
                if english_result is not None:
                    return english_result

        if _contains_any(text, denial_terms) and "否认式表达" not in evidence:
            evidence.append("否认式表达")
            implicit_label = implicit_label if implicit_label != "未明确" else "回避"

        return SegmentEmotion(
            text=text,
            valence=valence,
            arousal=arousal,
            confidence=confidence,
            explicit_label=explicit_label,
            implicit_label=implicit_label,
            evidence=_unique(evidence),
            source="rules",
        )

    def _english_hint(self, segment_text: str) -> SegmentEmotion | None:
        lower = segment_text.lower()
        hints = [
            ({"angry", "mad", "hate", "anxious", "worry", "afraid", "tense", "tight"}, -0.5, 0.6, "不安", "焦虑", "英文负性高唤醒线索"),
            ({"happy", "excited", "joy", "proud", "hopeful", "active", "amazing"}, 0.55, 0.55, "开心", "兴奋", "英文积极高唤醒线索"),
            ({"sad", "lonely", "tired", "empty", "depressed", "bored", "low"}, -0.55, -0.55, "低落", "悲伤", "英文负性低唤醒线索"),
            ({"calm", "safe", "relaxed", "peaceful", "comfortable", "love"}, 0.55, -0.55, "平静", "放松", "英文积极低唤醒线索"),
        ]
        for terms, valence, arousal, explicit, implicit, evidence in hints:
            if any(term in lower for term in terms):
                return SegmentEmotion(segment_text, valence, arousal, 0.56, explicit, implicit, [evidence], "rules")
        return None

    def _predict_classifier(self, segment_text: str) -> dict[str, Any] | None:
        if self.classifier_model is None or self.classifier_tokenizer is None:
            return None

        try:
            import torch

            inputs = self.classifier_tokenizer(
                segment_text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=160,
            )
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.no_grad():
                logits = self.classifier_model(**inputs).logits[0]
                probs = torch.softmax(logits, dim=-1)

            top_count = min(3, int(probs.shape[0]))
            top_probs, top_indices = torch.topk(probs, k=top_count)
            top_labels = []
            for probability, index in zip(top_probs.tolist(), top_indices.tolist()):
                label = self._classifier_label_for_index(int(index))
                top_labels.append({
                    "label": label,
                    "probability": float(probability),
                    **self._va_for_classifier_label(label),
                })

            best = top_labels[0]
            return {
                "valence": best["valence"],
                "arousal": best["arousal"],
                "confidence": best["probability"],
                "explicit_label": best["explicit_label"],
                "implicit_label": best["implicit_label"],
                "raw_label": best["label"],
                "top_labels": top_labels,
            }
        except Exception as exc:
            self.model_error = str(exc)
            self.model_errors.append(f"classifier predict: {exc}")
            return None

    def _classifier_label_for_index(self, index: int) -> str:
        label = self.classifier_id2label.get(index)
        if label and not label.upper().startswith("LABEL_"):
            return label
        return CHINESE_EMOTION_LABELS.get(index, label or f"LABEL_{index}")

    def _va_for_classifier_label(self, label: str) -> dict[str, Any]:
        normalized = label.strip()
        lower = normalized.lower()
        for key in (normalized, lower):
            if key in CLASSIFIER_LABEL_TO_VA:
                valence, arousal, explicit_label, implicit_label = CLASSIFIER_LABEL_TO_VA[key]
                return {
                    "valence": valence,
                    "arousal": arousal,
                    "explicit_label": explicit_label,
                    "implicit_label": implicit_label,
                }
        return {
            "valence": 0.0,
            "arousal": 0.0,
            "explicit_label": normalized,
            "implicit_label": "未明确",
        }

    def _fuse_rule_and_classifier(
        self,
        rule_result: SegmentEmotion,
        classifier_result: dict[str, Any],
    ) -> SegmentEmotion:
        classifier_confidence = float(classifier_result["confidence"])
        rule_has_evidence = bool(rule_result.evidence)
        rule_is_implicit = rule_result.implicit_label not in {"未明确", rule_result.explicit_label}
        strong_negation = any(
            evidence.startswith(("否定情绪词", "否定评价", "否定偏好", "否定安全感"))
            for evidence in rule_result.evidence
        )

        if rule_has_evidence and rule_result.confidence >= 0.6:
            rule_weight = 0.68 if rule_is_implicit else 0.6
        elif rule_has_evidence:
            rule_weight = 0.55
        else:
            rule_weight = 0.25

        if strong_negation:
            rule_weight = max(rule_weight, 0.86)
        if classifier_confidence < 0.45:
            rule_weight = max(rule_weight, 0.72)
        classifier_weight = 1 - rule_weight
        if strong_negation and float(classifier_result["valence"]) > 0:
            classifier_weight = min(classifier_weight, 0.08)
            rule_weight = 1 - classifier_weight

        valence = rule_result.valence * rule_weight + classifier_result["valence"] * classifier_weight
        arousal = rule_result.arousal * rule_weight + classifier_result["arousal"] * classifier_weight
        confidence = max(rule_result.confidence, classifier_confidence * 0.92)
        explicit_label = rule_result.explicit_label if strong_negation else classifier_result["explicit_label"]
        implicit_label = (
            rule_result.implicit_label
            if rule_result.implicit_label != "未明确"
            else classifier_result["implicit_label"]
        )

        top_label_text = "、".join(
            f"{item['label']}:{item['probability']:.2f}"
            for item in classifier_result.get("top_labels", [])[:3]
        )
        evidence = [
            *rule_result.evidence,
            f"显性情绪分类：{classifier_result['raw_label']} ({classifier_confidence:.2f})",
        ]
        if top_label_text:
            evidence.append(f"分类候选：{top_label_text}")

        return SegmentEmotion(
            text=rule_result.text,
            valence=valence,
            arousal=arousal,
            confidence=confidence,
            explicit_label=explicit_label,
            implicit_label=implicit_label,
            evidence=_unique(evidence),
            source="classifier+rules",
        )


_ANALYZER: TextEmotionAnalyzer | None = None


def get_text_emotion_analyzer() -> TextEmotionAnalyzer:
    global _ANALYZER
    if _ANALYZER is None:
        _ANALYZER = TextEmotionAnalyzer()
    return _ANALYZER


def analyze_text_emotion(text: str) -> dict[str, Any]:
    return get_text_emotion_analyzer().analyze(text)
