# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    from emotion_rec.text_emotion import analyze_text_emotion
    from emotion_rec.va_mapper import map_segments, map_va
    from emotion_rec.storage import list_diary_entries, log_usage_event
    from emotion_rec import llm_client
except ModuleNotFoundError:
    from text_emotion import analyze_text_emotion  # type: ignore
    from va_mapper import map_segments, map_va  # type: ignore
    from storage import list_diary_entries, log_usage_event  # type: ignore
    import llm_client  # type: ignore


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


REGION_ALIASES = {'head': ['head', '头', '头部', '脑袋', '头皮', '额头', '太阳穴', 'forehead', 'temple'],
 'eyes': ['eyes', 'eye', '眼睛', '眼部', '眼眶', '视力', 'dry eyes'],
 'ears': ['ears', 'ear', '耳朵', '耳部', '耳鸣'],
 'nose_sinus': ['nose_sinus', 'nose', 'sinus', '鼻子', '鼻腔', '鼻窦', '鼻塞'],
 'mouth_jaw': ['mouth_jaw', 'mouth', 'jaw', '口腔', '嘴', '下颌', '牙关', '咬肌'],
 'throat': ['throat', '喉咙', '咽喉', '嗓子', '咽部'],
 'chest': ['chest', '胸', '胸口', '胸部', '呼吸', 'breathing'],
 'heart': ['heart', '心脏', '心口', '心前区', '心跳'],
 'shoulder_neck': ['shoulder_neck', 'neck', 'shoulder', '脖子', '颈部', '肩膀', '肩颈'],
 'upper_back': ['upper_back', '上背', '上背部', '肩胛', '背上部'],
 'lower_back': ['lower_back', '腰', '腰部', '腰背', '下背', 'lower back'],
 'stomach': ['stomach', '胃', '胃部', '上腹', '胃口', 'upper abdomen'],
 'abdomen': ['abdomen', 'belly', '肚子', '腹部', '肠胃', '腹胀'],
 'lower_abdomen_pelvis': ['lower_abdomen_pelvis', '下腹', '小腹', '盆腔', '经期', '痛经', '周期'],
 'skin': ['skin', '皮肤', '起疹', '瘙痒', '发红'],
 'hands': ['hands', 'hand', '手', '手部', '手心', '手臂', '手指'],
 'legs': ['legs', 'leg', '腿', '腿部', '膝盖', '脚', '脚踝'],
 'whole_body': ['whole_body', '全身', '身体', '浑身']}

REGION_LABELS = {'head': '头部',
 'eyes': '眼部',
 'ears': '耳部',
 'nose_sinus': '鼻腔/鼻窦',
 'mouth_jaw': '口腔/下颌',
 'throat': '咽喉',
 'chest': '胸口/呼吸',
 'heart': '心跳/心前区',
 'shoulder_neck': '肩颈',
 'upper_back': '上背部',
 'lower_back': '腰背',
 'stomach': '胃部/上腹',
 'abdomen': '腹部/肠胃',
 'lower_abdomen_pelvis': '下腹/盆腔',
 'skin': '皮肤',
 'hands': '手部',
 'legs': '腿部',
 'whole_body': '全身'}

SYMPTOM_ALIASES = {'headache': ['头疼', '头痛', '脑袋疼', '偏头痛', 'headache'],
 'dizziness': ['头晕', '眩晕', '发晕', 'dizzy', 'dizziness'],
 'brain_fog': ['脑雾', '反应慢', '注意力涣散', '脑袋空', 'brain fog'],
 'eye_strain': ['眼疲劳', '眼酸', '眼胀', '眼睛累', 'eye strain'],
 'blurred_vision': ['视物模糊', '看不清', '视线模糊', 'blurred vision'],
 'dry_eyes': ['眼干', '干眼', 'dry eyes'],
 'ear_ringing': ['耳鸣', '耳朵嗡嗡', 'ringing ears', 'tinnitus'],
 'nasal_congestion': ['鼻塞', '鼻子堵', '鼻腔不适', 'nasal congestion'],
 'jaw_tension': ['下颌紧', '咬牙', '牙关紧', '咬肌紧', 'jaw tension'],
 'throat_tightness': ['喉咙紧', '嗓子堵', '咽喉紧', 'throat tightness'],
 'dry_throat': ['嗓子干', '喉咙干', 'dry throat'],
 'chest_tightness': ['胸闷', '胸口闷', '胸口紧', '胸部紧', 'chest tight', 'tight chest'],
 'palpitation': ['心跳快', '心跳过快', '心慌', '心悸', 'palpitation', 'heart racing'],
 'shortness_of_breath': ['呼吸困难', '喘不上气', '气短', 'shortness of breath'],
 'stomach_cramp': ['胃痉挛', '胃抽', '胃痛', '胃疼', 'stomach cramp', 'stomach pain'],
 'acid_reflux': ['反酸', '烧心', '胃酸', 'acid reflux', 'heartburn'],
 'appetite_loss': ['没胃口', '食欲差', '不想吃', 'appetite loss'],
 'nausea': ['恶心', '想吐', '反胃', 'nausea'],
 'diarrhea': ['拉肚子', '腹泻', 'diarrhea'],
 'constipation': ['便秘', '排便困难', 'constipation'],
 'bloating': ['腹胀', '胀气', '肚子胀', 'bloating'],
 'lower_abdominal_cramp': ['下腹痛', '小腹痛', '小腹坠胀', 'lower abdominal cramp'],
 'menstrual_cramps': ['痛经', '经期腹痛', '周期相关不适', 'period cramps', 'menstrual cramps'],
 'muscle_tension': ['紧绷', '僵硬', '酸痛', '肩颈紧', '肌肉紧张', 'tension'],
 'back_pain': ['背痛', '腰痛', '腰酸', '后背疼', 'back pain'],
 'hand_shaking': ['手抖', '发抖', '手颤', 'shaking hands'],
 'cold_hands_feet': ['手脚冰凉', '手冷', '脚冷', 'cold hands', 'cold feet'],
 'numbness': ['麻木', '发麻', 'numbness'],
 'sweating': ['出汗', '冒汗', '冷汗', 'sweating'],
 'fatigue': ['疲惫', '累', '乏力', '没力气', 'fatigue', 'tired'],
 'sleepiness': ['犯困', '困倦', '想睡', 'sleepy'],
 'insomnia': ['失眠', '睡不着', '入睡困难', 'insomnia'],
 'restlessness': ['坐立不安', '烦躁', '静不下来', 'restless'],
 'skin_itching': ['皮肤痒', '瘙痒', 'itching']}

SYMPTOM_LABELS = {'headache': '头疼',
 'dizziness': '头晕',
 'brain_fog': '脑雾/注意力涣散',
 'eye_strain': '眼疲劳',
 'blurred_vision': '视物模糊',
 'dry_eyes': '眼干',
 'ear_ringing': '耳鸣',
 'nasal_congestion': '鼻塞',
 'jaw_tension': '下颌紧绷/咬牙',
 'throat_tightness': '喉咙紧',
 'dry_throat': '嗓子干',
 'chest_tightness': '胸闷',
 'palpitation': '心跳过快/心慌',
 'shortness_of_breath': '呼吸困难/气短',
 'stomach_cramp': '胃痉挛/胃痛',
 'acid_reflux': '反酸/烧心',
 'appetite_loss': '食欲下降',
 'nausea': '恶心',
 'diarrhea': '腹泻',
 'constipation': '便秘',
 'bloating': '腹胀',
 'lower_abdominal_cramp': '下腹痛/小腹坠胀',
 'menstrual_cramps': '经期腹痛/周期相关不适',
 'muscle_tension': '肌肉紧绷',
 'back_pain': '背痛/腰酸',
 'hand_shaking': '手抖',
 'cold_hands_feet': '手脚冰凉',
 'numbness': '麻木',
 'sweating': '出汗/冷汗',
 'fatigue': '疲惫/乏力',
 'sleepiness': '困倦',
 'insomnia': '失眠/入睡困难',
 'restlessness': '坐立不安',
 'skin_itching': '皮肤瘙痒'}


def _normalize_region(value: Any) -> str:
    raw = str(value or "").strip().lower()
    for key, aliases in REGION_ALIASES.items():
        if raw == key or raw in {item.lower() for item in aliases}:
            return key
    for key, aliases in REGION_ALIASES.items():
        if any(alias.lower() in raw for alias in aliases):
            return key
    return raw or "unknown"


def _normalize_symptom(value: Any) -> str:
    raw = str(value or "").strip().lower()
    for key, aliases in SYMPTOM_ALIASES.items():
        if raw == key or raw in {item.lower() for item in aliases}:
            return key
    for key, aliases in SYMPTOM_ALIASES.items():
        if any(alias.lower() in raw for alias in aliases):
            return key
    return raw or "unknown"


def _normalize_selected_regions(items: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        if isinstance(item, dict):
            raw_id = item.get("id") or item.get("region_id") or item.get("label")
            raw_label = item.get("label") or raw_id
        else:
            raw_id = item
            raw_label = item
        region_id = _normalize_region(raw_id)
        normalized.append({
            "id": region_id,
            "label": REGION_LABELS.get(region_id, str(raw_label or region_id)),
            "raw": item,
        })
    return normalized


def _normalize_symptoms(items: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        if isinstance(item, dict):
            raw_label = item.get("label") or item.get("id") or item.get("symptom")
            region_id = _normalize_region(item.get("region_id") or item.get("region") or "")
            severity = item.get("severity")
            duration = item.get("duration") or ""
        else:
            raw_label = item
            region_id = "unknown"
            severity = None
            duration = ""
        symptom_id = _normalize_symptom(raw_label)
        try:
            severity_value = int(severity) if severity is not None and str(severity) != "" else None
        except Exception:
            severity_value = None
        normalized.append({
            "id": symptom_id,
            "label": SYMPTOM_LABELS.get(symptom_id, str(raw_label or symptom_id)),
            "region_id": region_id,
            "severity": severity_value,
            "duration": str(duration or ""),
            "raw": item,
        })
    return normalized


def _collect_recent_diaries(participant_code: str | None, limit: int) -> list[dict[str, Any]]:
    if not participant_code:
        return []
    try:
        entries = list_diary_entries(participant_code)
    except Exception as error:
        print(f"[body_sensation] recent diary load skipped: {error}")
        return []

    result = []
    for entry in (entries or [])[: max(0, min(limit, 10))]:
        if not isinstance(entry, dict):
            continue
        text = (
            entry.get("raw_text")
            or entry.get("transcript_text")
            or entry.get("text")
            or ""
        )
        result.append({
            "created_at": entry.get("created_at"),
            "raw_text": str(text)[:800],
            "final_label": entry.get("final_label") or entry.get("emotion_label"),
            "va_mapping_json": entry.get("va_mapping_json"),
            "text_emotion_json": entry.get("text_emotion_json"),
        })
    return result



def _build_recent_diary_context(recent_diaries: list[dict[str, Any]]) -> str:
    lines = []
    for index, entry in enumerate(recent_diaries or [], start=1):
        text = str(entry.get("raw_text") or "").strip()
        label = entry.get("final_label") or ""
        created_at = entry.get("created_at") or ""
        if not text:
            continue
        lines.append(f"{index}. 时间：{created_at}；情绪标签：{label}；内容：{text[:300]}")
    return "\n".join(lines)


def _strip_llm_content(content: str) -> str:
    content = str(content or "").strip()
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    content = content.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    return content


def _json_from_llm_content(content: str) -> dict[str, Any] | None:
    content = _strip_llm_content(content)
    try:
        value = json.loads(content)
        return value if isinstance(value, dict) else None
    except Exception:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            value = json.loads(content[start : end + 1])
            return value if isinstance(value, dict) else None
        except Exception:
            return None
    return None


def _first_value(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data.get(key) not in (None, "", []):
            return data.get(key)
    return default


def _normalize_possible_links(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        if isinstance(item, dict):
            label = _first_value(item, ["label", "标签", "title", "name", "type"], "")
            explanation = _first_value(item, ["explanation", "description", "说明", "解释", "reason"], "")
            confidence = _first_value(item, ["confidence", "置信度"], "low")
            normalized.append({
                "label": str(label or "可能相关线索"),
                "explanation": str(explanation or ""),
                "confidence": str(confidence or "low"),
            })
        elif isinstance(item, str):
            normalized.append({
                "label": "可能相关线索",
                "explanation": item,
                "confidence": "low",
            })
    return normalized


def _normalize_steps(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = [line.strip(" -0123456789.、\t") for line in value.splitlines()]
        return [item for item in parts if item]
    return []


def _normalize_body_llm_advice(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    data = raw

    response_text = data.get("response")
    if isinstance(response_text, str) and response_text.strip():
        text_value = response_text.strip()
        parts = [part.strip() for part in re.split(r"[。；;\n]+", text_value) if part.strip()]
        title = parts[0][:36] if parts else "先照顾这次具体的身体信号"
        steps = [part for part in parts if any(word in part for word in ["先", "喝", "坐", "走", "呼吸", "观察", "记录", "补", "暂停"])]
        return {
            "title": title,
            "summary": text_value,
            "state_reading": text_value,
            "possible_links": [],
            "steps": steps[:6],
            "reflection_prompt": "你可以只记一句：这次不适是在饿、渴、久坐、用脑过久，还是任务最紧的时候最明显？",
            "when_to_seek_help": [
                "如果症状持续加重、反复出现，或出现胸痛、呼吸困难、晕厥、剧烈头痛、麻木无力、血便或高烧，请及时就医。"
            ],
            "not_medical_diagnosis": True,
            "_partial_from_response": True,
        }

    # Qwen sometimes wraps the useful object under advice/result/data.
    for wrapper_key in ["advice", "result", "data", "output"]:
        wrapped = data.get(wrapper_key)
        if isinstance(wrapped, dict):
            data = wrapped
            break

    title = _first_value(data, ["title", "标题", "建議標題", "建议标题"])
    summary = _first_value(data, ["summary", "总结", "總結", "摘要", "整体分析", "回应", "additional_notes"])
    state_reading = _first_value(
        data,
        ["state_reading", "状态理解", "状态解读", "状态读取", "状态分析", "更细腻的状态理解", "additional_notes"],
        "",
    )
    possible_links = _first_value(
        data,
        ["possible_links", "身体情绪线索", "身体-情绪线索", "可能关联", "可能关系", "links", "clues"],
        [],
    )
    steps = _first_value(
        data,
        ["steps", "建议步骤", "可尝试步骤", "行动建议", "照护步骤", "建议", "suggestions"],
        [],
    )
    reflection_prompt = _first_value(
        data,
        ["reflection_prompt", "继续记录提示", "记录提示", "反思提示", "观察提示"],
        "",
    )
    when_to_seek_help = _first_value(
        data,
        ["when_to_seek_help", "就医提示", "何时求助", "安全提醒", "风险提示"],
        [],
    )

    if not title and (summary or state_reading):
        title = "先照顾这次具体的身体信号"

    if not reflection_prompt:
        reflection_prompt = "你可以只记一句：这次不适是在饿、渴、久坐、用脑过久，还是任务最紧的时候最明显？"

    if not when_to_seek_help:
        when_to_seek_help = [
            "如果症状持续加重、反复出现，或出现胸痛、呼吸困难、晕厥、剧烈头痛、麻木无力、血便或高烧，请及时就医。"
        ]

    if isinstance(state_reading, list):
        state_reading = " ".join(str(item).strip() for item in state_reading if str(item).strip())

    normalized = {
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "state_reading": str(state_reading or "").strip(),
        "possible_links": _normalize_possible_links(possible_links),
        "steps": _normalize_steps(steps),
        "reflection_prompt": str(reflection_prompt or "").strip(),
        "when_to_seek_help": _normalize_steps(when_to_seek_help),
        "not_medical_diagnosis": True,
    }

    useful_score = 0
    if normalized["title"]:
        useful_score += 1
    if normalized["summary"]:
        useful_score += 1
    if normalized["state_reading"]:
        useful_score += 1
    if normalized["steps"]:
        useful_score += 1

    if useful_score < 2:
        print("[body_sensation] LLM advice ignored because required fields are missing. keys=", list(data.keys()))
        return None

    return normalized


def _call_body_llm(input_payload: dict[str, Any]) -> dict[str, Any] | None:
    if not _env_bool("BODY_ADVICE_LLM_ENABLED", True):
        return None

    model = os.getenv("BODY_LLM_MODEL", "").strip() or None
    try:
        temperature = float(os.getenv("BODY_LLM_TEMPERATURE", "0.15"))
    except ValueError:
        temperature = 0.15
    try:
        max_tokens = int(os.getenv("BODY_LLM_MAX_TOKENS", "4096"))
    except ValueError:
        max_tokens = 4096

    system_prompt = """你是一个身体感受与情绪状态陪伴助手，不是医生，也不是诊断系统。

用户现在有身体上的疑惑。你的任务不是让用户自己判断是哪一篇日记造成了不舒服，而是综合用户最近的多条日记、本次选择的身体部位和感受、补充描述、情绪分析结果，帮助用户整理“可能相关的状态线索”和“可以先做的低风险照护动作”。

核心原则：
1. 本次身体感受是输出中心。
   用户这次选择的 selected_regions 和 symptoms 是主线。你必须先回应这些身体部位和感受。
   如果用户选择了头晕、嗓子干、胃痛、胸闷、肩颈紧，就必须围绕这些感受展开。

2. 最近日记是整体背景，不需要用户选择“哪条日记导致不适”。
   你会看到 recent_diaries / recent_diary_context。它们代表用户最近一段时间的生活、情绪和身体状态。
   你要主动判断哪些内容可能和本次身体感受有关，哪些只是情绪背景，哪些是积极资源，哪些暂时无关。

3. 不要乱归因。
   不能把积极事件、社交事件、喜欢某人、开心片段直接说成本次身体不适的原因。
   如果某条开心日记和身体不适没有明显关系，你可以把它作为 positive_resource，而不是病因。

4. 也不要忽略积极体验。
   如果用户最近有开心、喜欢、期待、被支持、放松的记录，你要温柔肯定这些正面感受。
   但正面情绪不能覆盖用户此刻的不适。你要同时看见：用户有开心的部分，也有身体正在求助的部分。

5. 要肯定负面感受。
   如果用户有疲惫、焦虑、低落、紧张、压抑、身体不适，不要轻描淡写。
   可以说“这不是你太脆弱，而是身体在提示今天的消耗和补给可能不太平衡”。
   但不要夸张、不要煽情、不要医学诊断。

你必须把日记背景分成四类来思考：
- direct_body_context：可能直接相关的身体线索，例如睡眠、饮食、喝水、咖啡因、久坐、用脑强度、任务压力、明显身体不适。
- indirect_emotion_context：可能间接相关的情绪线索，例如兴奋、紧张、关系刺激、情绪波动。
- positive_resource：积极资源，例如开心、喜欢、期待、被支持、放松、觉得有生命力。
- unrelated_context：暂时看不出和本次身体感受有关的内容。

重要边界：
- 不能做医学诊断。
- 不能说“你就是因为……导致……”
- 可以说“可能和……叠加有关”“从记录看，更像是……在提醒你”
- 如果用户有胸痛、呼吸困难、晕厥、剧烈头痛、麻木无力、血便、高烧等红旗风险，必须优先提示及时就医。
- 不要询问或推断用户性别、疾病、身份。
- 涉及经期相关不适时，只把它当作用户主动选择的身体感受，不扩展隐私判断。

语言风格：
- 温柔，但不要煽情。
- 具体，但不要武断。
- 像一个认真看完用户最近记录的人，而不是健康百科。
- 不要使用空泛表达：多休息、放松一下、保持好心情、注意身体、调整状态、释放压力。
- 如果要表达类似意思，必须写成具体动作，例如“先坐下，喝半杯温水，2分钟内不要继续盯屏幕”。

输出限制：
- 只输出合法 JSON。
- 不要输出 Markdown。
- 不要输出 <think>。
- 禁止使用 response 字段。
- 禁止使用 clues / suggestions / additional_notes 作为顶层字段。
- 禁止把所有内容塞进一个字符串。"""

    user_prompt = (
        """请严格输出下面这个 JSON 结构。顶层字段必须完全使用这些英文 key：

{
  "title": "一句贴合用户当前身体状态的短标题",
  "summary": "综合本次身体感受和最近多条日记后的状态总结",
  "state_reading": "3到5句话，细腻解释当前身体感受与作息、饮食、用脑、压力、正面情绪资源、负面情绪负荷之间的可能关系，但不诊断",
  "possible_links": [
    {
      "label": "线索名称",
      "explanation": "引用具体输入线索的解释",
      "confidence": "low"
    }
  ],
  "steps": [
    "具体动作1",
    "具体动作2",
    "具体动作3",
    "具体动作4"
  ],
  "reflection_prompt": "一句轻量记录提示",
  "when_to_seek_help": [
    "安全边界提示"
  ],
  "not_medical_diagnosis": true
}

写作任务：

1. 先处理本次身体感受。
   如果本次输入是头晕，就围绕头晕。
   如果本次输入是嗓子干，就围绕咽喉、补水、用嗓、环境刺激。
   如果本次输入是胃痛，就围绕胃部。
   如果本次输入是肩颈紧，就围绕肩颈。
   不要一上来讲无关日记里的开心事件，也不要转移到其他身体部位。

2. 再综合最近多条日记。
   用户不需要自己选择哪条日记导致不适，你要帮用户判断：
   - 哪些日记像 direct_body_context，可以解释本次身体感受的可能背景；
   - 哪些日记像 indirect_emotion_context，只是情绪波动背景；
   - 哪些日记像 positive_resource，是今天值得保留的正面体验；
   - 哪些日记像 unrelated_context，暂时不强行解释。

3. 如果近期日记里有开心、喜欢、兴奋、期待等积极记录：
   你要肯定它们，但不能让它们抢走主线。
   可以这样写：
   “那条让你开心的记录，不太像这次头晕和嗓子干的直接来源，但它说明今天也有让你变亮一点的东西。等身体缓下来，可以把它当作一种情绪资源，而不是把整天都归结为不舒服。”

4. 如果近期日记里有疲惫、压抑、焦虑、低落、委屈、压力：
   你要肯定这些负面感受。
   可以这样写：
   “这些不舒服不需要被马上解释成你哪里做错了。它更像是身体把最近的消耗、紧绷和补给不足一起显示出来。”

5. summary 必须包含本次输入里的具体线索。
   例如：起床晚、午饭少、喝水少、久坐、高强度学习、头晕、嗓子干、肩颈紧、食欲下降。
   没有出现的线索不要编造。

6. state_reading 是最重要的字段。
   它要像认真读过用户最近记录的人写出来。
   不要写成医学百科。
   不要写成模板安慰。
   可以使用这种表达：
   “这不是单纯的‘身体不舒服’，更像是今天的消耗比补给多：吃得少、喝水少、用脑久，身体先用头晕提醒你停一下。”
   也可以写：
   “开心的记录是今天的情绪资源，但它不能替代身体需要的水、食物和停顿。”

7. possible_links 写 2 到 4 条。
   每条 explanation 都必须引用具体线索。
   label 可以使用这些类型：
   - 直接身体线索｜饮食和补水
   - 直接身体线索｜久坐和用脑强度
   - 直接身体线索｜咽喉干燥和水分不足
   - 间接情绪线索｜兴奋或压力波动
   - 积极资源｜让心情变亮的事件
   - 负面情绪线索｜压力或低落没有被照顾
   - 暂时无关背景｜不强行归因

8. steps 写 4 到 6 条。
   每条都必须具体到用户可以马上做。
   必须包含：
   - 一个立刻稳定身体的动作；
   - 一个补水/进食/减少刺激的动作；
   - 一个肩颈、呼吸或姿势释放动作；
   - 一个任务降载动作；
   - 一个后续观察动作。
   每条建议要说明为什么适合用户现在的状态。

9. reflection_prompt 要轻，不要像问卷。
   好例子：
   “你可以只记一句：这次头晕是在饿、渴、久坐，还是任务最紧的时候最明显？”

10. 不要说：
   - 根据您提供的信息
   - 建议您保持良好心态
   - 多休息
   - 放松一下
   - 注意身体
   - 你的症状是由……导致的

11. 输出前自检：
   顶层字段必须包含 title、summary、state_reading、possible_links、steps、reflection_prompt、when_to_seek_help、not_medical_diagnosis。
   如果你想输出 response、clues、suggestions、additional_notes，必须改写成上面的标准字段。
   如果 title 或 summary 没有回应本次身体感受，请重写。
   如果只讲积极日记而没有回应身体不适，请重写。

下面是输入 JSON：
"""
        + json.dumps(input_payload, ensure_ascii=False, indent=2)
    )

    try:
        parsed = llm_client.chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if isinstance(parsed, dict):
            print("[body_sensation] parsed LLM keys:", list(parsed.keys()))
            return parsed
        return None
    except Exception as error:
        print(f"[body_sensation] LLM skipped: {error}")
        return None


def _analyze_emotion_context(text: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    try:
        text_emotion = analyze_text_emotion(text)
        va_mapping = map_segments(text_emotion.get("segments", []))
        overall = va_mapping.get("overall", {})
        candidates = [
            item.get("label")
            for item in overall.get("candidates", [])
            if isinstance(item, dict) and item.get("label")
        ]
        evidence = []
        for seg in text_emotion.get("segments", []):
            if isinstance(seg, dict):
                evidence.extend(seg.get("evidence", []) or [])
        return (
            {
                "primary_label": overall.get("label", "中性"),
                "quadrant": overall.get("quadrant", "neutral"),
                "valence": overall.get("valence", 0.0),
                "arousal": overall.get("arousal", 0.0),
                "confidence": overall.get("confidence", 0.0),
                "color": overall.get("color", "#94A3B8"),
                "candidate_labels": candidates[:6],
                "evidence": evidence[:8],
            },
            text_emotion,
            va_mapping,
        )
    except Exception as error:
        print(f"[body_sensation] emotion analysis fallback: {error}")
        fallback = map_va(0.0, 0.0, 0.0)
        return (
            {
                "primary_label": fallback.get("label", "中性"),
                "quadrant": fallback.get("quadrant", "neutral"),
                "valence": fallback.get("valence", 0.0),
                "arousal": fallback.get("arousal", 0.0),
                "confidence": fallback.get("confidence", 0.0),
                "color": fallback.get("color", "#94A3B8"),
                "candidate_labels": [],
                "evidence": [],
            },
            {},
            {"overall": fallback, "segments": []},
        )


def _detect_red_flags(
    symptoms: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    text: str,
) -> dict[str, Any]:
    joined = " ".join(
        [text]
        + [str(item.get("label", "")) for item in symptoms]
        + [str(item.get("duration", "")) for item in symptoms]
        + [str(item.get("label", "")) for item in regions]
    ).lower()

    symptom_ids = {item.get("id") for item in symptoms}
    region_ids = {item.get("id") for item in regions} | {item.get("region_id") for item in symptoms}

    red_flags = []

    def hit(keywords: list[str]) -> bool:
        return any(word.lower() in joined for word in keywords)

    if (
        "chest" in region_ids
        or "chest_tightness" in symptom_ids
        or "palpitation" in symptom_ids
        or "shortness_of_breath" in symptom_ids
    ):
        if hit(["胸痛", "胸口痛", "压榨", "压迫", "呼吸困难", "喘不上气", "冷汗", "晕厥", "昏厥", "放射到", "左臂", "下颌"]):
            red_flags.append("胸口压迫/疼痛、呼吸困难、冷汗或放射痛需要优先排除急症风险。")

    if "headache" in symptom_ids or "head" in region_ids:
        if hit(["突然", "剧烈", "最严重", "爆炸", "麻木", "无力", "说话困难", "意识混乱", "视力", "高烧", "颈部僵硬", "外伤"]):
            red_flags.append("突然或剧烈头痛，伴随神经症状、发热颈硬或外伤，需要及时就医。")

    if "diarrhea" in symptom_ids or "abdomen" in region_ids or "stomach" in region_ids:
        if hit(["血便", "黑便", "高烧", "脱水", "尿很少", "三天", "3天", "频繁呕吐", "一直吐"]):
            red_flags.append("腹泻/胃肠不适伴随血便、高烧、脱水或持续多日，需要及时就医。")

    severe_symptoms = [
        item for item in symptoms
        if isinstance(item.get("severity"), int) and item["severity"] >= 5
    ]
    if severe_symptoms:
        red_flags.append("用户标记的严重程度较高，建议不要只按情绪压力处理。")

    if red_flags:
        return {
            "risk_level": "high",
            "red_flags": red_flags,
            "not_medical_diagnosis": True,
            "message": "这些提示不能替代医疗判断。若症状明显、持续加重或你感到不安全，请及时联系医生或当地急救服务。",
        }

    return {
        "risk_level": "low",
        "red_flags": [],
        "not_medical_diagnosis": True,
        "message": "以下内容只用于情绪支持和低风险自我照护，不构成医学诊断。",
    }


def _build_possible_links(
    symptoms: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    emotion_context: dict[str, Any],
    text: str,
) -> list[dict[str, Any]]:
    symptom_ids = {item.get("id") for item in symptoms}
    region_ids = {item.get("id") for item in regions} | {item.get("region_id") for item in symptoms}
    quadrant = emotion_context.get("quadrant")
    arousal = float(emotion_context.get("arousal") or 0.0)
    valence = float(emotion_context.get("valence") or 0.0)
    joined = text.lower()

    links = []

    if quadrant == "high_negative" or (arousal > 0.35 and valence < 0):
        if {"head", "chest", "shoulder_neck"} & region_ids or {"headache", "chest_tightness", "palpitation", "muscle_tension"} & symptom_ids:
            links.append({
                "type": "stress_overload",
                "label": "压力过载线索",
                "description": "当前文本更接近高唤醒负性状态，头部、胸口或肩颈不适可能与紧张、任务压力和身体绷紧有关。",
                "confidence": "medium",
            })

    if {"stomach", "abdomen"} & region_ids or {"stomach_cramp", "diarrhea", "nausea"} & symptom_ids:
        if any(word in joined for word in ["没吃", "吃得少", "午饭", "咖啡", "空腹", "晚饭", "deadline", "学习", "压力"]):
            links.append({
                "type": "digestive_load",
                "label": "饮食和压力叠加线索",
                "description": "胃肠不适可能与进食延迟、咖啡因、空腹和压力唤醒叠加有关。",
                "confidence": "medium",
            })

    if "dizziness" in symptom_ids or "头晕" in joined or "dizzy" in joined:
        links.append({
            "type": "energy_drop",
            "label": "能量不足线索",
            "description": "头晕可能与睡眠不足、进食较少、长时间学习或补水不足有关。若反复或加重，应优先考虑身体原因。",
            "confidence": "low",
        })

    if not links:
        links.append({
            "type": "general_body_signal",
            "label": "身体信号记录",
            "description": "这些身体感受可以先作为情绪和生活节律的信号记录下来，观察它们是否和压力、睡眠、饮食或关系事件同步出现。",
            "confidence": "low",
        })

    return links


def _fallback_advice(
    symptoms: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    emotion_context: dict[str, Any],
    possible_links: list[dict[str, Any]],
    safety: dict[str, Any],
) -> dict[str, Any]:
    symptom_labels = "、".join([item.get("label", "") for item in symptoms if item.get("label")]) or "身体不适"
    region_labels = "、".join([item.get("label", "") for item in regions if item.get("label")]) or "身体"

    if safety.get("risk_level") == "high":
        return {
            "source": "fallback",
            "title": "先确认安全，再处理情绪压力",
            "summary": f"你记录的是{region_labels}的{symptom_labels}。其中有一些信号不适合只按压力或情绪处理。",
            "possible_links": possible_links,
            "steps": [
                "如果症状明显、突然出现、持续加重，先暂停当前活动，不要继续硬扛。",
                "联系身边可信任的人，说明你的症状和持续时间。",
                "如果出现胸痛、呼吸困难、晕厥、明显麻木无力、剧烈头痛等情况，请及时联系医生或当地急救服务。",
            ],
            "reflection_prompt": "等安全稳定后，再记录症状出现前 1 小时内的睡眠、饮食、咖啡因、压力事件和情绪变化。",
            "when_to_seek_help": safety.get("red_flags", []),
            "not_medical_diagnosis": True,
        }

    steps = [
        "先停下当前任务 3 到 5 分钟，把屏幕、消息和学习材料暂时放到一边。",
        "喝几口温水，检查自己是否空腹、进食过少或已经连续坐了很久。",
        "做 6 轮慢呼吸：吸气 4 秒，呼气 6 秒，重点感受肩颈、胸口和腹部有没有松一点。",
        "把接下来 30 分钟的任务缩小成一个最小动作，不要同时处理多个任务。",
    ]

    if any(item.get("id") == "headache" for item in symptoms):
        steps.insert(1, "如果是头疼，先减少屏幕刺激，放松下颌和肩颈，避免继续加咖啡因来硬撑。")
    if any(item.get("id") in {"stomach_cramp", "diarrhea", "nausea"} for item in symptoms):
        steps.insert(1, "如果是胃肠不适，先避免冷饮、辛辣和继续空腹，选择温和、少量的食物观察。")
    if any(item.get("id") == "dizziness" for item in symptoms):
        steps.insert(1, "如果是头晕，先坐下或靠稳，补水，避免突然站起；如果反复或加重，要优先考虑就医。")

    return {
        "source": "fallback",
        "title": "先把身体信号和今天的状态连起来看",
        "summary": f"你记录的是{region_labels}的{symptom_labels}。我会把它先当作一个身体信号来看，而不是急着下结论。结合当前情绪线索，它可能不是单一原因，而是压力、作息、饮食和身体紧绷叠加后的结果。",
        "state_reading": "这类不适更值得关注的是它出现前发生了什么：有没有吃得少、喝水少、连续用脑、久坐、睡眠不足，或者一直压着某种情绪没有处理。",
        "possible_links": possible_links,
        "steps": steps[:6],
        "reflection_prompt": "你可以补记一句：这个不适是在压力最高时出现，还是在睡眠、饮食、咖啡因或久坐之后更明显？",
        "when_to_seek_help": [
            "如果症状持续加重、反复出现，或你直觉上觉得不安全，请咨询医生。",
            "如果出现胸痛、呼吸困难、晕厥、剧烈头痛、麻木无力、血便或高烧，请及时就医。",
        ],
        "not_medical_diagnosis": True,
    }


def _log_body_sensation_event(
    participant_code: str | None,
    regions: list[dict[str, Any]],
    symptoms: list[dict[str, Any]],
    safety: dict[str, Any],
    emotion_context: dict[str, Any],
) -> bool:
    if not participant_code:
        return False
    try:
        log_usage_event(
            participant_code,
            "body_sensation_advice",
            {
                "selected_regions": regions,
                "symptoms": symptoms,
                "risk_level": safety.get("risk_level"),
                "primary_label": emotion_context.get("primary_label"),
                "quadrant": emotion_context.get("quadrant"),
                "valence": emotion_context.get("valence"),
                "arousal": emotion_context.get("arousal"),
                "color": emotion_context.get("color"),
            },
        )
        return True
    except Exception as error:
        print(f"[body_sensation] usage event skipped: {error}")
        return False


def generate_body_sensation_advice(payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}

    participant_code = str(payload.get("participant_code") or "").strip() or None
    journal_text = str(payload.get("journal_text") or "").strip()
    free_text = str(payload.get("free_text") or "").strip()
    include_recent_diaries = bool(payload.get("include_recent_diaries", True))
    recent_diary_limit = int(payload.get("recent_diary_limit") or 3)

    regions = _normalize_selected_regions(payload.get("selected_regions") or [])
    symptoms = _normalize_symptoms(payload.get("symptoms") or [])

    symptom_text = "；".join(
        [
            f"{item.get('label')}，严重程度：{item.get('severity') or '未填'}，持续时间：{item.get('duration') or '未填'}"
            for item in symptoms
        ]
    )

    combined_text = "\n".join(
        part for part in [
            f"当前日记：{journal_text}" if journal_text else "",
            f"身体感受补充：{free_text}" if free_text else "",
            f"用户选择的症状：{symptom_text}" if symptom_text else "",
        ]
        if part
    ).strip()

    if not combined_text:
        combined_text = "用户没有填写日记文本，只选择了身体感受。"

    recent_diaries = _collect_recent_diaries(participant_code, recent_diary_limit) if include_recent_diaries else []
    recent_diary_context = _build_recent_diary_context(recent_diaries)

    analysis_text = combined_text
    if recent_diary_context:
        analysis_text = (
            combined_text
            + "\n\n以下是用户今天或近期的其他日记记录，请一起作为状态背景，不要只看单条输入：\n"
            + recent_diary_context
        )

    emotion_context, text_emotion, va_mapping = _analyze_emotion_context(analysis_text)
    safety = _detect_red_flags(symptoms, regions, analysis_text)
    possible_links = _build_possible_links(symptoms, regions, emotion_context, analysis_text)

    fallback = _fallback_advice(symptoms, regions, emotion_context, possible_links, safety)

    if recent_diary_context and safety.get("risk_level") != "high":
        fallback["summary"] = (
            "我会把你这次填写的身体感受，和今天/近期的多条日记一起看。"
            + fallback.get("summary", "")
            + f" 这次已参考最近 {len(recent_diaries)} 条记录，所以建议会更偏向整体状态，而不是只解释单次不适。"
        )
        fallback["reflection_prompt"] = (
            "你可以继续观察：这些身体感受是否总是在睡眠不足、进食变少、长时间学习、关系压力或任务堆积之后出现？"
        )

    current_input_priority = {
        "must_focus_on_this_request": True,
        "journal_text": journal_text,
        "free_text": free_text,
        "selected_regions": regions,
        "symptoms": symptoms,
        "instruction": (
            "本次身体感受是主线。建议必须优先围绕这些部位和症状。"
            "近期日记只能作为背景，不允许覆盖本次身体感受。"
        ),
    }

    llm_input = {
        "current_input_priority": current_input_priority,
        "emotion_context": emotion_context,
        "possible_links": possible_links,
        "safety": safety,
        "recent_diary_context": recent_diary_context,
        "recent_diaries": recent_diaries,
        "analysis_scope": "current_input_plus_recent_diaries",
        "output_rules": [
            "不做医学诊断",
            "只输出可能相关线索和低风险建议",
            "必须优先回应 current_input_priority",
            "近期日记只能辅助解释，不允许带偏主线",
            "如果命中红旗风险，优先提醒就医",
        ],
    }

    # Final prompt behavior:
    # The user should not need to pick which diary caused the body sensation.
    # Send all recent diaries as background and let the prompt classify their relationship.
    llm_input["recent_diaries"] = recent_diaries
    llm_input["recent_diary_context"] = recent_diary_context
    llm_input["recent_diary_usage_rule"] = (
        "用户不需要选择哪条日记导致不适。"
        "current_input_priority 是本次身体感受主线；"
        "recent_diaries 是最近状态背景；"
        "模型需要自行区分 direct_body_context、indirect_emotion_context、positive_resource、unrelated_context。"
    )

    llm_advice = None
    if safety.get("risk_level") != "high":
        llm_advice = _call_body_llm(llm_input)

    advice = fallback
    normalized_llm_advice = _normalize_body_llm_advice(llm_advice)

    if isinstance(normalized_llm_advice, dict):
        advice = {
            "source": "llm_partial" if normalized_llm_advice.get("_partial_from_response") else "llm",
            "title": normalized_llm_advice.get("title") or fallback["title"],
            "summary": normalized_llm_advice.get("summary") or fallback["summary"],
            "state_reading": normalized_llm_advice.get("state_reading") or fallback.get("state_reading", ""),
            "possible_links": normalized_llm_advice.get("possible_links") or possible_links,
            "steps": normalized_llm_advice.get("steps") or fallback["steps"],
            "reflection_prompt": normalized_llm_advice.get("reflection_prompt") or fallback["reflection_prompt"],
            "when_to_seek_help": normalized_llm_advice.get("when_to_seek_help") or fallback["when_to_seek_help"],
            "not_medical_diagnosis": True,
        }

    logged = _log_body_sensation_event(participant_code, regions, symptoms, safety, emotion_context)

    return {
        "status": "success",
        "body_sensation": {
            "selected_regions": regions,
            "symptoms": symptoms,
        },
        "emotion_context": emotion_context,
        "possible_links": possible_links,
        "advice": advice,
        "safety": safety,
        "recent_diaries_used": len(recent_diaries),
        "analysis_scope": "current_input_plus_recent_diaries" if recent_diary_context else "current_input_only",
        "logged": logged,
        "debug": {
            "llm_enabled": _env_bool("BODY_ADVICE_LLM_ENABLED", True),
            "advice_source": advice.get("source"),
        },
    }
