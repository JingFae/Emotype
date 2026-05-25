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

const labelOptions = [
  "中性",
  "复杂情绪",
  "消极高能量",
  "积极高能量",
  "消极低能量",
  "积极低能量",
];

let entries = JSON.parse(localStorage.getItem("emomirror.entries") || "[]");
let selectedLabel = "";
let analyzeTimer = null;
let recognition = null;
let isListening = false;

function vaMapper() {
  return window.VAMapper;
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
  const reflections = {
    high_negative: "镜面读到一种高能量的紧绷感。它可能接近愤怒、焦虑或不安，也可能只是身体在提醒你需要边界。",
    high_positive: "镜面读到一种明亮、上扬的能量。它可能接近兴奋、开心、期待或被激活的专注。",
    low_negative: "镜面读到一种低能量的下沉感。它可能接近疲惫、失落、孤独或迟缓的难过。",
    low_positive: "镜面读到一种低唤醒的稳定感。它可能接近平静、放松、满足或安全。",
    neutral: "镜面还没有读到明显方向。你可以继续写得更具体，或先停留在这种不确定里。",
  };
  return reflections[mapping.quadrant] || reflections.neutral;
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
    prompts: [
      "这个词贴近吗？如果不贴近，哪个词更像？",
      "身体里哪个位置最先出现这种感觉？",
      "如果把它减轻 10%，你现在需要什么？",
    ],
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
        color: style.color,
        backgroundColor: value.backgroundColor || style.color,
      },
    ]),
  );
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
  selectedLabel = emotion.primary;
  primaryEmotion.textContent = selectedLabel;
  reflectionText.textContent = emotion.reflection;
  confidenceMeter.style.width = `${Math.round((emotion.confidence || 0) * 100)}%`;
  emotionDot.style.background = emotion.color || palette.mauve;

  const hasRemoteDesign = payload.llm_design && Object.keys(payload.llm_design).length > 0;
  const design = hasRemoteDesign
    ? normalizeDesignColors(payload.llm_design, overall)
    : localDesign(journalText.value, vaMapping);
  renderTypography(journalText.value, design);
  renderChips(selectedLabel);
  renderPrompts(emotion.prompts || []);
}

function renderChips(activeLabel) {
  emotionChips.textContent = "";
  labelOptions.forEach((label) => {
    const button = document.createElement("button");
    button.className = `emotion-chip ${label === activeLabel ? "is-active" : ""}`;
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => {
      selectedLabel = label;
      primaryEmotion.textContent = label;
      renderChips(label);
    });
    emotionChips.appendChild(button);
  });
}

function renderPrompts(prompts) {
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

function saveCurrentEntry() {
  const text = journalText.value.trim();
  if (!text) {
    setStatus("Nothing to save");
    return;
  }
  const confidence = Math.round(Number(confidenceMeter.style.width.replace("%", "")) || 0);
  entries.unshift({
    text,
    label: selectedLabel || primaryEmotion.textContent,
    confidence,
    date: new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date()),
  });
  entries = entries.slice(0, 12);
  saveEntries();
  renderHome();
  setStatus("Saved locally");
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

function bindEvents() {
  viewButtons.forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.viewTarget));
  });

  journalText.addEventListener("input", scheduleAnalysis);
  intensityRange.addEventListener("input", () => {
    homeIntensity.textContent = `${intensityRange.value}%`;
    renderTypography(journalText.value, localDesign(journalText.value));
    scheduleAnalysis();
  });
  saveEntry.addEventListener("click", saveCurrentEntry);
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
  bindEvents();
  setupSpeechRecognition();
  renderChips("");
  renderPrompts(localEmotion("").prompts);
  renderTypography(journalText.value, localDesign(journalText.value));
  renderHome();
  scheduleAnalysis();
}

boot();
