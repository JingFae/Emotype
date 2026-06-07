const views = document.querySelectorAll(".view");
const viewButtons = document.querySelectorAll("[data-view]");
const journalText = document.querySelector("#journalText");
const typeStage = document.querySelector("#typeStage");
const analysisStatus = document.querySelector("#analysisStatus");
const intensityRange = document.querySelector("#intensityRange");
const homeIntensity = document.querySelector("#homeIntensity");
const primaryEmotion = document.querySelector("#primaryEmotion");
const reflectionText = document.querySelector("#reflectionText");
const confidenceMeter = document.querySelector("#confidenceMeter");
const emotionDot = document.querySelector("#emotionDot");
const emotionChips = document.querySelector("#emotionChips");
const customEmotionLabel = document.querySelector("#customEmotionLabel");
const applyCustomLabel = document.querySelector("#applyCustomLabel");
const vaPlane = document.querySelector("#vaPlane");
const vaHandle = document.querySelector("#vaHandle");
const vaReadout = document.querySelector("#vaReadout");
const promptRow = document.querySelector("#promptRow");
const saveEntry = document.querySelector("#saveEntry");
const entryList = document.querySelector("#entryList");
const entryCount = document.querySelector("#entryCount");
const latestEmotion = document.querySelector("#latestEmotion");
const latestConfidence = document.querySelector("#latestConfidence");
const homeMirrorWord = document.querySelector("#homeMirrorWord");
const homeMirrorCaption = document.querySelector("#homeMirrorCaption");
const clearEntries = document.querySelector("#clearEntries");
const voiceButton = document.querySelector("#voiceButton");
const typingMode = document.querySelector("#typingMode");
const voiceMode = document.querySelector("#voiceMode");
const entryStorageMode = document.querySelector("#entryStorageMode");

const palette = {
  plum: "#5E5094",
  periwinkle: "#A99EDF",
  mist: "#E2DCF5",
  blush: "#E4BEE8",
  orchid: "#BF68BE",
  mint: "#A6CFCD",
  blueMist: "#949DCA",
  mauve: "#BEAACF",
};

let entries = JSON.parse(localStorage.getItem("emomirror.entries") || "[]");
let selectedLabel = "";
let analyzeTimer = null;
let recognition = null;
let isListening = false;
let currentOverallMapping = null;
let currentCandidates = [];
let currentDesign = {};
let isDraggingVA = false;
let participant = JSON.parse(localStorage.getItem("emomirror.participant") || "null");
let currentAnalysisPayload = {};
let detectedOverallMapping = null;
let currentVAMapping = null;

function vaMapper() {
  return window.VAMapper;
}

function clampNumber(value, lower = -1, upper = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(lower, Math.min(upper, number));
}

const NEGATION_PREFIXES = ["不", "没", "沒", "没有", "沒有", "未", "无", "無", "并不", "並不", "不是", "别", "別"];

function isNegatedMatch(text, label, index) {
  const prefix = String(text || "").slice(Math.max(0, index - 4), index).toLowerCase();
  return NEGATION_PREFIXES.some((term) => prefix.endsWith(term.toLowerCase()));
}

function containsUnnegatedAny(text, terms) {
  const source = String(text || "");
  const lower = source.toLowerCase();
  return terms
    .slice()
    .sort((left, right) => right.length - left.length)
    .some((term) => {
      const termLower = term.toLowerCase();
      let cursor = 0;
      while (cursor < lower.length) {
        const index = lower.indexOf(termLower, cursor);
        if (index === -1) return false;
        if (!isNegatedMatch(source, term, index)) return true;
        cursor = index + termLower.length;
      }
      return false;
    });
}

function lexiconMatchesForText(text) {
  const source = String(text || "");
  const lower = source.toLowerCase();
  return vaMapper()
    .getEmotionLexicon()
    .slice()
    .sort((left, right) => String(right.label || "").length - String(left.label || "").length)
    .filter((item) => {
      const label = String(item.label || "");
      if (!label) return false;
      const labelLower = label.toLowerCase();
      let cursor = 0;
      while (cursor < lower.length) {
        const index = lower.indexOf(labelLower, cursor);
        if (index === -1) return false;
        if (Number(item.valence) <= 0 || !isNegatedMatch(source, label, index)) return true;
        cursor = index + labelLower.length;
      }
      return false;
    });
}

function formatSigned(value) {
  const number = clampNumber(value);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function quadrantPreset(label) {
  const labels = vaMapper().QUADRANT_LABELS || {};
  const presets = {
    [labels.neutral || "中性"]: { valence: 0, arousal: 0, quadrant: "neutral" },
    [labels.high_negative || "消极高能量"]: { valence: -0.62, arousal: 0.62, quadrant: "high_negative" },
    [labels.high_positive || "积极高能量"]: { valence: 0.62, arousal: 0.62, quadrant: "high_positive" },
    [labels.low_negative || "消极低能量"]: { valence: -0.62, arousal: -0.62, quadrant: "low_negative" },
    [labels.low_positive || "积极低能量"]: { valence: 0.62, arousal: -0.62, quadrant: "low_positive" },
  };
  return presets[label] || null;
}

function lexiconItemForLabel(label) {
  return vaMapper().getEmotionLexicon().find((item) => item.label === label) || null;
}

function candidateFromLabel(label, fallback = {}) {
  const lexiconItem = lexiconItemForLabel(label);
  const preset = quadrantPreset(label);
  const source = lexiconItem || preset || fallback;
  const valence = clampNumber(source.valence ?? fallback.valence ?? 0);
  const arousal = clampNumber(source.arousal ?? fallback.arousal ?? 0);
  const mapped = vaMapper().mapVA({
    valence,
    arousal,
    confidence: source.confidence ?? fallback.confidence ?? 0.72,
  });

  return {
    ...mapped,
    label,
    source: source.source || fallback.source || "candidate",
  };
}

function switchView(targetId) {
  views.forEach((view) => view.classList.toggle("is-active", view.id === targetId));
  viewButtons.forEach((button) => {
    const isActive = button.dataset.view === targetId;
    if (button.classList.contains("tab-button")) {
      button.classList.toggle("is-active", isActive);
    }
  });
  if (targetId === "dataView") refreshDataCharts();
}

function setStatus(text) {
  analysisStatus.textContent = text;
}

function participantCode() {
  return participant?.participant_code || "";
}

function saveParticipant(nextParticipant) {
  participant = nextParticipant;
  if (participant) {
    localStorage.setItem("emomirror.participant", JSON.stringify(participant));
  } else {
    localStorage.removeItem("emomirror.participant");
  }
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = "request failed";
    try {
      const data = await response.json();
      message = data.detail || data.error || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

function serverEntryToLocal(entry) {
  const confidence = Number(entry.va_mapping_json?.overall?.confidence ?? 0);
  return {
    id: entry.id,
    text: entry.raw_text || entry.transcript_text || "",
    label: entry.final_label || entry.original_label || "中性",
    valence: entry.final_valence,
    arousal: entry.final_arousal,
    color: entry.final_color,
    quadrant: entry.va_mapping_json?.overall?.quadrant,
    confidence: Math.round(confidence * 100),
    date: entry.created_at ? new Date(entry.created_at).toLocaleString() : "",
    synced: true,
  };
}

async function loadParticipantEntries() {
  if (!participantCode()) {
    renderHome();
    return;
  }
  try {
    const data = await apiJson(`/participants/${encodeURIComponent(participantCode())}/diaries`);
    entries = (data.diary_entries || []).map(serverEntryToLocal);
    saveEntries();
    renderHome();
  } catch (error) {
    renderHome();
  }
}

function logUsageEvent(eventType, metadata = {}) {
  if (!participantCode()) return;
  fetch("/usage-events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_code: participantCode(),
      event_type: eventType,
      metadata_json: metadata,
    }),
  }).catch(() => {});
}

function downloadBlob(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportParticipant(format = "json") {
  if (!participantCode()) {
    const localBundle = {
      participant: null,
      diary_entries: entries,
      usage_events: [],
      exported_from: "localStorage",
      exported_at: new Date().toISOString(),
    };
    downloadBlob(JSON.stringify(localBundle, null, 2), "emomirror-local-export.json", "application/json;charset=utf-8");
    return;
  }

  try {
    const url = `/participants/${encodeURIComponent(participantCode())}/export.${format}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("export failed");
    const content = format === "json"
      ? JSON.stringify(await response.json(), null, 2)
      : await response.text();
    downloadBlob(
      content,
      `emomirror-${participantCode()}.${format}`,
      format === "json" ? "application/json;charset=utf-8" : "text/csv;charset=utf-8",
    );
  } catch (error) {
    console.error("Export failed:", error.message);
  }
}

function getIntensity() {
  return Number(intensityRange.value) / 100;
}

function animationClass(name) {
  if (!name || getIntensity() < 0.25) return "";
  return `anim-${String(name).replace(/[^a-z0-9-]/gi, "").toLowerCase()}`;
}

function applyIntensity(style = {}) {
  const intensity = getIntensity();
  const next = { ...style };
  if (next.scale) {
    next.scale = 1 + (Number(next.scale) - 1) * intensity;
  }
  if (intensity < 0.35) {
    delete next.animation;
  }
  return next;
}

function hexToRgba(hex, alpha) {
  const clean = String(hex || "").replace("#", "");
  if (clean.length !== 6) return `rgba(148, 163, 184, ${alpha})`;
  const r = Number.parseInt(clean.slice(0, 2), 16);
  const g = Number.parseInt(clean.slice(2, 4), 16);
  const b = Number.parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function styleForMapping(mapping = {}) {
  const color = mapping.color || vaMapper().NEUTRAL_COLOR;
  const styles = {
    high_negative: { weight: 900, scale: 1.72, color, backgroundColor: color, animation: "shake-hard" },
    high_positive: { weight: 850, scale: 1.62, color, backgroundColor: color, animation: "pulse-scale" },
    low_negative: { weight: 420, scale: 1.38, color, backgroundColor: color, animation: "sad-droop" },
    low_positive: { weight: 720, scale: 1.42, color, backgroundColor: color, animation: "float-drift" },
    neutral: { weight: 560, scale: 1.16, color, backgroundColor: color, animation: "float-drift" },
  };
  return styles[mapping.quadrant] || styles.neutral;
}

const EMOTION_RENDER_RULES = [
  { terms: ["暴怒", "狂怒"], emoji: "😡", tone: "rage", animation: "shake-hard", scale: 1.26, backgroundAlpha: 0.16 },
  { terms: ["愤怒", "生气", "很生气", "恼火"], emoji: "😠", tone: "anger", animation: "shake-hard", scale: 1.18, backgroundAlpha: 0.15 },
  { terms: ["烦躁", "懊恼", "不耐烦", "不高兴"], emoji: "😤", tone: "irritation", animation: "shake-hard", scale: 1.12, backgroundAlpha: 0.13 },
  { terms: ["焦虑", "紧张", "坐立不安", "紧绷"], emoji: "😰", tone: "anxiety", animation: "shake-hard", scale: 1.14, backgroundAlpha: 0.14 },
  { terms: ["担心", "忧虑", "不安"], emoji: "😟", tone: "worry", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.11 },
  { terms: ["害怕"], emoji: "😨", tone: "fear", animation: "shake-hard", scale: 1.16, backgroundAlpha: 0.14 },
  { terms: ["憎恶", "厌恶"], emoji: "🤢", tone: "disgust", animation: "sad-droop", scale: 1.08, backgroundAlpha: 0.12 },
  { terms: ["目瞪口呆", "惊讶"], emoji: "😮", tone: "surprise", animation: "pulse-scale", scale: 1.14, backgroundAlpha: 0.11 },

  { terms: ["兴奋", "狂喜", "兴高采烈"], emoji: "🤩", tone: "ecstatic", animation: "pulse-scale", scale: 1.24, backgroundAlpha: 0.15 },
  { terms: ["激动", "激动人心", "活跃"], emoji: "⚡", tone: "activated", animation: "pulse-scale", scale: 1.18, backgroundAlpha: 0.13 },
  { terms: ["开心", "快乐", "欢快", "愉快"], emoji: "😊", tone: "joy", animation: "float-drift", scale: 1.1, backgroundAlpha: 0.11 },
  { terms: ["幸福", "满怀希望", "乐观"], emoji: "🌤️", tone: "hope", animation: "float-drift", scale: 1.1, backgroundAlpha: 0.1 },
  { terms: ["热情", "积极", "精力充沛"], emoji: "✨", tone: "spark", animation: "pulse-scale", scale: 1.16, backgroundAlpha: 0.13 },
  { terms: ["专注"], emoji: "🎯", tone: "focus", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["自豪", "自信感", "有成就感"], emoji: "🌟", tone: "pride", animation: "pulse-scale", scale: 1.12, backgroundAlpha: 0.11 },

  { terms: ["悲伤", "沮丧", "低落", "失望"], emoji: "😢", tone: "sadness", animation: "sad-droop", scale: 1.1, backgroundAlpha: 0.12 },
  { terms: ["忧郁", "抑郁", "绝望", "凄凉"], emoji: "🌧️", tone: "despair", animation: "sad-droop", scale: 1.16, backgroundAlpha: 0.14 },
  { terms: ["孤独", "疏离"], emoji: "🫥", tone: "lonely", animation: "sad-droop", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["疲惫", "耗尽", "精疲力竭"], emoji: "😮‍💨", tone: "exhausted", animation: "sad-droop", scale: 1.12, backgroundAlpha: 0.11 },
  { terms: ["厌倦", "无聊", "冷漠", "消极"], emoji: "☁️", tone: "flat", animation: "float-drift", scale: 1.06, backgroundAlpha: 0.09 },
  { terms: ["挫败"], emoji: "😞", tone: "defeated", animation: "sad-droop", scale: 1.08, backgroundAlpha: 0.12 },

  { terms: ["平静", "安宁", "安详"], emoji: "🌿", tone: "calm", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["放松", "松弛", "舒适", "安逸", "悠闲"], emoji: "🍃", tone: "relaxed", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["安全"], emoji: "🛟", tone: "safe", animation: "float-drift", scale: 1.06, backgroundAlpha: 0.09 },
  { terms: ["满足", "满意", "满意的"], emoji: "😌", tone: "content", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["感恩", "爱意"], emoji: "💛", tone: "warmth", animation: "float-drift", scale: 1.1, backgroundAlpha: 0.11 },
  { terms: ["平衡"], emoji: "⚖️", tone: "balance", animation: "float-drift", scale: 1.04, backgroundAlpha: 0.09 },
  { terms: ["自在", "无忧无虑", "惬意"], emoji: "🌱", tone: "ease", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["冷静"], emoji: "🫧", tone: "cool", animation: "float-drift", scale: 1.04, backgroundAlpha: 0.08 },

  { terms: ["回避", "否认式表达"], emoji: "🫧", tone: "avoidance", animation: "float-drift", scale: 1.06, backgroundAlpha: 0.08 },
  { terms: ["身体紧绷", "胸口", "胸口紧"], emoji: "🫀", tone: "body", animation: "pulse-scale", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["复杂情绪"], emoji: "🌀", tone: "complex", animation: "float-drift", scale: 1.08, backgroundAlpha: 0.1 },
  { terms: ["中性"], emoji: "😐", tone: "neutral", animation: "float-drift", scale: 1.0, backgroundAlpha: 0.07 },
];

const QUADRANT_RENDER_FALLBACK = {
  high_negative: { emoji: "😣", tone: "high-negative", animation: "shake-hard", scale: 1.1, backgroundAlpha: 0.12 },
  high_positive: { emoji: "✨", tone: "high-positive", animation: "pulse-scale", scale: 1.12, backgroundAlpha: 0.12 },
  low_negative: { emoji: "☁️", tone: "low-negative", animation: "sad-droop", scale: 1.08, backgroundAlpha: 0.1 },
  low_positive: { emoji: "🌿", tone: "low-positive", animation: "float-drift", scale: 1.06, backgroundAlpha: 0.09 },
  neutral: { emoji: "😐", tone: "neutral", animation: "float-drift", scale: 1.0, backgroundAlpha: 0.07 },
};

function emotionRenderSignal(mapping = {}) {
  if (mapping.emoji) {
    return {
      ...(QUADRANT_RENDER_FALLBACK[mapping.quadrant] || QUADRANT_RENDER_FALLBACK.neutral),
      emoji: mapping.emoji,
    };
  }

  const label = [
    mapping.implicit_label,
    mapping.label,
    mapping.explicit_label,
    mapping.nearest_label,
    ...(Array.isArray(mapping.evidence) ? mapping.evidence : []),
  ].filter(Boolean).join(" ");
  const hit = EMOTION_RENDER_RULES.find((rule) => rule.terms.some((term) => label.includes(term)));
  return hit || QUADRANT_RENDER_FALLBACK[mapping.quadrant] || QUADRANT_RENDER_FALLBACK.neutral;
}

function emojiForEmotion(mapping = {}) {
  return emotionRenderSignal(mapping).emoji;
}

function buildEmojiInsertions(text, vaMapping = null) {
  const sourceText = String(text || "");
  const mapping = vaMapping || currentVAMapping;
  const insertions = new Map();
  if (!sourceText.trim() || !mapping) return insertions;

  const segments = (mapping.segments || []).filter((segment) => String(segment.text || "").trim());
  let cursor = 0;
  let emojiCount = 0;
  for (const segment of segments) {
    if (emojiCount >= 4) break;
    if (Number(segment.confidence ?? 0.5) < 0.18) continue;
    const segmentText = String(segment.text || "").trim();
    const start = sourceText.indexOf(segmentText, cursor);
    if (start === -1) continue;
    let end = start + segmentText.length - 1;
    while (end + 1 < sourceText.length && /[。！？!?，,；;]/.test(sourceText[end + 1])) {
      end += 1;
    }
    cursor = end + 1;
    if (!insertions.has(end)) {
      insertions.set(end, { emoji: emojiForEmotion(segment), mapping: segment });
      emojiCount += 1;
    }
  }

  if (!insertions.size && mapping.overall && sourceText.trim()) {
    const end = Math.max(0, sourceText.search(/\s*$/) - 1);
    insertions.set(end, { emoji: emojiForEmotion(mapping.overall), mapping: mapping.overall });
  }

  return insertions;
}

function createEmojiGlyph(emoji, mapping = {}) {
  const span = document.createElement("span");
  const signal = emotionRenderSignal(mapping);
  const baseStyle = styleForMapping(mapping);
  const style = applyIntensity({
    ...baseStyle,
    animation: signal.animation || baseStyle.animation,
    scale: signal.scale || 1.08,
  });
  const scale = Number.isFinite(Number(style.scale)) ? Math.max(0.9, Math.min(1.7, Number(style.scale))) : 1;
  span.className = `glyph emoji emoji-${signal.tone || "neutral"} ${animationClass(style.animation)}`;
  span.textContent = emoji;
  span.style.setProperty("--scale", scale);
  span.style.setProperty("--glyph-weight", 620);
  span.style.setProperty("--glyph-color", style.color || "var(--ink)");
  if (style.backgroundColor) {
    span.style.backgroundColor = hexToRgba(style.backgroundColor, signal.backgroundAlpha ?? 0.1);
  }
  return span;
}

function addStyleRange(design, start, length, style, onlyIfEmpty = false) {
  for (let offset = 0; offset < length; offset += 1) {
    const key = String(start + offset);
    if (onlyIfEmpty && design[key]) continue;
    design[key] = { ...(design[key] || {}), ...style };
  }
}

function renderTypography(text, design = {}, vaMapping = null) {
  typeStage.textContent = "";
  const fragment = document.createDocumentFragment();
  const emojiInsertions = buildEmojiInsertions(text, vaMapping);

  [...text || "Start writing to see the mirror."].forEach((char, index) => {
    const span = document.createElement("span");
    const style = applyIntensity(design[String(index)] || {});
    const scale = Number.isFinite(Number(style.scale)) ? Math.max(0.85, Math.min(2.2, Number(style.scale))) : 1;
    span.className = `glyph ${char === " " ? "space" : ""} ${animationClass(style.animation)}`;
    span.textContent = char === " " ? "\u00a0" : char;
    span.style.setProperty("--scale", scale);
    span.style.setProperty("--glyph-weight", style.weight || 560);
    span.style.setProperty("--glyph-color", style.color || "var(--ink)");
    if (style.backgroundColor) {
      span.style.backgroundColor = hexToRgba(style.backgroundColor, 0.14);
      span.style.borderRadius = "0.28em";
    }
    fragment.appendChild(span);

    const emojiInsertion = emojiInsertions.get(index);
    if (emojiInsertion) {
      fragment.appendChild(createEmojiGlyph(emojiInsertion.emoji, emojiInsertion.mapping));
    }
  });

  typeStage.appendChild(fragment);
}

function averageMatches(matches) {
  const weight = 1 / matches.length;
  return {
    valence: matches.reduce((sum, item) => sum + item.valence * weight, 0),
    arousal: matches.reduce((sum, item) => sum + item.arousal * weight, 0),
    confidence: Math.min(0.92, 0.44 + 0.12 * matches.length),
  };
}

function inferSegmentVA(segmentText) {
  const lower = segmentText.toLowerCase();
  const negatedMoodRules = [
    { terms: ["很不开心", "非常不开心"], valence: -0.54, arousal: -0.2, confidence: 0.78, explicit_label: "不高兴", implicit_label: "低落", evidence: ["否定情绪词：不开心"] },
    { terms: ["不开心"], valence: -0.46, arousal: -0.16, confidence: 0.72, explicit_label: "不高兴", implicit_label: "低落", evidence: ["否定情绪词：不开心"] },
    { terms: ["不高兴", "不满意", "不喜欢"], valence: -0.4, arousal: 0.18, confidence: 0.68, explicit_label: "不高兴", implicit_label: "不满", evidence: ["否定评价"] },
    { terms: ["不舒服"], valence: -0.4, arousal: 0.22, confidence: 0.66, explicit_label: "不安", implicit_label: "身体不适", evidence: ["否定身体感受"] },
    { terms: ["不安全"], valence: -0.42, arousal: 0.48, confidence: 0.68, explicit_label: "不安", implicit_label: "警觉", evidence: ["否定安全感"] },
  ];
  const negatedHit = negatedMoodRules.find((rule) => rule.terms.some((term) => lower.includes(term.toLowerCase())));
  if (negatedHit) return negatedHit;

  const implicitHints = [
    { terms: ["不知道该怎么办", "不知道該怎麼辦", "怎么办", "怎麼辦", "纠结", "糾結", "要不要", "犹豫", "猶豫"], valence: -0.36, arousal: 0.48, confidence: 0.66, explicit_label: "不安", implicit_label: "纠结", evidence: ["决策不确定"] },
    { terms: ["压力", "壓力", "学习压力", "學習壓力", "压力很大", "壓力很大", "撑不住", "撐不住", "崩溃", "崩潰"], valence: -0.62, arousal: 0.72, confidence: 0.76, explicit_label: "紧绷", implicit_label: "压力过载", evidence: ["压力过载"] },
    { terms: ["胸口", "心慌", "睡不着", "睡不著", "紧", "緊"], valence: -0.45, arousal: 0.65, confidence: 0.78, explicit_label: "不安", implicit_label: "焦虑", evidence: ["身体紧绷"] },
  ];
  const implicitHit = implicitHints.find((hint) => hint.terms.some((term) => lower.includes(term.toLowerCase())));
  if (implicitHit) return implicitHit;

  const lexiconMatches = lexiconMatchesForText(segmentText);

  if (lexiconMatches.length) return averageMatches(lexiconMatches);

  const positiveHints = [
    { terms: ["开心", "開心", "高兴", "高興", "期待", "兴奋", "興奮"], valence: 0.62, arousal: 0.52, confidence: 0.62, explicit_label: "开心", implicit_label: "开心", evidence: ["积极高唤醒线索"] },
    { terms: ["安心", "放松", "放鬆", "舒服", "平静", "平靜", "安全"], valence: 0.48, arousal: -0.48, confidence: 0.62, explicit_label: "平静", implicit_label: "放松", evidence: ["积极低唤醒线索"] },
  ];
  const positiveHit = positiveHints.find((hint) => containsUnnegatedAny(segmentText, hint.terms));
  if (positiveHit) return positiveHit;

  const englishHints = [
    { terms: ["angry", "mad", "hate", "anxious", "worry", "afraid", "tense", "tight"], valence: -0.5, arousal: 0.6 },
    { terms: ["happy", "excited", "joy", "proud", "hopeful", "active", "amazing"], valence: 0.55, arousal: 0.55 },
    { terms: ["sad", "lonely", "tired", "empty", "depressed", "bored", "low"], valence: -0.55, arousal: -0.55 },
    { terms: ["calm", "safe", "relaxed", "peaceful", "comfortable", "love"], valence: 0.55, arousal: -0.55 },
  ];

  const hit = englishHints.find((hint) => hint.terms.some((term) => lower.includes(term)));
  if (hit) {
    return { valence: hit.valence, arousal: hit.arousal, confidence: 0.56 };
  }

  return { valence: 0, arousal: 0, confidence: segmentText.trim() ? 0.2 : 0 };
}

function localVAMapping(text) {
  const segmentInputs = vaMapper()
    .splitTextSegments(text)
    .map((segment) => ({
      text: segment,
      ...inferSegmentVA(segment),
    }));

  return vaMapper().mapSegments(segmentInputs);
}

function reflectionFor(mapping) {
  return "";
}

function localEmotion(text, existingMapping = null) {
  const vaMapping = existingMapping || localVAMapping(text);
  const overall = vaMapping.overall || vaMapper().mapVA({ valence: 0, arousal: 0, confidence: 0 });

  return {
    primary: overall.label,
    key: overall.quadrant,
    secondary: overall.nearest_label ? [overall.nearest_label] : [],
    confidence: text.trim() ? overall.confidence : 0.12,
    color: overall.color,
    vad: { valence: overall.valence, arousal: overall.arousal, dominance: 0 },
    reflection: reflectionFor(overall),
    prompts: [],
    va_mapping: vaMapping,
  };
}

function localDesign(text, existingMapping = null) {
  const design = {};
  const vaMapping = existingMapping || localVAMapping(text);
  const overallStyle = styleForMapping(vaMapping.overall);
  let cursor = 0;

  for (const segment of vaMapping.segments || []) {
    const start = text.indexOf(segment.text, cursor);
    if (start === -1) continue;
    cursor = start + segment.text.length;
    const segmentStyle = {
      ...styleForMapping(segment),
      scale: 1.06,
      weight: 580,
    };
    addStyleRange(design, start, segment.text.length, segmentStyle, true);
  }

  const lexicon = vaMapper().getEmotionLexicon().slice().sort((a, b) => b.label.length - a.label.length);
  let styledTerms = 0;
  for (const item of lexicon) {
    const label = String(item.label || "");
    let index = text.indexOf(label);
    while (index !== -1 && Number(item.valence) > 0 && isNegatedMatch(text, label, index)) {
      index = text.indexOf(label, index + label.length);
    }
    if (index === -1 || styledTerms >= 4) continue;
    addStyleRange(design, index, label.length, styleForMapping(vaMapper().mapVA(item)));
    styledTerms += 1;
  }

  if (!styledTerms) {
    const match = text.match(/[A-Za-z']{5,}|[\u4e00-\u9fff]{2,4}/);
    if (match) {
      addStyleRange(design, match.index || 0, match[0].length, overallStyle);
    }
  }

  return design;
}

function normalizeDesignColors(design = {}, mapping = {}) {
  const style = styleForMapping(mapping);
  return Object.fromEntries(
    Object.entries(design).map(([key, value]) => [
      key,
      {
        ...value,
        color: value.color || style.color,
        backgroundColor: value.backgroundColor || style.color,
      },
    ]),
  );
}

function recolorDesign(design = {}, mapping = {}) {
  const style = styleForMapping(mapping);
  const baseDesign = Object.keys(design || {}).length
    ? design
    : localDesign(journalText.value, { segments: [], overall: mapping });

  return Object.fromEntries(
    Object.entries(baseDesign).map(([key, value]) => [
      key,
      {
        ...value,
        color: style.color,
        backgroundColor: style.color,
      },
    ]),
  );
}

function nearestLexiconCandidates(mapping = {}, limit = 8) {
  const valence = clampNumber(mapping.valence ?? 0);
  const arousal = clampNumber(mapping.arousal ?? 0);
  return vaMapper()
    .getEmotionLexicon()
    .map((item) => ({
      ...item,
      distance: Math.sqrt((valence - item.valence) ** 2 + (arousal - item.arousal) ** 2),
      source: "nearby",
    }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, limit)
    .map((item) => candidateFromLabel(item.label, item));
}

function buildEmotionCandidates(payload = {}, overall = {}, vaMapping = {}) {
  const candidates = [];
  const seen = new Set();

  const addCandidate = (candidateLike, fallback = {}) => {
    const label = typeof candidateLike === "string" ? candidateLike : candidateLike?.label;
    if (!label || seen.has(label)) return;
    seen.add(label);
    candidates.push(candidateFromLabel(label, { ...overall, ...fallback, ...(candidateLike || {}) }));
  };

  addCandidate(overall.label, { ...overall, source: "detected" });
  addCandidate(overall.nearest_label, { ...overall, source: "nearest" });
  (overall.candidates || []).forEach((candidate) => addCandidate(candidate, { source: "backend_nearby" }));
  (vaMapping.candidates || []).forEach((candidate) => addCandidate(candidate, { source: "backend_nearby" }));

  const segmentSources = [
    ...(vaMapping.segments || []),
    ...(payload.text_emotion?.segments || []),
  ];

  segmentSources.forEach((segment) => {
    ["implicit_label", "explicit_label", "label", "nearest_label"].forEach((key) => {
      addCandidate(segment[key], { ...segment, source: key });
    });
  });

  nearestLexiconCandidates(overall, 8).forEach((candidate) => addCandidate(candidate));

  return candidates.slice(0, 12);
}

function updateVAControl(mapping = {}) {
  const valence = clampNumber(mapping.valence ?? 0);
  const arousal = clampNumber(mapping.arousal ?? 0);
  const color = mapping.color || vaMapper().getEmotionColor(valence, arousal);
  const x = ((valence + 1) / 2) * 100;
  const y = ((1 - arousal) / 2) * 100;

  vaHandle.style.left = `${x}%`;
  vaHandle.style.top = `${y}%`;
  vaHandle.style.background = color;
  vaPlane.style.setProperty("--active-color", color);
  vaReadout.textContent = `V ${formatSigned(valence)} · A ${formatSigned(arousal)}`;
  vaPlane.setAttribute("aria-valuetext", `Valence ${formatSigned(valence)}, arousal ${formatSigned(arousal)}`);
}

function applyManualMapping(mapping = {}, options = {}) {
  const mapped = vaMapper().mapVA({
    valence: mapping.valence,
    arousal: mapping.arousal,
    confidence: mapping.source_confidence ?? mapping.confidence ?? 0.8,
  });
  const next = {
    ...mapped,
    ...mapping,
    valence: mapped.valence,
    arousal: mapped.arousal,
    color: mapped.color,
    quadrant: mapped.quadrant,
    quadrant_label: mapped.quadrant_label,
    label: mapping.label || mapped.label,
  };

  currentOverallMapping = next;
  selectedLabel = next.label;
  primaryEmotion.textContent = selectedLabel;
  reflectionText.textContent = reflectionFor(next);
  confidenceMeter.style.width = `${Math.round((next.confidence || 0) * 100)}%`;
  emotionDot.style.background = next.color || palette.mauve;
  updateVAControl(next);

  if (options.refreshCandidates) {
    currentCandidates = buildEmotionCandidates({}, next, { segments: [] });
  } else if (options.addToCandidates && !currentCandidates.some((candidate) => candidate.label === next.label)) {
    currentCandidates = [{ ...next, source: "custom" }, ...currentCandidates].slice(0, 12);
  }
  if (options.syncInput !== false) {
    customEmotionLabel.value = options.custom ? next.label : "";
  }

  currentVAMapping = { segments: [], overall: next };
  renderTypography(journalText.value, recolorDesign(currentDesign, next), currentVAMapping);
  renderChips(selectedLabel);
}

function normalizeAnalysisPayload(payload) {
  const text = journalText.value;
  const fallbackMapping = localVAMapping(text);
  const vaMapping = payload.va_mapping || payload.emotion?.va_mapping || fallbackMapping;
  const overall = vaMapping.overall || fallbackMapping.overall;
  const fallbackEmotion = localEmotion(text, vaMapping);
  const emotion = {
    ...fallbackEmotion,
    ...(payload.emotion || {}),
    primary: overall.label || payload.emotion?.primary || fallbackEmotion.primary,
    key: overall.quadrant || payload.emotion?.key || fallbackEmotion.key,
    confidence: overall.confidence ?? payload.emotion?.confidence ?? fallbackEmotion.confidence,
    color: overall.color || payload.emotion?.color || fallbackEmotion.color,
    va_mapping: vaMapping,
  };

  return { emotion, vaMapping, overall };
}

function applyAnalysis(payload) {
  const { emotion, vaMapping, overall } = normalizeAnalysisPayload(payload);
  currentAnalysisPayload = payload;
  detectedOverallMapping = overall;
  currentOverallMapping = overall;
  currentVAMapping = vaMapping;
  currentCandidates = buildEmotionCandidates(payload, overall, vaMapping);
  selectedLabel = emotion.primary;
  primaryEmotion.textContent = selectedLabel;
  reflectionText.textContent = emotion.reflection;
  confidenceMeter.style.width = `${Math.round((emotion.confidence || 0) * 100)}%`;
  emotionDot.style.background = emotion.color || palette.mauve;
  if (document.activeElement !== customEmotionLabel) {
    customEmotionLabel.value = "";
  }
  updateVAControl(overall);

  const hasRemoteDesign = payload.llm_design && Object.keys(payload.llm_design).length > 0;
  const design = hasRemoteDesign
    ? normalizeDesignColors(payload.llm_design, overall)
    : localDesign(journalText.value, vaMapping);
  currentDesign = design;
  renderTypography(journalText.value, design, vaMapping);
  renderChips(selectedLabel);
  renderPrompts(emotion.prompts || []);
}

function renderChips(activeLabel) {
  emotionChips.textContent = "";
  const candidates = currentCandidates.length
    ? currentCandidates
    : nearestLexiconCandidates(currentOverallMapping || { valence: 0, arousal: 0 }, 8);

  candidates.forEach((candidate) => {
    const button = document.createElement("button");
    button.className = `emotion-chip ${candidate.label === activeLabel ? "is-active" : ""}`;
    button.type = "button";
    button.textContent = candidate.label;
    button.style.setProperty("--chip-color", candidate.color || vaMapper().NEUTRAL_COLOR);
    button.title = `V ${formatSigned(candidate.valence)} · A ${formatSigned(candidate.arousal)}`;
    button.addEventListener("click", () => {
      applyManualMapping(candidate);
      logUsageEvent("label_candidate_selected", {
        label: candidate.label,
        valence: candidate.valence,
        arousal: candidate.arousal,
        distance: candidate.distance,
      });
      setStatus("Label adjusted");
    });
    emotionChips.appendChild(button);
  });
}

function renderPrompts(prompts) {
  if (!promptRow) return;
  promptRow.textContent = "";
  prompts.slice(0, 3).forEach((prompt) => {
    const button = document.createElement("button");
    button.className = "prompt-chip";
    button.type = "button";
    button.textContent = prompt;
    button.addEventListener("click", () => {
      const prefix = journalText.value.trim() ? "\n\n" : "";
      journalText.value += `${prefix}${prompt} `;
      journalText.focus();
      scheduleAnalysis();
    });
    promptRow.appendChild(button);
  });
}

async function analyzeText() {
  const text = journalText.value;
  if (!text.trim()) {
    applyAnalysis({ emotion: localEmotion(text), va_mapping: localVAMapping(text), llm_design: {} });
    setStatus("Ready");
    return;
  }

  const localMapping = localVAMapping(text);
  setStatus("Mirroring");
  applyAnalysis({
    emotion: localEmotion(text, localMapping),
    va_mapping: localMapping,
    llm_design: localDesign(text, localMapping),
  });

  try {
    const response = await fetch("/analyze-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, intensity: getIntensity() }),
    });
    if (!response.ok) throw new Error("analysis failed");
    const payload = await response.json();
    applyAnalysis(payload);
    setStatus("Live");
  } catch (error) {
    setStatus("Local mirror");
  }
}

function scheduleAnalysis() {
  clearTimeout(analyzeTimer);
  const mapping = localVAMapping(journalText.value);
  currentVAMapping = mapping;
  renderTypography(journalText.value, localDesign(journalText.value, mapping), mapping);
  analyzeTimer = setTimeout(analyzeText, 420);
}

function saveEntries() {
  localStorage.setItem("emomirror.entries", JSON.stringify(entries));
}

function renderHome() {
  if (entryCount)      entryCount.textContent      = String(entries.length);
  if (homeIntensity)   homeIntensity.textContent   = `${intensityRange.value}%`;
  if (entryStorageMode) entryStorageMode.textContent = participantCode() ? `synced as ${participantCode()}` : (currentLang === "zh" ? "仅本地" : "local only");

  if (entries.length) {
    const latest = entries[0];
    latestEmotion.textContent = latest.label;
    latestConfidence.textContent = `${latest.confidence}% confidence`;
    if (homeMirrorWord)    homeMirrorWord.textContent    = latest.label.split("/")[0].trim().toLowerCase();
    if (homeMirrorCaption) homeMirrorCaption.textContent = latest.date;
  } else {
    latestEmotion.textContent = currentLang === "zh" ? "中性" : "Neutral";
    latestConfidence.textContent = currentLang === "zh" ? "等待输入" : "waiting for text";
    if (homeMirrorWord)    homeMirrorWord.textContent    = "steady";
    if (homeMirrorCaption) homeMirrorCaption.textContent = "No entry yet today";
  }

  entryList.textContent = "";
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.style.cssText = "color:var(--muted-light);font-size:14px;padding:20px 0;";
    empty.textContent = currentLang === "zh" ? "还没有记录，去写第一篇日记吧 ✏️" : "No entries yet. Start journaling ✏️";
    entryList.appendChild(empty);
    return;
  }

  // Show ALL entries, newest first
  entries.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "entry-card";
    const dot = document.createElement("span");
    dot.style.cssText = `display:inline-block;width:10px;height:10px;border-radius:50%;background:${entry.color || "var(--amber)"};margin-right:7px;flex-shrink:0;margin-top:3px;`;
    const title = document.createElement("strong");
    title.style.display = "flex";
    title.style.alignItems = "flex-start";
    title.append(dot, entry.label || "中性");
    const copy = document.createElement("p");
    copy.textContent = entry.text || "";
    const date = document.createElement("small");
    date.textContent = entry.date || "";
    date.style.color = "var(--muted-light)";
    card.append(title, copy, date);
    entryList.appendChild(card);
  });
}

async function saveCurrentEntry() {
  const text = journalText.value.trim();
  if (!text) {
    setStatus("Nothing to save");
    return;
  }
  const confidence = Math.round(Number(confidenceMeter.style.width.replace("%", "")) || 0);
  const mapping = currentOverallMapping || vaMapper().mapVA({ valence: 0, arousal: 0, confidence: 0 });
  const original = detectedOverallMapping || mapping;
  const localEntry = {
    text,
    label: selectedLabel || primaryEmotion.textContent,
    valence: mapping.valence,
    arousal: mapping.arousal,
    color: mapping.color,
    quadrant: mapping.quadrant,
    confidence,
    date: new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date()),
    synced: false,
  };

  const _saveCode = participantCode() || "local";
  try {
    const data = await apiJson("/diaries", {
      method: "POST",
      body: JSON.stringify({
        participant_code: _saveCode,
        raw_text: text,
        transcript_text: text,
        original_valence: original.valence,
        original_arousal: original.arousal,
        original_label: original.label,
        final_valence: mapping.valence,
        final_arousal: mapping.arousal,
        final_label: selectedLabel || mapping.label,
        final_color: mapping.color,
        candidates_json: currentCandidates,
        text_emotion_json: currentAnalysisPayload.text_emotion || {},
        va_mapping_json: {
          ...(currentAnalysisPayload.va_mapping || {}),
          final_override: {
            valence: mapping.valence,
            arousal: mapping.arousal,
            label: selectedLabel || mapping.label,
            color: mapping.color,
            quadrant: mapping.quadrant,
          },
        },
      }),
    });
    entries.unshift(serverEntryToLocal(data.diary_entry));
    entries = entries.slice(0, 24);
    saveEntries();
    renderHome();
    setStatus("Saved");
    return;
  } catch (error) {
    setStatus("Saved locally; sync failed");
    console.error("Save to server failed:", error.message);
  }

  entries.unshift(localEntry);
  entries = entries.slice(0, 12);
  saveEntries();
  renderHome();
  setStatus("Saved locally");
}

let mediaRecorder = null;
let mediaChunks = [];

async function _transcribeJournalWithServer(blob) {
  const fd = new FormData();
  fd.append("file", blob, "audio.webm");
  try {
    voiceButton.textContent = "识别中…";
    const res = await fetch("/api/transcribe", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const { text } = await res.json();
    if (text) {
      const spacer = journalText.value.trim() ? " " : "";
      journalText.value += `${spacer}${text.trim()}`;
      scheduleAnalysis();
    }
  } catch (err) {
    setStatus("识别失败，请重试");
  } finally {
    voiceButton.textContent = "开始语音";
    voiceMode.classList.remove("is-active");
    typingMode.classList.add("is-active");
    isListening = false;
  }
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceButton.textContent = "开始录音";
    voiceButton.title = "浏览器不支持实时语音识别，将录音后上传识别";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "zh-CN";

  recognition.onresult = (event) => {
    let finalText = "";
    let interimText = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const phrase = event.results[index][0].transcript;
      if (event.results[index].isFinal) finalText += phrase;
      else interimText += phrase;
    }
    if (finalText) {
      const spacer = journalText.value.trim() ? " " : "";
      journalText.value += `${spacer}${finalText.trim()}`;
      scheduleAnalysis();
    }
    setStatus(interimText ? "正在听写…" : "语音已捕获");
  };

  recognition.onend = () => {
    isListening = false;
    voiceButton.textContent = "开始语音";
    typingMode.classList.add("is-active");
    voiceMode.classList.remove("is-active");
  };

  recognition.onerror = (event) => {
    isListening = false;
    voiceButton.textContent = "开始语音";
    const msgs = {
      "not-allowed": "请在浏览器中允许麦克风权限，然后重试",
      "network": "语音识别需要网络连接（使用 Google 服务），请检查网络",
      "no-speech": "没有检测到语音，请靠近麦克风重试",
      "audio-capture": "麦克风不可用，请检查设备",
    };
    setStatus(msgs[event.error] || "语音识别出错，请重试");
  };
}

function toggleVoice() {
  if (isListening) {
    if (recognition) recognition.stop();
    if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
    return;
  }

  // Prefer Web Speech API
  if (recognition) {
    isListening = true;
    voiceButton.textContent = "停止语音";
    typingMode.classList.remove("is-active");
    voiceMode.classList.add("is-active");
    try {
      recognition.start();
    } catch (error) {
      isListening = false;
      voiceButton.textContent = "开始语音";
      setStatus("语音启动失败，请重试");
    }
    return;
  }

  // Fallback: MediaRecorder → server Whisper
  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    isListening = true;
    mediaChunks = [];
    voiceButton.textContent = "停止录音";
    typingMode.classList.remove("is-active");
    voiceMode.classList.add("is-active");
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => { if (e.data.size) mediaChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(mediaChunks, { type: "audio/webm" });
      _transcribeJournalWithServer(blob);
    };
    mediaRecorder.start();
  }).catch(() => {
    setStatus("麦克风权限被拒绝，请在浏览器设置中允许");
  });
}

function mappingFromPointer(event) {
  const rect = vaPlane.getBoundingClientRect();
  const x = clampNumber((event.clientX - rect.left) / rect.width, 0, 1);
  const y = clampNumber((event.clientY - rect.top) / rect.height, 0, 1);
  return vaMapper().mapVA({
    valence: x * 2 - 1,
    arousal: 1 - y * 2,
    confidence: currentOverallMapping?.source_confidence ?? currentOverallMapping?.confidence ?? 0.82,
  });
}

function applyVAPointer(event) {
  applyManualMapping(mappingFromPointer(event), { refreshCandidates: true });
  setStatus("Coordinate adjusted");
}

function nudgeVA(deltaValence, deltaArousal) {
  const base = currentOverallMapping || vaMapper().mapVA({ valence: 0, arousal: 0, confidence: 0.8 });
  applyManualMapping(vaMapper().mapVA({
    valence: clampNumber(base.valence + deltaValence),
    arousal: clampNumber(base.arousal + deltaArousal),
    confidence: base.source_confidence ?? base.confidence ?? 0.8,
  }), { refreshCandidates: true });
  setStatus("Coordinate adjusted");
}

async function connectParticipant(event) {
  event.preventDefault();
}

function bindEvents() {
  viewButtons.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  journalText.addEventListener("input", scheduleAnalysis);
  intensityRange.addEventListener("input", () => {
    homeIntensity.textContent = `${intensityRange.value}%`;
    if (currentOverallMapping) {
      renderTypography(journalText.value, recolorDesign(currentDesign, currentOverallMapping), currentVAMapping);
    } else {
      const localMapping = localVAMapping(journalText.value);
      renderTypography(journalText.value, localDesign(journalText.value, localMapping), localMapping);
    }
    scheduleAnalysis();
  });
  saveEntry.addEventListener("click", saveCurrentEntry);
  applyCustomLabel.addEventListener("click", () => {
    const label = customEmotionLabel.value.trim();
    if (!label) return;
    const base = currentOverallMapping || vaMapper().mapVA({ valence: 0, arousal: 0, confidence: 0.8 });
    applyManualMapping({ ...base, label }, { addToCandidates: true, custom: true });
    logUsageEvent("custom_label_applied", {
      label,
      valence: currentOverallMapping?.valence,
      arousal: currentOverallMapping?.arousal,
    });
    setStatus("Custom label applied");
  });
  customEmotionLabel.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyCustomLabel.click();
    }
  });
  vaPlane.addEventListener("pointerdown", (event) => {
    isDraggingVA = true;
    vaPlane.setPointerCapture(event.pointerId);
    applyVAPointer(event);
  });
  vaPlane.addEventListener("pointermove", (event) => {
    if (isDraggingVA) applyVAPointer(event);
  });
  vaPlane.addEventListener("pointerup", () => {
    isDraggingVA = false;
  });
  vaPlane.addEventListener("pointercancel", () => {
    isDraggingVA = false;
  });
  vaPlane.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 0.14 : 0.06;
    const moves = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, step],
      ArrowDown: [0, -step],
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    nudgeVA(move[0], move[1]);
  });
  if (clearEntries) clearEntries.addEventListener("click", () => clearAllRecords());
  const dataExportJson = document.getElementById("dataExportJson");
  const dataExportCsv = document.getElementById("dataExportCsv");
  if (dataExportJson) dataExportJson.addEventListener("click", () => exportParticipant("json"));
  if (dataExportCsv) dataExportCsv.addEventListener("click", () => exportParticipant("csv"));
  voiceButton.addEventListener("click", toggleVoice);
  voiceMode.addEventListener("click", toggleVoice);
  typingMode.addEventListener("click", () => {
    if (isListening && recognition) recognition.stop();
    typingMode.classList.add("is-active");
    voiceMode.classList.remove("is-active");
  });
}

async function boot() {
  await vaMapper().loadEmotionLexicon();
  if (participant) saveParticipant(participant);
  else saveParticipant(null);
  initI18n();
  startDateTicker();
  bindEvents();
  setupSpeechRecognition();
  initBodyTab();
  const initialView = String(window.location.hash || "").replace("#", "");
  if (initialView && document.getElementById(initialView)) switchView(initialView);
  renderChips("");
  renderPrompts(localEmotion("").prompts);
  renderTypography(journalText.value, localDesign(journalText.value), localVAMapping(journalText.value));
  if (participantCode()) await loadParticipantEntries();
  else renderHome();
  scheduleAnalysis();
}

/* ============================================================
   I18N — Bilingual zh / en
   ============================================================ */
const I18N = {
  zh: {
    "brand.tag": "情绪镜像日记",
    "nav.home": "首页", "nav.journal": "随手记", "nav.diaryBook": "日记本", "nav.review": "情绪复盘", "nav.records": "历史记录", "nav.body": "身体感受", "nav.data": "数据",
    "nav.essay": "情绪随笔", "nav.ecoEcho": "Emo 回响", "nav.historyReview": "历史回顾", "nav.profile": "个人信息", "nav.login": "登录",
    "topbar.local": "本地模式",
    "research.title": "研究模式", "research.code": "实验编号", "research.consent": "同意保存日记和操作日志用于研究分析",
    "research.connect": "进入记录", "research.exportJson": "导出 JSON", "research.exportCsv": "导出 CSV",
    "research.status": "未连接实验编号，本机临时保存。",
    "home.title": "感受你的情绪",
    "home.subtitle": "写下或说出今天发生的事，EmoBridge 会把你的情绪转化成流动的文字与色彩。",
    "home.cta": "开始今天的记录",
    "home.stat.entries": "记录条数", "home.stat.localOnly": "仅本地", "home.stat.latest": "最新情绪",
    "home.stat.waiting": "等待输入", "home.stat.intensity": "镜像强度", "home.stat.intensityHint": "可在日记页调整",
    "home.recent.eyebrow": "从新到旧", "home.recent.title": "情绪日记", "home.recent.clear": "清除本地记录",
    "journal.eyebrow": "表达性写作", "journal.title": "今天的记录", "journal.ready": "就绪",
    "journal.modeType": "文字输入", "journal.modeVoice": "语音转文字",
    "journal.placeholder": "写下发生了什么。可以具体、模糊、矛盾，或者不确定。",
    "journal.intensity": "镜像反馈强度", "journal.startVoice": "开始语音", "journal.save": "保存记录",
    "journal.mirror.eyebrow": "情绪动态字体", "journal.mirror.title": "实时镜像",
    "journal.detected": "识别结果", "journal.customLabel": "自定义标签",
    "journal.customPlaceholder": "输入更贴近的情绪词", "journal.apply": "应用",
    "journal.va": "V-A 坐标",
    "va.positive": "积极", "va.negative": "消极", "va.high": "高能量", "va.low": "低能量",
    "body.eyebrow": "情绪与身体", "body.title": "身体感受",
    "body.subtitle": "选择身体不适部位和感受，结合最近日记，生成温和缓解提示。",
    "body.diagram": "身体部位图", "body.svgPlaceholder": "人体图即将上线", "body.svgHint": "通过右侧选择部位与感受",
    "body.selected": "已选组合", "body.noPairs": "暂无",
    "body.journalRef": "当前日记参考", "body.journalRefPlaceholder": "填写当前的日记内容（可选）",
    "body.selectRegion": "选择部位", "body.selectSymptom": "选择感受",
    "body.details": "详细信息", "body.severity": "程度", "body.duration": "持续时间",
    "body.addPair": "加入组合", "body.clearPairs": "清空",
    "body.describe": "补充描述", "body.describePlaceholder": "今天喝水较少，坐着学习了很久…",
    "body.generate": "生成身体感受建议", "body.statusHint": "系统会综合身体感受和最近日记。",
    "data.eyebrow": "数据与洞察", "data.title": "情绪数据",
    "data.emotionFreq": "情绪频率分布", "data.refresh": "刷新",
    "data.noData": "暂无记录，先去写日记吧 ✏️",
    "data.vaHistory": "V-A 坐标历史",
    "data.export": "导出数据", "data.exportHint": "包含所有本地保存的日记记录。",
    "data.summary": "记录摘要", "data.danger": "危险操作",
  },
  en: {
    "brand.tag": "Emotion Mirror Journal",
    "nav.home": "Home", "nav.journal": "Journal", "nav.diaryBook": "Diary", "nav.review": "Review", "nav.records": "Records", "nav.body": "Body Sense", "nav.data": "Data",
    "nav.essay": "Journal", "nav.ecoEcho": "Emo Echo", "nav.historyReview": "History", "nav.profile": "Profile", "nav.login": "Login",
    "topbar.local": "Local mode",
    "research.title": "Research mode", "research.code": "Participant ID", "research.consent": "I agree to save journals and logs for research",
    "research.connect": "Connect", "research.exportJson": "Export JSON", "research.exportCsv": "Export CSV",
    "research.status": "No participant ID. Saving locally.",
    "home.title": "Feel your emotion",
    "home.subtitle": "Write or speak. EmoBridge turns subtle emotional signals into living type.",
    "home.cta": "Start today's entry",
    "home.stat.entries": "Entries", "home.stat.localOnly": "local only", "home.stat.latest": "Latest label",
    "home.stat.waiting": "waiting for text", "home.stat.intensity": "Mirror intensity", "home.stat.intensityHint": "adjustable in journal",
    "home.recent.eyebrow": "Newest first", "home.recent.title": "Emotion Journal", "home.recent.clear": "Clear local entries",
    "journal.eyebrow": "Expressive writing", "journal.title": "Today's entry", "journal.ready": "Ready",
    "journal.modeType": "Type", "journal.modeVoice": "Voice to text",
    "journal.placeholder": "Write what happened. Be specific, vague, contradictory, or unsure.",
    "journal.intensity": "Feedback intensity", "journal.startVoice": "Start voice", "journal.save": "Save entry",
    "journal.mirror.eyebrow": "Kinetic affective type", "journal.mirror.title": "Live mirror",
    "journal.detected": "Detected", "journal.customLabel": "Custom label",
    "journal.customPlaceholder": "Type a closer emotion word", "journal.apply": "Apply",
    "journal.va": "V-A Coordinate",
    "va.positive": "Positive", "va.negative": "Negative", "va.high": "High energy", "va.low": "Low energy",
    "body.eyebrow": "Emotion & Body", "body.title": "Body Sensation",
    "body.subtitle": "Select body regions and symptoms. The system combines body cues with recent journals.",
    "body.diagram": "Body diagram", "body.svgPlaceholder": "Body diagram coming soon", "body.svgHint": "Select region & symptom on the right",
    "body.selected": "Selected pairs", "body.noPairs": "None yet",
    "body.journalRef": "Journal reference", "body.journalRefPlaceholder": "Paste today's journal (optional)",
    "body.selectRegion": "Select region", "body.selectSymptom": "Select symptom",
    "body.details": "Details", "body.severity": "Severity", "body.duration": "Duration",
    "body.addPair": "Add pair", "body.clearPairs": "Clear",
    "body.describe": "Describe more", "body.describePlaceholder": "Less water today, studied for hours…",
    "body.generate": "Generate advice", "body.statusHint": "System combines body cues and recent journals.",
    "data.eyebrow": "Insights", "data.title": "Emotion Data",
    "data.emotionFreq": "Emotion frequency", "data.refresh": "Refresh",
    "data.noData": "No entries yet. Start journaling ✏️",
    "data.vaHistory": "V-A history",
    "data.export": "Export data", "data.exportHint": "Includes all locally saved journal entries.",
    "data.summary": "Summary", "data.danger": "Danger zone",
  }
};

let currentLang = localStorage.getItem("emomirror.lang") || "zh";

function t(key) {
  return (I18N[currentLang] || I18N.zh)[key] || (I18N.zh)[key] || key;
}

function applyI18n() {
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    el.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.dataset.i18nPlaceholder;
    el.placeholder = t(key);
  });
}

function initI18n() {
  applyI18n();
}

/* ============================================================
   BODY TAB — region → specific symptoms (including positive)
   ============================================================ */
const BODY_STRUCTURE = [
  { id: "head", zh: "头部", en: "Head", symptoms: [
    { id: "headache",      zh: "头疼",        en: "Headache" },
    { id: "dizziness",     zh: "头晕",        en: "Dizziness" },
    { id: "brain_fog",     zh: "脑雾/注意力涣散", en: "Brain fog" },
    { id: "tinnitus",      zh: "耳鸣",        en: "Ear ringing" },
    { id: "clear_head",    zh: "头脑清晰",    en: "Clear mind",  positive: true },
    { id: "focused",       zh: "专注有力",    en: "Focused",     positive: true },
  ]},
  { id: "eyes", zh: "眼部", en: "Eyes", symptoms: [
    { id: "eye_strain",    zh: "眼疲劳",      en: "Eye strain" },
    { id: "dry_eyes",      zh: "眼干",        en: "Dry eyes" },
    { id: "blurred",       zh: "视物模糊",    en: "Blurred vision" },
    { id: "bright_eyes",   zh: "眼神明亮",    en: "Eyes feel bright", positive: true },
  ]},
  { id: "throat_mouth", zh: "口咽", en: "Throat", symptoms: [
    { id: "throat_tight",  zh: "喉咙紧/异物感", en: "Throat tightness" },
    { id: "dry_throat",    zh: "嗓子干",      en: "Dry throat" },
    { id: "jaw_tension",   zh: "下颌/牙关紧绷", en: "Jaw tension" },
    { id: "voice_clear",   zh: "声音通畅",    en: "Voice clear",  positive: true },
  ]},
  { id: "chest", zh: "胸口", en: "Chest", symptoms: [
    { id: "chest_tight",   zh: "胸闷/压迫感", en: "Chest tightness" },
    { id: "palpitation",   zh: "心跳过快/心慌", en: "Palpitation" },
    { id: "short_breath",  zh: "呼吸困难/气短", en: "Shortness of breath" },
    { id: "chest_open",    zh: "呼吸顺畅",    en: "Breathing easy", positive: true },
    { id: "heart_warm",    zh: "心里温暖",    en: "Heart feels warm", positive: true },
  ]},
  { id: "shoulder_neck", zh: "肩颈", en: "Shoulder/Neck", symptoms: [
    { id: "neck_stiff",    zh: "颈部僵硬",    en: "Neck stiffness" },
    { id: "shoulder_pain", zh: "肩膀酸痛",    en: "Shoulder ache" },
    { id: "muscle_tight",  zh: "肌肉紧绷",    en: "Muscle tension" },
    { id: "shoulder_relax",zh: "肩颈放松",    en: "Shoulders relaxed", positive: true },
  ]},
  { id: "stomach", zh: "胃部", en: "Stomach", symptoms: [
    { id: "stomach_pain",  zh: "胃痛/痉挛",   en: "Stomach cramp" },
    { id: "nausea",        zh: "恶心/反胃",   en: "Nausea" },
    { id: "appetite_loss", zh: "食欲下降",    en: "Appetite loss" },
    { id: "bloating",      zh: "腹胀/胀气",   en: "Bloating" },
    { id: "appetite_good", zh: "食欲好",      en: "Good appetite", positive: true },
    { id: "stomach_comfy", zh: "胃部舒适",    en: "Stomach comfortable", positive: true },
  ]},
  { id: "back", zh: "腰背", en: "Back", symptoms: [
    { id: "lower_back",    zh: "腰酸背痛",    en: "Lower back pain" },
    { id: "back_stiff",    zh: "背部僵硬",    en: "Back stiffness" },
    { id: "back_relax",    zh: "腰背舒展",    en: "Back feeling loose", positive: true },
  ]},
  { id: "hands", zh: "手部", en: "Hands", symptoms: [
    { id: "hand_shaking",  zh: "手抖",        en: "Shaking hands" },
    { id: "cold_hands",    zh: "手冰凉",      en: "Cold hands" },
    { id: "sweaty_hands",  zh: "手心出汗",    en: "Sweaty palms" },
    { id: "hands_warm",    zh: "双手温暖",    en: "Hands feel warm", positive: true },
  ]},
  { id: "legs", zh: "腿部", en: "Legs", symptoms: [
    { id: "leg_heavy",     zh: "腿沉/无力",   en: "Heavy/weak legs" },
    { id: "cold_feet",     zh: "脚冰凉",      en: "Cold feet" },
    { id: "restless_legs", zh: "腿部躁动不安", en: "Restless legs" },
    { id: "legs_light",    zh: "步伐轻盈",    en: "Legs feel light", positive: true },
  ]},
  { id: "whole_body", zh: "全身", en: "Whole body", symptoms: [
    { id: "fatigue",       zh: "疲惫/乏力",   en: "Fatigue" },
    { id: "insomnia",      zh: "失眠/睡眠差",  en: "Insomnia" },
    { id: "sweating",      zh: "出汗/冷汗",   en: "Sweating" },
    { id: "restless",      zh: "坐立不安",    en: "Restlessness" },
    { id: "energized",     zh: "精力充沛",    en: "Energized",        positive: true },
    { id: "calm_body",     zh: "全身放松",    en: "Body at ease",     positive: true },
    { id: "grounded",      zh: "踏实稳定",    en: "Feeling grounded", positive: true },
  ]},
];

let bodySelectedRegion = BODY_STRUCTURE[0];
let bodySelectedSymptom = BODY_STRUCTURE[0].symptoms[0];
let bodyPairs = [];

function bodyLabel(item) {
  return currentLang === "zh" ? item.zh : item.en;
}

// Update journal date display
function updateJournalDate() {
  const el = document.getElementById("journalDateDisplay");
  if (!el) return;
  const now = new Date();
  const days    = ["日", "一", "二", "三", "四", "五", "六"];
  const daysEn  = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const m = now.getMonth() + 1;
  const d = now.getDate();
  if (currentLang === "zh") {
    el.textContent = `${now.getFullYear()}.${m}.${d} 星期${days[now.getDay()]}`;
  } else {
    el.textContent = `${now.getFullYear()}.${m}.${d} ${daysEn[now.getDay()]}`;
  }
}

// Keep date ticking — update every minute
function startDateTicker() {
  updateJournalDate();
  const msToNextMinute = (60 - new Date().getSeconds()) * 1000;
  setTimeout(() => {
    updateJournalDate();
    setInterval(updateJournalDate, 60000);
  }, msToNextMinute);
}

function renderBodyChips() {
  const regionBox = document.getElementById("bodyRegionChips");
  const symptomBox = document.getElementById("bodySymptomChips");
  if (!regionBox || !symptomBox) return;

  // Region chips
  regionBox.innerHTML = "";
  BODY_STRUCTURE.forEach((region) => {
    const btn = document.createElement("button");
    btn.className = `body-chip${bodySelectedRegion.id === region.id ? " selected" : ""}`;
    btn.textContent = bodyLabel(region);
    btn.type = "button";
    btn.onclick = () => {
      bodySelectedRegion = region;
      bodySelectedSymptom = region.symptoms[0];
      renderBodyChips();
    };
    regionBox.appendChild(btn);
  });

  // Symptom chips — only for selected region, positive ones styled green
  symptomBox.innerHTML = "";
  const header = document.createElement("div");
  header.style.cssText = "font-size:12px;font-weight:700;color:var(--muted);margin-bottom:6px;width:100%;";
  header.textContent = bodyLabel(bodySelectedRegion) + " " + (currentLang === "zh" ? "相关感受：" : "symptoms:");
  symptomBox.appendChild(header);

  bodySelectedRegion.symptoms.forEach((sym) => {
    const btn = document.createElement("button");
    const isSelected = bodySelectedSymptom.id === sym.id;
    btn.className = `body-chip${sym.positive ? " positive" : ""}${isSelected ? " selected" : ""}`;
    btn.textContent = bodyLabel(sym);
    btn.type = "button";
    btn.onclick = () => { bodySelectedSymptom = sym; renderBodyChips(); };
    symptomBox.appendChild(btn);
  });
}

function renderBodyPairs() {
  const box = document.getElementById("bodyPairsView");
  if (!box) return;
  if (!bodyPairs.length) {
    box.textContent = t("body.noPairs");
    return;
  }
  box.innerHTML = bodyPairs.map((p, i) => `
    <div class="body-pair-item">
      <div><b>${bodyLabel(p.region)}</b> → ${bodyLabel(p.symptom)}
        <div style="font-size:11px;color:var(--muted-light);">${currentLang === "zh" ? "严重程度" : "Severity"}: ${p.severity} / 5</div>
      </div>
      <button onclick="removeBodyPair(${i})" type="button">✕</button>
    </div>
  `).join("");
}

function removeBodyPair(i) {
  bodyPairs.splice(i, 1);
  renderBodyPairs();
}

async function clearAllRecords() {
  if (!confirm("确定要清除所有记录吗？此操作不可撤销。")) return;
  const code = (participant?.participant_code || "local").trim() || "local";
  try {
    await fetch(`/participants/${encodeURIComponent(code)}/all-data`, { method: "DELETE" });
  } catch (e) {}
  entries = [];
  participant = null;
  localStorage.removeItem("emomirror.entries");
  localStorage.removeItem("emomirror.participant");
  localStorage.removeItem("emotype_participant_code");
  localStorage.removeItem("participant_code");
  localStorage.removeItem("participantCode");
  renderHome();
}

function bodyParticipantCode() {
  try { return localStorage.getItem("emomirror.participant") && JSON.parse(localStorage.getItem("emomirror.participant"))?.participant_code || ""; }
  catch (e) { return ""; }
}

async function submitBodyAdvice() {
  const btn = document.getElementById("bodySubmitBtn");
  const status = document.getElementById("bodySubmitStatus");
  const adviceBox = document.getElementById("bodyAdvice");
  if (!btn || !adviceBox) return;

  // Auto-add current selection if no pairs
  if (!bodyPairs.length) {
    const severity = Number((document.getElementById("bodySeverity") || {}).value || 3);
    const duration = (document.getElementById("bodyDuration") || {}).value || "";
    bodyPairs.push({ region: bodySelectedRegion, symptom: bodySelectedSymptom, severity, duration });
    renderBodyPairs();
  }

  btn.disabled = true;
  btn.textContent = currentLang === "zh" ? "生成中…" : "Generating…";
  if (status) status.textContent = currentLang === "zh" ? "正在调用模型，稍等…" : "Calling model, please wait…";
  adviceBox.style.display = "none";

  const payload = {
    participant_code: bodyParticipantCode() || "local",
    journal_text: (document.getElementById("bodyJournalText") || {}).value || (document.getElementById("journalText") || {}).value || "",
    selected_regions: [...new Map(bodyPairs.map((p) => [p.region.id, { id: p.region.id, label: p.region.zh }])).values()],
    symptoms: bodyPairs.map((p) => ({ region_id: p.region.id, label: p.symptom.zh, severity: p.severity, duration: p.duration })),
    free_text: (document.getElementById("bodyFreeText") || {}).value || "",
    include_recent_diaries: true,
    recent_diary_limit: 5,
  };

  try {
    const res = await fetch("/body-sensation/advice", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    renderBodyAdvice(data);
    if (status) status.textContent = currentLang === "zh" ? "建议已生成 ✓" : "Advice ready ✓";
  } catch (e) {
    if (status) status.textContent = currentLang === "zh" ? "请求失败，请检查后端是否运行" : "Request failed. Is the server running?";
  } finally {
    btn.disabled = false;
    btn.textContent = t("body.generate");
  }
}

function renderBodyAdvice(data) {
  const box = document.getElementById("bodyAdvice");
  if (!box) return;
  const advice = data.advice || {};
  const links = data.possible_links || [];
  const safety = data.safety || {};
  box.innerHTML = `
    <div class="advice-title">${advice.title || (currentLang === "zh" ? "建议" : "Advice")}</div>
    <div class="advice-summary">${advice.summary || ""}</div>
    ${advice.state_reading ? `<div style="padding:12px 14px;border-radius:10px;background:rgba(16,185,129,0.07);margin-bottom:12px;font-size:14px;line-height:1.7;">${advice.state_reading}</div>` : ""}
    ${links.length ? `<div class="advice-section">
      <h4>${currentLang === "zh" ? "身体-情绪线索" : "Body-Emotion Links"}</h4>
      <ul>${links.map((x) => `<li><b>${x.label || x.type || ""}</b>：${x.description || ""}</li>`).join("")}</ul>
    </div>` : ""}
    ${advice.steps && advice.steps.length ? `<div class="advice-section">
      <h4>${currentLang === "zh" ? "可尝试步骤" : "Steps to try"}</h4>
      <ol>${advice.steps.map((s) => `<li>${s}</li>`).join("")}</ol>
    </div>` : ""}
    ${advice.reflection_prompt ? `<div class="advice-section">
      <h4>${currentLang === "zh" ? "继续记录提示" : "Reflection prompt"}</h4>
      <p style="font-size:14px;color:var(--muted);">${advice.reflection_prompt}</p>
    </div>` : ""}
    ${safety.risk_level === "high" && safety.red_flags && safety.red_flags.length ? `
      <div style="border-radius:10px;background:var(--red-bg);padding:12px 14px;margin-top:10px;font-size:13px;color:var(--red);">
        ⚠️ ${safety.red_flags.join("；")}
      </div>` : ""}
    <div class="advice-meta">${currentLang === "zh" ? "来源" : "Source"}: ${advice.source || "-"} | ${currentLang === "zh" ? "不构成医疗建议" : "Not medical advice"}</div>
  `;
  box.style.display = "block";
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function initBodyTab() {
  updateJournalDate();
  renderBodyChips();
  renderBodyPairs();

  const addBtn = document.getElementById("bodyAddPair");
  if (addBtn) addBtn.addEventListener("click", () => {
    const severity = Number((document.getElementById("bodySeverity") || {}).value || 3);
    const duration = (document.getElementById("bodyDuration") || {}).value || "";
    bodyPairs.push({ region: bodySelectedRegion, symptom: bodySelectedSymptom, severity, duration });
    renderBodyPairs();
  });

  const clearBtn = document.getElementById("bodyClearPairs");
  if (clearBtn) clearBtn.addEventListener("click", () => { bodyPairs = []; renderBodyPairs(); });

  const submitBtn = document.getElementById("bodySubmitBtn");
  if (submitBtn) submitBtn.addEventListener("click", submitBodyAdvice);

  const severityEl = document.getElementById("bodySeverity");
  const severityLabel = document.getElementById("bodySeverityLabel");
  if (severityEl && severityLabel) {
    severityEl.addEventListener("input", () => { severityLabel.textContent = `${severityEl.value} / 5`; });
  }

  // Mirror journal text to body tab
  const journalEl = document.getElementById("journalText");
  const bodyJournalEl = document.getElementById("bodyJournalText");
  if (journalEl && bodyJournalEl) {
    journalEl.addEventListener("input", () => { bodyJournalEl.value = journalEl.value; });
    bodyJournalEl.value = journalEl.value;
  }

  // Data tab danger clear
  const clearEntriesData = document.getElementById("clearEntriesData");
  if (clearEntriesData) clearEntriesData.addEventListener("click", () => clearAllRecords());
}

/* ============================================================
   DATA TAB — Chart.js charts
   ============================================================ */
let emotionChartInst = null;
let vaChartInst = null;

function refreshDataCharts() {
  renderEmotionChart();
  renderVAChart();
  renderDataSummary();
}

function renderEmotionChart() {
  const canvas = document.getElementById("emotionChart");
  const noData = document.getElementById("chartNoData");
  if (!canvas) return;

  if (!entries.length) {
    canvas.style.display = "none";
    if (noData) noData.style.display = "block";
    return;
  }
  canvas.style.display = "block";
  if (noData) noData.style.display = "none";

  const counts = {};
  entries.forEach((e) => { const l = e.label || "中性"; counts[l] = (counts[l] || 0) + 1; });
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12);

  const COLORS = ["#F59E0B","#EF4444","#3B82F6","#10B981","#8B5CF6","#EC4899","#F97316","#06B6D4","#84CC16","#6366F1","#14B8A6","#F43F5E"];

  if (emotionChartInst) emotionChartInst.destroy();
  emotionChartInst = new Chart(canvas, {
    type: "bar",
    data: {
      labels: sorted.map(([l]) => l),
      datasets: [{
        data: sorted.map(([, c]) => c),
        backgroundColor: COLORS.slice(0, sorted.length),
        borderRadius: 8,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.parsed.y} ${currentLang === "zh" ? "次" : "times"}` } },
      },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: "rgba(245,158,11,0.1)" } },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderVAChart() {
  const canvas = document.getElementById("vaChart");
  const noData = document.getElementById("vaChartNoData");
  if (!canvas) return;

  const valid = entries.filter((e) => typeof e.valence === "number" && typeof e.arousal === "number");
  if (!valid.length) {
    canvas.style.display = "none";
    if (noData) noData.style.display = "block";
    return;
  }
  canvas.style.display = "block";
  if (noData) noData.style.display = "none";

  if (vaChartInst) vaChartInst.destroy();
  vaChartInst = new Chart(canvas, {
    type: "scatter",
    data: {
      datasets: [{
        label: currentLang === "zh" ? "情绪坐标" : "Emotion points",
        data: valid.map((e) => ({ x: e.valence || 0, y: e.arousal || 0, label: e.label })),
        backgroundColor: valid.map((e) => e.color || "#F59E0B"),
        pointRadius: 7,
        pointHoverRadius: 10,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.raw.label || ""} (V:${ctx.raw.x.toFixed(2)}, A:${ctx.raw.y.toFixed(2)})` } },
      },
      scales: {
        x: { min: -1, max: 1, title: { display: true, text: currentLang === "zh" ? "效价 (Valence)" : "Valence", color: "#78716C" }, grid: { color: "rgba(245,158,11,0.1)" } },
        y: { min: -1, max: 1, title: { display: true, text: currentLang === "zh" ? "唤醒度 (Arousal)" : "Arousal", color: "#78716C" }, grid: { color: "rgba(59,130,246,0.1)" } },
      },
    },
  });
}

function renderDataSummary() {
  const box = document.getElementById("dataSummary");
  if (!box) return;
  if (!entries.length) {
    box.textContent = currentLang === "zh" ? "暂无记录。" : "No entries yet.";
    return;
  }
  const counts = {};
  entries.forEach((e) => { const l = e.label || "中性"; counts[l] = (counts[l] || 0) + 1; });
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const avgV = entries.reduce((s, e) => s + (e.valence || 0), 0) / entries.length;
  const avgA = entries.reduce((s, e) => s + (e.arousal || 0), 0) / entries.length;
  box.innerHTML = [
    `${currentLang === "zh" ? "共" : "Total"} <b>${entries.length}</b> ${currentLang === "zh" ? "条记录" : "entries"}`,
    `${currentLang === "zh" ? "平均效价" : "Avg Valence"}: <b>${avgV.toFixed(2)}</b>`,
    `${currentLang === "zh" ? "平均唤醒度" : "Avg Arousal"}: <b>${avgA.toFixed(2)}</b>`,
    `${currentLang === "zh" ? "最常见情绪" : "Top emotions"}:`,
    ...top.map(([l, c]) => `&nbsp;&nbsp;${l} × ${c}`),
  ].join("<br>");
}

// Refresh button
document.addEventListener("DOMContentLoaded", () => {
  const refreshBtn = document.getElementById("refreshCharts");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshDataCharts);
});

boot();
