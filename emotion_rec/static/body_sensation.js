const BODY_PARTICIPANT_STORAGE_KEYS = [
  "emomirror.participant",
  "emotype_participant_code",
  "participant_code",
  "participantCode",
  "currentParticipantCode",
];

const BODY_STRUCTURE = [
  { id: "head", label: "头部", symptoms: [
    { id: "headache", label: "头疼" },
    { id: "dizziness", label: "头晕" },
    { id: "brain_fog", label: "脑雾/注意力涣散" },
    { id: "clear_head", label: "头脑清晰", positive: true },
    { id: "focused", label: "专注有力", positive: true },
  ]},
  { id: "eyes", label: "眼部", symptoms: [
    { id: "eye_strain", label: "眼疲劳" },
    { id: "dry_eyes", label: "眼干" },
    { id: "blurred_vision", label: "视物模糊" },
    { id: "bright_eyes", label: "眼神明亮", positive: true },
  ]},
  { id: "throat_mouth", label: "口咽", symptoms: [
    { id: "throat_tightness", label: "喉咙紧/异物感" },
    { id: "dry_throat", label: "嗓子干" },
    { id: "jaw_tension", label: "下颌/牙关紧绷" },
    { id: "voice_clear", label: "声音通畅", positive: true },
  ]},
  { id: "chest", label: "胸口", symptoms: [
    { id: "chest_tightness", label: "胸闷/压迫感" },
    { id: "palpitation", label: "心跳过快/心慌" },
    { id: "short_breath", label: "呼吸困难/气短" },
    { id: "chest_open", label: "呼吸顺畅", positive: true },
    { id: "heart_warm", label: "心里温暖", positive: true },
  ]},
  { id: "shoulder_neck", label: "肩颈", symptoms: [
    { id: "neck_stiff", label: "颈部僵硬" },
    { id: "shoulder_pain", label: "肩膀酸痛" },
    { id: "muscle_tight", label: "肌肉紧绷" },
    { id: "shoulder_relax", label: "肩颈放松", positive: true },
  ]},
  { id: "stomach", label: "胃部", symptoms: [
    { id: "stomach_pain", label: "胃痛/痉挛" },
    { id: "nausea", label: "恶心/反胃" },
    { id: "appetite_loss", label: "食欲下降" },
    { id: "bloating", label: "腹胀/胀气" },
    { id: "appetite_good", label: "食欲好", positive: true },
    { id: "stomach_comfy", label: "胃部舒适", positive: true },
  ]},
  { id: "back", label: "腰背", symptoms: [
    { id: "lower_back", label: "腰酸背痛" },
    { id: "back_stiff", label: "背部僵硬" },
    { id: "back_relax", label: "腰背舒展", positive: true },
  ]},
  { id: "hands", label: "手部", symptoms: [
    { id: "hand_shaking", label: "手抖" },
    { id: "cold_hands", label: "手冰凉" },
    { id: "sweaty_hands", label: "手心出汗" },
    { id: "hands_warm", label: "双手温暖", positive: true },
  ]},
  { id: "legs", label: "腿部", symptoms: [
    { id: "leg_heavy", label: "腿沉/无力" },
    { id: "cold_feet", label: "脚冰凉" },
    { id: "restless_legs", label: "腿部躁动不安" },
    { id: "legs_light", label: "步伐轻盈", positive: true },
  ]},
  { id: "whole_body", label: "全身", symptoms: [
    { id: "fatigue", label: "疲惫/乏力" },
    { id: "insomnia", label: "失眠/睡眠差" },
    { id: "sweating", label: "出汗/冷汗" },
    { id: "restless", label: "坐立不安" },
    { id: "energized", label: "精力充沛", positive: true },
    { id: "calm_body", label: "全身放松", positive: true },
    { id: "grounded", label: "踏实稳定", positive: true },
  ]},
];

const BODY_LABEL_EN = {
  head: "Head",
  headache: "Headache",
  dizziness: "Dizziness",
  brain_fog: "Brain fog / scattered attention",
  clear_head: "Clear mind",
  focused: "Focused",
  eyes: "Eyes",
  eye_strain: "Eye strain",
  dry_eyes: "Dry eyes",
  blurred_vision: "Blurred vision",
  bright_eyes: "Bright eyes",
  throat_mouth: "Mouth / throat",
  throat_tightness: "Throat tightness / lump sensation",
  dry_throat: "Dry throat",
  jaw_tension: "Jaw tension",
  voice_clear: "Clear voice",
  chest: "Chest",
  chest_tightness: "Chest tightness / pressure",
  palpitation: "Fast heartbeat / palpitation",
  short_breath: "Shortness of breath",
  chest_open: "Breathing easily",
  heart_warm: "Warm-hearted",
  shoulder_neck: "Shoulders / neck",
  neck_stiff: "Neck stiffness",
  shoulder_pain: "Shoulder ache",
  muscle_tight: "Muscle tension",
  shoulder_relax: "Relaxed shoulders / neck",
  stomach: "Stomach",
  stomach_pain: "Stomach pain / cramps",
  nausea: "Nausea",
  appetite_loss: "Loss of appetite",
  bloating: "Bloating / gas",
  appetite_good: "Good appetite",
  stomach_comfy: "Comfortable stomach",
  back: "Lower back / back",
  lower_back: "Lower back pain",
  back_stiff: "Back stiffness",
  back_relax: "Loose back",
  hands: "Hands",
  hand_shaking: "Shaking hands",
  cold_hands: "Cold hands",
  sweaty_hands: "Sweaty palms",
  hands_warm: "Warm hands",
  legs: "Legs",
  leg_heavy: "Heavy / weak legs",
  cold_feet: "Cold feet",
  restless_legs: "Restless legs",
  legs_light: "Light steps",
  whole_body: "Whole body",
  fatigue: "Fatigue / weakness",
  insomnia: "Insomnia / poor sleep",
  sweating: "Sweating / cold sweat",
  restless: "Restlessness",
  energized: "Energized",
  calm_body: "Relaxed body",
  grounded: "Grounded",
};

const BODY_EMOTION_LABEL_EN = {
  "中性": "Neutral",
  "不明确": "Unclear",
  "未明确": "Unclear",
  "不安": "Uneasy",
  "焦虑": "Anxious",
  "紧张": "Nervous",
  "紧绷": "Tense",
  "开心": "Happy",
  "兴奋": "Excited",
  "平静": "Calm",
  "放松": "Relaxed",
  "低落": "Low",
  "悲伤": "Sad",
  "疲惫": "Tired",
  "复杂情绪": "Mixed emotions",
  "身体不适": "Physical discomfort",
};

const els = {
  refreshContextBtn: document.getElementById("bodyRefreshContextBtn"),
  contextState: document.getElementById("bodyContextState"),
  journalText: document.getElementById("bodyJournalText"),
  recentContext: document.getElementById("bodyRecentContext"),
  regionChips: document.getElementById("bodyRegionChips"),
  symptomChips: document.getElementById("bodySymptomChips"),
  severity: document.getElementById("bodySeverity"),
  severityLabel: document.getElementById("bodySeverityLabel"),
  duration: document.getElementById("bodyDuration"),
  freeText: document.getElementById("bodyFreeText"),
  addPairBtn: document.getElementById("bodyAddPairBtn"),
  clearPairsBtn: document.getElementById("bodyClearPairsBtn"),
  submitBtn: document.getElementById("bodySubmitBtn"),
  submitStatus: document.getElementById("bodySubmitStatus"),
  pairCount: document.getElementById("bodyPairCount"),
  selectedPairs: document.getElementById("bodySelectedPairs"),
  adviceState: document.getElementById("bodyAdviceState"),
  adviceEmpty: document.getElementById("bodyAdviceEmpty"),
  adviceContent: document.getElementById("bodyAdviceContent"),
};

function bodyLang() {
  try {
    return window.SharedI18N?.lang?.() || localStorage.getItem("emomirror.lang") || "zh";
  } catch (error) {
    return "zh";
  }
}

function bodyIsEnglish() {
  return bodyLang() === "en";
}

function bodyText(zh, en) {
  return bodyIsEnglish() ? en : zh;
}

function bodyT(key, fallback) {
  const value = window.SharedI18N?.t?.(key);
  return value && value !== key ? value : fallback;
}

function bodyFormat(key, fallback, values = {}) {
  return bodyT(key, fallback).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? "");
}

function bodyLabel(item) {
  if (!item) return "";
  return bodyIsEnglish() ? (BODY_LABEL_EN[item.id] || item.label || item.id) : (item.label || item.id);
}

function bodyEmotionLabel(label) {
  const text = String(label || "");
  if (!bodyIsEnglish()) return text;
  return BODY_EMOTION_LABEL_EN[text.trim()] || text;
}

const state = {
  selectedRegion: BODY_STRUCTURE[0],
  selectedSymptom: BODY_STRUCTURE[0].symptoms[0],
  pairs: [],
  contextRecords: [],
  loadingContext: false,
  submitting: false,
};

function normalizeCode(value) {
  return String(value || "").trim();
}

function readParticipantFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return normalizeCode(
    params.get("participant_code") ||
    params.get("participantCode") ||
    params.get("code") ||
    params.get("participant"),
  );
}

function readParticipantFromStorage() {
  for (const key of BODY_PARTICIPANT_STORAGE_KEYS) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      if (key === "emomirror.participant") {
        const parsed = JSON.parse(raw);
        const code = normalizeCode(parsed?.participant_code);
        if (code) return code;
      } else {
        const code = normalizeCode(raw);
        if (code) return code;
      }
    } catch (error) {}
  }
  return "";
}

function currentParticipantCode() {
  // Prefer logged-in user's username
  if (typeof Auth !== "undefined" && Auth.isLoggedIn()) {
    var user = Auth.getUser();
    if (user && user.username) return user.username;
  }
  return readParticipantFromUrl() || readParticipantFromStorage() || "local";
}

function rememberParticipantCode(code) {
  const clean = normalizeCode(code);
  if (!clean) return;
  try {
    localStorage.setItem("emotype_participant_code", clean);
    localStorage.setItem("participant_code", clean);
    localStorage.setItem("participantCode", clean);
  } catch (error) {}
}

async function apiJson(url, options = {}) {
  // Use Auth.apiJson when available (adds JWT Bearer token)
  if (typeof Auth !== "undefined" && Auth.apiJson) {
    return Auth.apiJson(url, options);
  }
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(options.headers || {}),
    },
  });
  let data = null;
  try {
    data = await response.json();
  } catch (error) {}
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || response.statusText || "request failed");
  }
  return data;
}

function setContextState(text) {
  els.contextState.textContent = text;
}

function setAdviceState(text) {
  els.adviceState.textContent = text;
}

function setSubmitStatus(text) {
  els.submitStatus.textContent = text;
}

function chipButton(label, options = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `body-chip-v2${options.active ? " is-active" : ""}${options.positive ? " is-positive" : ""}`;
  btn.textContent = label;
  btn.addEventListener("click", options.onClick);
  return btn;
}

function renderRegionChips() {
  els.regionChips.textContent = "";
  BODY_STRUCTURE.forEach((region) => {
    els.regionChips.appendChild(chipButton(bodyLabel(region), {
      active: state.selectedRegion.id === region.id,
      onClick: () => {
        state.selectedRegion = region;
        state.selectedSymptom = region.symptoms[0];
        renderRegionChips();
        renderSymptomChips();
      },
    }));
  });
}

function renderSymptomChips() {
  els.symptomChips.textContent = "";
  state.selectedRegion.symptoms.forEach((symptom) => {
    els.symptomChips.appendChild(chipButton(bodyLabel(symptom), {
      active: state.selectedSymptom.id === symptom.id,
      positive: Boolean(symptom.positive),
      onClick: () => {
        state.selectedSymptom = symptom;
        renderSymptomChips();
      },
    }));
  });
}

function renderPairs() {
  const count = state.pairs.length;
  els.pairCount.textContent = bodyIsEnglish()
    ? `${count} ${count === 1 ? "pair" : "pairs"}`
    : `${count} ${bodyT("body.pairUnit", "组")}`;
  els.selectedPairs.textContent = "";
  if (!state.pairs.length) {
    els.selectedPairs.textContent = bodyT("body.noPairs", bodyText("暂无", "None yet"));
    return;
  }

  state.pairs.forEach((pair, index) => {
    const row = document.createElement("article");
    row.className = "body-pair-card-v2";
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${bodyLabel(pair.region)} -> ${bodyLabel(pair.symptom)}`;
    const meta = document.createElement("span");
    meta.textContent = `${bodyT("body.severity", bodyText("程度", "Severity"))} ${pair.severity} / 5 · ${pair.duration || bodyT("body.noDuration", bodyText("未填写持续时间", "No duration entered"))}`;
    body.append(title, meta);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = bodyT("body.delete", bodyText("删除", "Delete"));
    remove.addEventListener("click", () => {
      state.pairs.splice(index, 1);
      renderPairs();
    });
    row.append(body, remove);
    els.selectedPairs.appendChild(row);
  });
}

function addPair() {
  state.pairs.push({
    region: state.selectedRegion,
    symptom: state.selectedSymptom,
    severity: Number(els.severity.value || 3),
    duration: normalizeCode(els.duration.value),
  });
  renderPairs();
}

function clearPairs() {
  state.pairs = [];
  renderPairs();
}

function uniqueRegionsFromPairs() {
  return Array.from(
    new Map(state.pairs.map((pair) => [pair.region.id, { id: pair.region.id, label: pair.region.label }])).values(),
  );
}

function symptomsFromPairs() {
  return state.pairs.map((pair) => ({
    id: pair.symptom.id,
    region_id: pair.region.id,
    label: pair.symptom.label,
    severity: pair.severity,
    duration: pair.duration,
  }));
}

function contextText(record) {
  return record.raw_text || record.transcript_text || record.content || record.text || record.summary || "";
}

function contextLabel(record, index) {
  const label = record.final_label || record.primary_emotion || record.original_label || record.label || bodyT("body.recordFallback", bodyText("记录", "Record"));
  const preview = contextText(record).replace(/\s+/g, " ").slice(0, 26);
  return `${index + 1}. ${bodyEmotionLabel(label)}${preview ? ` · ${preview}` : ""}`;
}

async function ensureParticipantSession(code) {
  if (!code || code === "local") return;
  try {
    await apiJson("/participants/session", {
      method: "POST",
      body: JSON.stringify({
        participant_code: code,
        consent_version: "research-v1",
      }),
    });
  } catch (error) {}
}

function renderRecentContext() {
  els.recentContext.textContent = "";
  if (!state.contextRecords.length) {
    const empty = document.createElement("p");
    empty.className = "body-context-empty";
    empty.textContent = bodyT("body.noRecentContext", bodyText("没有读取到最近随手记。仍然可以只根据本次身体感受生成建议。", "No recent journal entries were loaded. You can still generate advice from this body sensation only."));
    els.recentContext.appendChild(empty);
    return;
  }

  state.contextRecords.slice(0, 6).forEach((record, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "body-context-item";
    btn.textContent = contextLabel(record, index);
    btn.addEventListener("click", () => {
      const text = contextText(record);
      if (!text) return;
      const prefix = els.journalText.value.trim() ? "\n\n" : "";
      els.journalText.value += `${prefix}${text}`;
      els.journalText.focus();
    });
    els.recentContext.appendChild(btn);
  });
}

async function loadRecentContext() {
  const code = currentParticipantCode();
  rememberParticipantCode(code);
  state.loadingContext = true;
  els.refreshContextBtn.disabled = true;
  setContextState(bodyT("body.loading", bodyText("读取中", "Loading")));
  try {
    await ensureParticipantSession(code);
    const data = await apiJson(`/participants/${encodeURIComponent(code)}/diaries`);
    state.contextRecords = data.diary_entries || data.diaries || data.entries || [];
    setContextState(bodyFormat("body.loadedRecords", bodyText("已读取 {count} 条", "Loaded {count} records"), { count: state.contextRecords.length }));
  } catch (error) {
    state.contextRecords = [];
    setContextState(bodyT("body.loadFailed", bodyText("读取失败", "Load failed")));
  } finally {
    state.loadingContext = false;
    els.refreshContextBtn.disabled = false;
    renderRecentContext();
  }
}

function renderAdvice(data) {
  const advice = data?.advice || {};
  const links = data?.possible_links || advice.possible_links || [];
  const safety = data?.safety || {};
  const context = data?.emotion_context || {};
  els.adviceEmpty.style.display = "none";
  els.adviceContent.textContent = "";
  document.querySelector(".body-advice-column")?.classList.add("is-visible");

  const summary = document.createElement("p");
  summary.className = "body-advice-summary-v2";
  summary.textContent = advice.summary || bodyT("body.adviceGenerated", bodyText("建议已生成。", "Advice generated."));
  els.adviceContent.append(summary);

  if (advice.state_reading) {
    const stateBox = document.createElement("p");
    stateBox.className = "body-state-reading";
    stateBox.textContent = advice.state_reading;
    els.adviceContent.appendChild(stateBox);
  }

  const meta = document.createElement("div");
  meta.className = "body-advice-meta-v2";
  meta.textContent = `${bodyT("body.emotionClue", bodyText("情绪线索", "Emotion clue"))}: ${bodyEmotionLabel(context.primary_label) || "-"} · ${bodyT("body.source", bodyText("来源", "Source"))}: ${advice.source || "-"}`;
  els.adviceContent.appendChild(meta);

  appendAdviceList(bodyT("body.bodyEmotionLinks", bodyText("身体-情绪线索", "Body-emotion links")), links.map((item) => `${item.label || item.type || bodyText("线索", "Clue")}: ${item.description || ""}`));
  appendAdviceList(bodyT("body.stepsToTry", bodyText("可尝试步骤", "Steps to try")), advice.steps || [], true);

  if (advice.reflection_prompt) {
    appendAdviceParagraph(bodyT("body.reflectionPrompt", bodyText("继续记录提示", "Reflection prompt")), advice.reflection_prompt);
  }

  if (safety.risk_level === "high" && Array.isArray(safety.red_flags) && safety.red_flags.length) {
    appendAdviceList(bodyT("body.riskWarning", bodyText("风险提示", "Risk warning")), safety.red_flags);
  }

  appendAdviceParagraph(bodyT("body.note", bodyText("说明", "Note")), bodyT("body.nonMedicalNote", bodyText("这些建议不构成医疗诊断；如果症状明显、持续或让你担心，请优先寻求专业帮助。", "These suggestions are not a medical diagnosis. If symptoms are strong, persistent, or worrying, seek professional help first.")));
}

function appendAdviceParagraph(label, text) {
  const section = document.createElement("section");
  section.className = "body-advice-section-v2";
  const heading = document.createElement("span");
  heading.textContent = label;
  const p = document.createElement("p");
  p.textContent = text || "-";
  section.append(heading, p);
  els.adviceContent.appendChild(section);
}

function appendAdviceList(label, items, ordered = false) {
  if (!Array.isArray(items) || !items.length) return;
  const section = document.createElement("section");
  section.className = "body-advice-section-v2";
  const heading = document.createElement("span");
  heading.textContent = label;
  const list = document.createElement(ordered ? "ol" : "ul");
  items.slice(0, 8).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = typeof item === "string" ? item : JSON.stringify(item);
    list.appendChild(li);
  });
  section.append(heading, list);
  els.adviceContent.appendChild(section);
}

async function submitAdvice() {
  if (state.submitting) return;
  const code = currentParticipantCode();
  rememberParticipantCode(code);
  if (!state.pairs.length) addPair();

  const payload = {
    participant_code: code,
    journal_text: els.journalText.value.trim(),
    selected_regions: uniqueRegionsFromPairs(),
    symptoms: symptomsFromPairs(),
    free_text: els.freeText.value.trim(),
    include_recent_diaries: true,
    recent_diary_limit: 5,
  };

  state.submitting = true;
  els.submitBtn.disabled = true;
  els.submitBtn.textContent = bodyT("body.generating", bodyText("生成中", "Generating"));
  setAdviceState(bodyT("body.generating", bodyText("生成中", "Generating")));
  setSubmitStatus(bodyT("body.generateWait", bodyText("正在生成建议，可能需要几秒。", "Generating advice. This may take a few seconds.")));
  try {
    const data = await apiJson("/body-sensation/advice", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderAdvice(data);
    setAdviceState(bodyT("body.generated", bodyText("已生成", "Generated")));
    setSubmitStatus(bodyFormat("body.generatedStatus", bodyText("建议已生成。来源：{source}", "Advice generated. Source: {source}"), { source: data?.advice?.source || "-" }));
  } catch (error) {
    setAdviceState(bodyT("body.generateFailed", bodyText("生成失败", "Failed")));
    setSubmitStatus(bodyFormat("body.requestFailed", bodyText("请求失败：{message}", "Request failed: {message}"), { message: error.message }));
  } finally {
    state.submitting = false;
    els.submitBtn.disabled = false;
    els.submitBtn.textContent = bodyT("body.generate", bodyText("生成身体感受建议", "Generate Body Advice"));
  }
}

function bindEvents() {
  els.refreshContextBtn.addEventListener("click", loadRecentContext);
  els.addPairBtn.addEventListener("click", addPair);
  els.clearPairsBtn.addEventListener("click", clearPairs);
  els.submitBtn.addEventListener("click", submitAdvice);
  els.severity.addEventListener("input", () => {
    els.severityLabel.textContent = `${els.severity.value} / 5`;
  });
}

function boot() {
  const code = readParticipantFromUrl() || readParticipantFromStorage() || "local";
  rememberParticipantCode(code);
  renderRegionChips();
  renderSymptomChips();
  renderPairs();
  renderRecentContext();
  bindEvents();
  loadRecentContext();
}

document.addEventListener("DOMContentLoaded", boot);
