const views = document.querySelectorAll(".view");
const viewButtons = document.querySelectorAll("[data-view-target]");
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
const participantForm = document.querySelector("#participantForm");
const participantCodeInput = document.querySelector("#participantCode");
const participantConsent = document.querySelector("#participantConsent");
const participantStatus = document.querySelector("#participantStatus");
const exportParticipantJson = document.querySelector("#exportParticipantJson");
const exportParticipantCsv = document.querySelector("#exportParticipantCsv");
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

function vaMapper() {
  return window.VAMapper;
}

function clampNumber(value, lower = -1, upper = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(lower, Math.min(upper, number));
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
    const isActive = button.dataset.viewTarget === targetId;
    if (button.classList.contains("tab-button")) {
      button.classList.toggle("is-active", isActive);
    }
  });
}

function setStatus(text) {
  analysisStatus.textContent = text;
}

function participantCode() {
  return participant?.participant_code || "";
}

function setParticipantStatus(text) {
  participantStatus.textContent = text;
}

function saveParticipant(nextParticipant) {
  participant = nextParticipant;
  if (participant) {
    localStorage.setItem("emomirror.participant", JSON.stringify(participant));
    participantCodeInput.value = participant.participant_code;
    setParticipantStatus(`已连接实验编号 ${participant.participant_code}`);
  } else {
    localStorage.removeItem("emomirror.participant");
    setParticipantStatus("未连接实验编号，本机会先临时保存。");
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
    setParticipantStatus(`已加载 ${participantCode()} 的历史记录`);
  } catch (error) {
    setParticipantStatus(`历史读取失败：${error.message}`);
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
    setParticipantStatus("已导出本地临时数据。");
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
    setParticipantStatus(`已导出 ${format.toUpperCase()} 数据。`);
  } catch (error) {
    setParticipantStatus(`导出失败：${error.message}`);
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

function addStyleRange(design, start, length, style, onlyIfEmpty = false) {
  for (let offset = 0; offset < length; offset += 1) {
    const key = String(start + offset);
    if (onlyIfEmpty && design[key]) continue;
    design[key] = { ...(design[key] || {}), ...style };
  }
}

function renderTypography(text, design = {}) {
  typeStage.textContent = "";
  const fragment = document.createDocumentFragment();

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
  const lexiconMatches = vaMapper()
    .getEmotionLexicon()
    .filter((item) => item.label && segmentText.includes(item.label));

  if (lexiconMatches.length) return averageMatches(lexiconMatches);

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
    const index = text.indexOf(item.label);
    if (index === -1 || styledTerms >= 4) continue;
    addStyleRange(design, index, item.label.length, styleForMapping(vaMapper().mapVA(item)));
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

  renderTypography(journalText.value, recolorDesign(currentDesign, next));
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
  renderTypography(journalText.value, design);
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
  renderTypography(journalText.value, localDesign(journalText.value, mapping));
  analyzeTimer = setTimeout(analyzeText, 420);
}

function saveEntries() {
  localStorage.setItem("emomirror.entries", JSON.stringify(entries));
}

function renderHome() {
  entryCount.textContent = String(entries.length);
  homeIntensity.textContent = `${intensityRange.value}%`;
  entryStorageMode.textContent = participantCode() ? `synced as ${participantCode()}` : "local only";

  if (entries.length) {
    const latest = entries[0];
    latestEmotion.textContent = latest.label;
    latestConfidence.textContent = `${latest.confidence}% confidence`;
    homeMirrorWord.textContent = latest.label.split("/")[0].trim().toLowerCase();
    homeMirrorCaption.textContent = latest.date;
  } else {
    latestEmotion.textContent = "中性";
    latestConfidence.textContent = "waiting for text";
    homeMirrorWord.textContent = "steady";
    homeMirrorCaption.textContent = "No entry yet today";
  }

  entryList.textContent = "";
  if (!entries.length) {
    const empty = document.createElement("article");
    empty.className = "entry-card";
    const title = document.createElement("strong");
    const copy = document.createElement("p");
    title.textContent = "No local entries yet";
    copy.textContent = "Your saved reflections will appear here on this device.";
    empty.append(title, copy);
    entryList.appendChild(empty);
    return;
  }

  entries.slice(0, 6).forEach((entry) => {
    const card = document.createElement("article");
    card.className = "entry-card";
    const title = document.createElement("strong");
    const copy = document.createElement("p");
    const date = document.createElement("small");
    title.textContent = entry.label;
    copy.textContent = entry.text;
    date.textContent = entry.date;
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

  if (participantCode()) {
    try {
      const data = await apiJson("/diaries", {
        method: "POST",
        body: JSON.stringify({
          participant_code: participantCode(),
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
      setStatus("Saved to research log");
      return;
    } catch (error) {
      setStatus("Saved locally; sync failed");
      setParticipantStatus(`保存到数据库失败：${error.message}`);
    }
  }

  entries.unshift(localEntry);
  entries = entries.slice(0, 12);
  saveEntries();
  renderHome();
  if (!participantCode()) setStatus("Saved locally");
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceButton.disabled = true;
    voiceButton.textContent = "Voice unavailable";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = navigator.language || "en-US";

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
    setStatus(interimText ? "Listening" : "Voice captured");
  };

  recognition.onend = () => {
    isListening = false;
    voiceButton.textContent = "Start voice";
    typingMode.classList.add("is-active");
    voiceMode.classList.remove("is-active");
  };

  recognition.onerror = () => {
    isListening = false;
    voiceButton.textContent = "Start voice";
    setStatus("Voice unavailable");
  };
}

function toggleVoice() {
  if (!recognition) return;
  if (isListening) {
    recognition.stop();
    return;
  }
  isListening = true;
  voiceButton.textContent = "Stop voice";
  typingMode.classList.remove("is-active");
  voiceMode.classList.add("is-active");
  try {
    recognition.start();
  } catch (error) {
    isListening = false;
    voiceButton.textContent = "Start voice";
    setStatus("Voice paused");
  }
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
  logUsageEvent("va_coordinate_adjusted", {
    valence: currentOverallMapping?.valence,
    arousal: currentOverallMapping?.arousal,
    label: currentOverallMapping?.label,
    method: "keyboard",
  });
  setStatus("Coordinate adjusted");
}

async function connectParticipant(event) {
  event.preventDefault();
  const code = participantCodeInput.value.trim();
  if (!code) {
    setParticipantStatus("请输入实验编号，例如 P001。");
    return;
  }
  if (!participantConsent.checked) {
    setParticipantStatus("需要先同意保存日记和操作日志，才能连接实验编号。");
    return;
  }
  setParticipantStatus("正在连接实验编号...");
  try {
    const data = await apiJson("/participants/session", {
      method: "POST",
      body: JSON.stringify({
        participant_code: code,
        consent_version: "research-v1",
      }),
    });
    saveParticipant(data.participant);
    await loadParticipantEntries();
  } catch (error) {
    setParticipantStatus(`连接失败：${error.message}`);
  }
}

function bindEvents() {
  viewButtons.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.viewTarget));
  });

  participantForm.addEventListener("submit", connectParticipant);
  exportParticipantJson.addEventListener("click", () => exportParticipant("json"));
  exportParticipantCsv.addEventListener("click", () => exportParticipant("csv"));
  journalText.addEventListener("input", scheduleAnalysis);
  intensityRange.addEventListener("input", () => {
    homeIntensity.textContent = `${intensityRange.value}%`;
    if (currentOverallMapping) {
      renderTypography(journalText.value, recolorDesign(currentDesign, currentOverallMapping));
    } else {
      renderTypography(journalText.value, localDesign(journalText.value));
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
    logUsageEvent("va_coordinate_adjusted", {
      valence: currentOverallMapping?.valence,
      arousal: currentOverallMapping?.arousal,
      label: currentOverallMapping?.label,
      method: "pointer",
    });
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
  clearEntries.addEventListener("click", () => {
    entries = [];
    saveEntries();
    renderHome();
  });
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
  bindEvents();
  setupSpeechRecognition();
  renderChips("");
  renderPrompts(localEmotion("").prompts);
  renderTypography(journalText.value, localDesign(journalText.value));
  if (participantCode()) await loadParticipantEntries();
  else renderHome();
  scheduleAnalysis();
}

boot();
