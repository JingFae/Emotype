"""Valence-Arousal mapping utilities.

This module does not infer emotion from audio or text. It only maps already
estimated V-A coordinates to colors, labels, quadrants, and segment summaries.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

NEUTRAL_COLOR = "#94A3B8"
NEUTRAL_THRESHOLD = 0.12
COMPLEX_DISTANCE_THRESHOLD = 0.38
CONFIDENCE_DISTANCE_SCALE = 0.6

ANCHOR_COLORS = {
    "high_negative": "#DC2626",
    "high_positive": "#F59E0B",
    "low_negative": "#2563EB",
    "low_positive": "#10B981",
    "neutral": NEUTRAL_COLOR,
}

QUADRANT_LABELS = {
    "high_negative": "消极高能量",
    "high_positive": "积极高能量",
    "low_negative": "消极低能量",
    "low_positive": "积极低能量",
    "neutral": "中性",
}

LEXICON_PATH = Path(__file__).resolve().parent / "shared" / "emotion_lexicon.json"
SEGMENT_RE = re.compile(r"[^。！？!?,，；;\n]+")


def _load_lexicon() -> list[dict[str, Any]]:
    with LEXICON_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


EMOTION_LEXICON = _load_lexicon()


def clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = lower
    return max(lower, min(upper, number))


def normalize_vad(raw: dict[str, Any], source_range: str = "zero_one") -> dict[str, float]:
    """Normalize VAD values to [-1, 1].

    Use source_range="zero_one" for the current Wav2Vec2 outputs and
    source_range="minus_one_one" when values are already standardized.
    """

    valence = float(raw.get("valence", 0.0))
    arousal = float(raw.get("arousal", 0.0))
    dominance = float(raw.get("dominance", 0.0))

    normalized_source = source_range.replace("-", "_").lower()
    if normalized_source in {"zero_one", "zeroone", "0_1", "01"}:
        valence = valence * 2 - 1
        arousal = arousal * 2 - 1
        dominance = dominance * 2 - 1

    return {
        "valence": clamp(valence),
        "arousal": clamp(arousal),
        "dominance": clamp(dominance),
    }


def normalizeVAD(raw: dict[str, Any], source_range: str = "zero_one") -> dict[str, float]:
    return normalize_vad(raw, source_range)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    clean = color.lstrip("#")
    return tuple(int(clean[index:index + 2], 16) for index in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in rgb)


def mix_color(start: str, end: str, amount: float) -> str:
    ratio = max(0.0, min(1.0, float(amount)))
    start_rgb = _hex_to_rgb(start)
    end_rgb = _hex_to_rgb(end)
    mixed = tuple(
        round(start_rgb[index] + (end_rgb[index] - start_rgb[index]) * ratio)
        for index in range(3)
    )
    return _rgb_to_hex(mixed)


def get_quadrant(valence: float, arousal: float) -> str:
    v = clamp(valence)
    a = clamp(arousal)
    if abs(v) < NEUTRAL_THRESHOLD and abs(a) < NEUTRAL_THRESHOLD:
        return "neutral"
    if v < 0 and a > 0:
        return "high_negative"
    if v >= 0 and a > 0:
        return "high_positive"
    if v < 0 and a <= 0:
        return "low_negative"
    return "low_positive"


def get_emotion_color(valence: float, arousal: float) -> str:
    quadrant = get_quadrant(valence, arousal)
    if quadrant == "neutral":
        return NEUTRAL_COLOR

    distance = math.sqrt(clamp(valence) ** 2 + clamp(arousal) ** 2)
    strength = max(0.0, min(1.0, distance / math.sqrt(2)))
    return mix_color(NEUTRAL_COLOR, ANCHOR_COLORS[quadrant], strength)


def get_emotion_label(valence: float, arousal: float) -> dict[str, Any]:
    v = clamp(valence)
    a = clamp(arousal)
    if get_quadrant(v, a) == "neutral":
        return {
            "label": "中性",
            "distance": 0.0,
            "confidence": 1.0,
        }

    nearest = min(
        EMOTION_LEXICON,
        key=lambda item: math.sqrt((v - item["valence"]) ** 2 + (a - item["arousal"]) ** 2),
    )
    distance = math.sqrt((v - nearest["valence"]) ** 2 + (a - nearest["arousal"]) ** 2)
    confidence = max(0.0, min(1.0, 1 - distance / CONFIDENCE_DISTANCE_SCALE))

    if distance > COMPLEX_DISTANCE_THRESHOLD:
        return {
            "label": "复杂情绪",
            "distance": distance,
            "confidence": confidence,
            "nearest_label": nearest["label"],
        }

    return {
        "label": nearest["label"],
        "distance": distance,
        "confidence": confidence,
    }


def get_emotion_candidates(
    valence: float,
    arousal: float,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return nearby lexicon labels around a V-A point.

    These are not quadrant fallbacks. They are the closest emotion words in the
    shared 80-word V-A lexicon, ordered by Euclidean distance.
    """

    v = clamp(valence)
    a = clamp(arousal)
    nearest = sorted(
        EMOTION_LEXICON,
        key=lambda item: math.sqrt((v - item["valence"]) ** 2 + (a - item["arousal"]) ** 2),
    )

    candidates = []
    for item in nearest[:max(1, int(limit))]:
        item_valence = clamp(item["valence"])
        item_arousal = clamp(item["arousal"])
        distance = math.sqrt((v - item_valence) ** 2 + (a - item_arousal) ** 2)
        confidence = max(0.0, min(1.0, 1 - distance / CONFIDENCE_DISTANCE_SCALE))
        quadrant = item.get("quadrant") or get_quadrant(item_valence, item_arousal)
        candidates.append(
            {
                "label": item["label"],
                "valence": item_valence,
                "arousal": item_arousal,
                "distance": distance,
                "confidence": confidence,
                "quadrant": quadrant,
                "quadrant_label": QUADRANT_LABELS[quadrant],
                "color": get_emotion_color(item_valence, item_arousal),
                "source": "lexicon_nearby",
            }
        )

    if get_quadrant(v, a) == "neutral":
        candidates.insert(
            0,
            {
                "label": "中性",
                "valence": v,
                "arousal": a,
                "distance": 0.0,
                "confidence": 1.0,
                "quadrant": "neutral",
                "quadrant_label": QUADRANT_LABELS["neutral"],
                "color": NEUTRAL_COLOR,
                "source": "neutral_center",
            },
        )

    return candidates[:max(1, int(limit))]


def map_va(
    valence: float,
    arousal: float,
    confidence: float | None = None,
) -> dict[str, Any]:
    v = clamp(valence)
    a = clamp(arousal)
    label_result = get_emotion_label(v, a)
    label_confidence = float(label_result["confidence"])
    source_confidence = None if confidence is None else max(0.0, min(1.0, float(confidence)))
    final_confidence = (
        label_confidence
        if source_confidence is None
        else label_confidence * source_confidence
    )

    return {
        "valence": v,
        "arousal": a,
        "label": label_result["label"],
        "distance": float(label_result["distance"]),
        "confidence": final_confidence,
        "label_confidence": label_confidence,
        "source_confidence": source_confidence,
        "quadrant": get_quadrant(v, a),
        "quadrant_label": QUADRANT_LABELS[get_quadrant(v, a)],
        "color": get_emotion_color(v, a),
        "nearest_label": label_result.get("nearest_label"),
        "candidates": get_emotion_candidates(v, a),
    }


def split_text_segments(text: str) -> list[str]:
    return [match.group(0).strip() for match in SEGMENT_RE.finditer(text) if match.group(0).strip()]


def map_segments(segments: list[dict[str, Any]]) -> dict[str, Any]:
    mapped_segments = []
    weighted_valence = 0.0
    weighted_arousal = 0.0
    total_weight = 0.0

    for segment in segments:
        text = str(segment.get("text", "")).strip()
        mapped = map_va(
            segment.get("valence", 0.0),
            segment.get("arousal", 0.0),
            segment.get("confidence"),
        )
        mapped["text"] = text
        for metadata_key in ("explicit_label", "implicit_label", "evidence", "source"):
            if metadata_key in segment:
                mapped[metadata_key] = segment[metadata_key]
        mapped_segments.append(mapped)

        weight = max(1, len(text)) * max(0.05, float(mapped["confidence"]))
        weighted_valence += mapped["valence"] * weight
        weighted_arousal += mapped["arousal"] * weight
        total_weight += weight

    if total_weight:
        overall_valence = weighted_valence / total_weight
        overall_arousal = weighted_arousal / total_weight
        overall_confidence = sum(item["confidence"] for item in mapped_segments) / len(mapped_segments)
    else:
        overall_valence = 0.0
        overall_arousal = 0.0
        overall_confidence = 0.0

    return {
        "segments": mapped_segments,
        "overall": map_va(overall_valence, overall_arousal, overall_confidence),
    }
