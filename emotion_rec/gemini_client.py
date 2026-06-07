

"""Shared Gemini VLM client using Google AI Studio (``google-genai`` SDK).

Image (and other multimodal) understanding goes through this module so the
upload-analysis path shares the same configuration style and graceful-fallback
behaviour as the text LLM wrapper in ``emotion_rec/llm_client.py``.

While ``llm_client.py`` talks to DeepSeek through the OpenAI-compatible API,
this module talks to Gemini through Google's official ``google-genai`` SDK,
because Gemini is natively multimodal and is the model we use to analyse the
images users attach to Journal / Diary entries.

Configure with environment variables:
- GEMINI_API_KEY, or legacy GOOGLE_API_KEY (get one at https://aistudio.google.com/apikey)
- GEMINI_MODEL, default ``gemini-2.5-flash``
- GEMINI_FALLBACK_MODELS, comma-separated models tried when the primary keeps
  returning transient errors (default ``gemini-2.0-flash,gemini-flash-latest``)
- GEMINI_BASE_URL, optional override for the API endpoint
- GEMINI_TIMEOUT_SECONDS, default ``30``
- GEMINI_MAX_RETRIES, transient-error retries per model (default ``1``)
- GEMINI_ENABLED, default enabled

If no API key is configured, callers receive ``None`` and use their local
fallbacks — exactly like ``llm_client.py``.
"""

from __future__ import annotations

import os
import time
from typing import Any

# Reuse the JSON helpers from the text LLM wrapper so cleaning / parsing of
# model output behaves identically across both clients. Mirror app.py's
# package-vs-flat import handling.
try:  # pragma: no cover - import shim
    from emotion_rec import llm_client
except ModuleNotFoundError:  # pragma: no cover - import shim
    import llm_client  # type: ignore


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
# Secrets must be provided through the environment. If no key is configured,
# image analysis falls back locally without failing the upload.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
# 默认模型；如 AI Studio 显示的可用名不同，改这里或设置 GEMINI_MODEL 即可。
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "")
GEMINI_TIMEOUT_SECONDS = os.getenv("GEMINI_TIMEOUT_SECONDS", "30")
# Extra attempts on transient server errors (503/429/timeout). Total tries = 1 + this.
GEMINI_MAX_RETRIES = os.getenv("GEMINI_MAX_RETRIES", "1")
# Fallback models tried (in order) when the primary model keeps returning transient
# errors like 503 "high demand". gemini-2.0-flash has high capacity and rarely overloads.
GEMINI_FALLBACK_MODELS = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.0-flash,gemini-flash-latest")

# Inline image payloads are capped at ~20MB total request size by the API; keep
# a margin and fall back gracefully above it.
MAX_INLINE_IMAGE_BYTES = 18 * 1024 * 1024


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def default_model() -> str:
    return (GEMINI_MODEL or "gemini-2.5-flash").strip()


def _timeout_ms() -> int:
    try:
        return int(float(GEMINI_TIMEOUT_SECONDS) * 1000)
    except (TypeError, ValueError):
        return 30000


def _max_retries() -> int:
    try:
        return max(0, int(GEMINI_MAX_RETRIES))
    except (TypeError, ValueError):
        return 1


def _model_chain(primary: str | None) -> list[str]:
    """Ordered, de-duplicated list of models to try: primary first, then fallbacks."""
    chain = [primary or default_model()]
    for name in (GEMINI_FALLBACK_MODELS or "").split(","):
        name = name.strip()
        if name and name not in chain:
            chain.append(name)
    return chain


_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "DEADLINE", "TIMEOUT", "500", "INTERNAL")


def _is_transient(exc: Exception) -> bool:
    """Heuristically detect retryable server-side errors (overload / rate limit)."""
    text = str(exc).upper()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def _resolve_api_key() -> str:
    key = (GEMINI_API_KEY or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def gemini_enabled() -> bool:
    """True only when Gemini calls are enabled and an API key is configured."""
    return _env_bool("GEMINI_ENABLED", True) and bool(_resolve_api_key())


_CLIENT: Any = None
_CLIENT_SIGNATURE: tuple[str, str, int] | None = None


def get_client():
    """Return a cached ``google-genai`` client, or ``None`` when unavailable."""
    global _CLIENT, _CLIENT_SIGNATURE

    if not _env_bool("GEMINI_ENABLED", True):
        return None

    api_key = _resolve_api_key()
    if not api_key:
        return None

    signature = (api_key, (GEMINI_BASE_URL or "").strip(), _timeout_ms())
    if _CLIENT is not None and _CLIENT_SIGNATURE == signature:
        return _CLIENT

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # pragma: no cover - import guard
        print(f"[gemini_client] google-genai SDK not available: {exc}")
        return None

    try:
        http_options: dict[str, Any] = {"timeout": _timeout_ms()}
        if (GEMINI_BASE_URL or "").strip():
            http_options["base_url"] = GEMINI_BASE_URL.strip()
        _CLIENT = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(**http_options),
        )
        _CLIENT_SIGNATURE = signature
        return _CLIENT
    except Exception as exc:
        print(f"[gemini_client] failed to build genai client: {exc}")
        _CLIENT = None
        _CLIENT_SIGNATURE = None
        return None


# -----------------------------------------------------------------------------
# Image analysis
# -----------------------------------------------------------------------------
_CONTEXT_HINTS = {
    "diary": "这张图片是用户附在「正式日记」里的，通常是当天生活、场景或心情的记录。",
    "journal": "这张图片是用户附在「随手记 Journal」里的，通常是碎片化的当下感受或场景。",
    "general": "这张图片是用户附在情绪记录里的。",
}


def _build_prompt(context: str) -> str:
    """Build the image-analysis prompt.

    The reasoning structure follows the Grounded Affective Tree (GAT) framework
    (AICA-Bench, arXiv:2604.05900, Appendix C): observe objective cues first,
    branch into multiple evidence-cited emotion hypotheses with explicit
    intensity, then verify each hypothesis against the evidence before
    concluding. This directly targets the two failure modes that paper reports
    for VLM affective analysis — the "arousal bottleneck" (mis-estimating
    intensity) and catastrophic valence flips from a single salient cue.
    """
    hint = _CONTEXT_HINTS.get((context or "general").strip(), _CONTEXT_HINTS["general"])
    return f"""你是 EmoType 的视觉情绪分析助手，使用「先客观观察 → 再分支假设 → 最后核验」的接地推理流程（Grounded Affective Tree）来分析用户上传的图片。{hint}

请严格按以下四个阶段思考，并把每个阶段的结果写进同一个 JSON 对象。只输出这一个 JSON 对象，不要任何额外文字、解释或 markdown 代码块。

【阶段1 · 客观观察 visual_evidence】
先只描述图片中**真实可见**的客观线索，此阶段绝不推断情绪：人物与表情、肢体姿态与动作、关键物体、场景/背景、光线明暗、色彩饱和度、构图。每条线索一句话。**绝不臆造图中不存在的物体或事件。** 注意：**不要只依赖人脸**——人脸表情只是线索之一，需同等重视整体场景、环境、物体、光线与氛围（视觉模型常因过度依赖人脸而忽略整体语境、误判情绪）。

【阶段2 · 候选情绪 candidates】
基于上述线索提出 **3 个互不相同的**候选情绪假设。每个假设都必须引用具体的视觉线索作为证据，并给出强度等级 low/medium/high。强度（即唤醒度 arousal）必须由具体线索支撑——例如：紧绷的表情、夸张或剧烈的动作、强烈明暗对比、高饱和色彩 → 高唤醒；放松的姿态、柔和光线、低饱和度、安静的构图 → 低唤醒。

【阶段3 · 核验 verification】
逐一核验候选：被引用的线索是否真的支持所声称的强度？（例：若引用「放松的手」却声称「高度兴奋」，二者矛盾，应下调强度。）是否有其它线索指向不同结论？**特别警惕：不要被单一显眼线索带偏而翻转效价（valence 的正/负），要综合所有线索权衡。** 最后给出对最终判断的信心 confidence(0~1)。

【阶段4 · 结论：区分「人物表达」与「画面诱发」】
请分别给出两类情绪——它们可能并不相同：
- expressed_emotion：图中**人物所表达/流露**的情绪（依据表情、姿态、动作）。若图中无人物或无法辨别，留空字符串。
- evoked_emotion：整体**画面/场景所诱发**的情绪（依据场景、光线、色彩、氛围）。
例如：一个人在温暖咖啡馆里平静微笑（expressed=平静），而窗外阴雨灰暗的街景透出淡淡忧郁（evoked=忧郁）。
最后给出综合主情绪 primary_emotion 与其 V-A 坐标。

JSON 字段（严格使用以下键名，并按此顺序填写）：
- "visual_evidence": 字符串数组，阶段1 的客观线索（3~6 条）。
- "candidates": 数组，恰好 3 项，每项为 {{"emotion": 中文情绪标签, "intensity": "low|medium|high", "evidence": 引用到的具体线索}}。
- "verification": 一句中文，阶段3 的核验结论。
- "description": 一句中文客观描述图片内容（不超过 40 字）。
- "expressed_emotion": 人物所表达的情绪中文标签；无人物则为空字符串 ""。
- "evoked_emotion": 画面/场景所诱发的情绪中文标签。
- "primary_emotion": 综合后最贴切的中文主情绪标签。
- "secondary_emotions": 0~3 个细粒度中文情绪标签的数组。
- "valence": 情绪效价，-1.0（非常消极）到 1.0（非常积极）之间的小数。
- "arousal": 情绪唤醒度，-1.0（非常平静）到 1.0（非常激动）之间的小数，必须与阶段2/3 的强度判断一致。
- "confidence": 对最终判断的信心，0.0~1.0 之间的小数。
- "color": 能代表该情绪的十六进制颜色，形如 "#aabbcc"。
- "reflection": 一句温柔、不评判、不做医疗诊断的共情式反思（中文，不超过 40 字）。

若图片中没有明显的人物或情绪线索，也请基于整体氛围（光线、色彩、场景）给出最合理的估计，并用较低的 confidence 体现这种不确定性。"""


def _clamp_unit(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num != num:  # NaN
        return default
    return max(-1.0, min(1.0, num))


def _clamp_01(value: Any) -> float | None:
    """Clamp to [0, 1]; return None when not a usable number."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return max(0.0, min(1.0, num))


def _normalize_analysis(raw: Any) -> dict | None:
    """Coerce a model JSON payload into the canonical analysis shape.

    The canonical user-facing fields are kept stable for the frontend; the
    GAT grounding fields (visual_evidence / candidates / verification /
    confidence) are passed through so callers can optionally surface the
    evidence behind a verdict, but they are always optional.
    """
    if not isinstance(raw, dict):
        return None

    secondary = raw.get("secondary_emotions")
    if isinstance(secondary, str):
        secondary = [secondary]
    elif not isinstance(secondary, list):
        secondary = []
    secondary = [str(item).strip() for item in secondary if str(item).strip()][:3]

    color = str(raw.get("color") or "").strip()
    if not (color.startswith("#") and len(color) in (4, 7)):
        color = ""

    evidence = raw.get("visual_evidence")
    if isinstance(evidence, str):
        evidence = [evidence]
    elif not isinstance(evidence, list):
        evidence = []
    evidence = [str(item).strip() for item in evidence if str(item).strip()][:6]

    candidates = []
    raw_candidates = raw.get("candidates")
    if isinstance(raw_candidates, list):
        for item in raw_candidates[:3]:
            if not isinstance(item, dict):
                continue
            emotion = str(item.get("emotion") or "").strip()
            if not emotion:
                continue
            candidates.append({
                "emotion": emotion,
                "intensity": str(item.get("intensity") or "").strip().lower(),
                "evidence": str(item.get("evidence") or "").strip(),
            })

    return {
        "description": str(raw.get("description") or "").strip(),
        "primary_emotion": str(raw.get("primary_emotion") or raw.get("primary") or "").strip(),
        "expressed_emotion": str(raw.get("expressed_emotion") or "").strip(),
        "evoked_emotion": str(raw.get("evoked_emotion") or "").strip(),
        "secondary_emotions": secondary,
        "valence": _clamp_unit(raw.get("valence")),
        "arousal": _clamp_unit(raw.get("arousal")),
        "confidence": _clamp_01(raw.get("confidence")),
        "color": color,
        "reflection": str(raw.get("reflection") or "").strip(),
        "visual_evidence": evidence,
        "candidates": candidates,
        "verification": str(raw.get("verification") or "").strip(),
    }


def analyze_image(
    image_bytes: bytes,
    *,
    mime_type: str = "image/jpeg",
    context: str = "general",
    model: str | None = None,
    prompt: str | None = None,
) -> dict | None:
    """Analyse an uploaded image with Gemini.

    Returns a normalized emotion dict (description / primary_emotion /
    secondary_emotions / valence / arousal / color / reflection), or ``None``
    when Gemini is disabled, unconfigured, the payload is unusable, or the call
    fails — callers should treat ``None`` as "no analysis available".
    """
    if not image_bytes:
        return None
    if len(image_bytes) > MAX_INLINE_IMAGE_BYTES:
        print(f"[gemini_client] image too large for inline analysis: {len(image_bytes)} bytes")
        return None

    client = get_client()
    if client is None:
        return None

    try:
        from google.genai import types
    except Exception as exc:  # pragma: no cover - import guard
        print(f"[gemini_client] google-genai SDK not available: {exc}")
        return None

    request_contents = [
        types.Part.from_bytes(
            data=image_bytes,
            mime_type=(mime_type or "image/jpeg"),
        ),
        prompt or _build_prompt(context),
    ]
    request_config = types.GenerateContentConfig(
        # Lower temperature keeps the grounded observation/verification
        # consistent; GAT reasoning benefits from determinism here.
        temperature=0.3,
        response_mime_type="application/json",
    )

    content = None
    attempts = _max_retries() + 1
    chain = _model_chain(model)
    # Try each model in the chain; within a model, retry transient errors. On a
    # model that keeps failing transiently, fall through to the next model.
    for mi, model_name in enumerate(chain):
        transient_exhausted = False
        for attempt in range(attempts):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=request_contents,
                    config=request_config,
                )
                content = getattr(response, "text", None)
                break
            except Exception as exc:
                if _is_transient(exc) and attempt + 1 < attempts:
                    print(f"[gemini_client] transient error on {model_name}, retrying ({attempt + 1}/{attempts - 1}): {str(exc)[:140]}")
                    time.sleep(1.0 * (attempt + 1))
                    continue
                if _is_transient(exc) and mi + 1 < len(chain):
                    print(f"[gemini_client] {model_name} overloaded, falling back to {chain[mi + 1]}")
                    transient_exhausted = True
                    break
                print(f"[gemini_client] image analysis failed on {model_name}: {exc}")
                return None
        if content is not None:
            break
        if not transient_exhausted:
            return None

    if not content or not content.strip():
        return None

    parsed = llm_client.extract_json(content)
    normalized = _normalize_analysis(parsed)
    if normalized is None:
        print(f"[gemini_client] JSON parse failed. preview={llm_client.strip_content(content)[:300]}")
    return normalized


# -----------------------------------------------------------------------------
# Text chat (reuses same client / config as image analysis)
# -----------------------------------------------------------------------------

def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> str | None:
    """Call Gemini with OpenAI-format messages and return raw text content.

    System messages are extracted as Gemini's ``system_instruction``.
    User / assistant turns are converted to Gemini Content objects.
    Returns ``None`` when Gemini is unavailable or the call fails.
    """
    client = get_client()
    if client is None:
        return None

    try:
        from google.genai import types
    except Exception as exc:
        print(f"[gemini_client] google-genai SDK not available: {exc}")
        return None

    system_instruction: str | None = None
    contents: list = []
    for msg in messages:
        role = str(msg.get("role", "")).strip()
        content_text = str(msg.get("content", "")).strip()
        if role == "system":
            system_instruction = content_text
        elif role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content_text)]))
        elif role in ("assistant", "model"):
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content_text)]))

    config_kwargs: dict[str, Any] = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if temperature is not None:
        config_kwargs["temperature"] = temperature
    if max_tokens is not None:
        config_kwargs["max_output_tokens"] = max_tokens
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    request_config = types.GenerateContentConfig(**config_kwargs)

    model_name = model or default_model()
    chain = _model_chain(model_name)
    attempts = _max_retries() + 1

    for mi, model_name in enumerate(chain):
        transient_exhausted = False
        for attempt in range(attempts):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=request_config,
                )
                return getattr(response, "text", None)
            except Exception as exc:
                if _is_transient(exc) and attempt + 1 < attempts:
                    print(f"[gemini_client] transient error on {model_name}, retrying ({attempt + 1}): {str(exc)[:140]}")
                    time.sleep(1.0 * (attempt + 1))
                    continue
                if _is_transient(exc) and mi + 1 < len(chain):
                    print(f"[gemini_client] {model_name} overloaded, falling back to {chain[mi + 1]}")
                    transient_exhausted = True
                    break
                print(f"[gemini_client] chat call failed on {model_name}: {exc}")
                return None
        if not transient_exhausted:
            break
    return None


def chat_json(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    retries: int = 1,
    **kwargs: Any,
) -> Any:
    """Call Gemini in JSON mode and return parsed JSON, or ``None``."""
    last_content: str | None = None
    for _ in range(max(1, retries + 1)):
        content = chat(
            messages,
            model=model,
            temperature=temperature,
            json_mode=True,
            max_tokens=max_tokens,
            **kwargs,
        )
        if content and content.strip():
            parsed = llm_client.extract_json(content)
            if parsed is not None:
                return parsed
            last_content = content
    if last_content is not None:
        print(f"[gemini_client] JSON parse failed. preview={llm_client.strip_content(last_content)[:300]}")
    return None
