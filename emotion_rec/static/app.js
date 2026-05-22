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
  rose: "#E2C7D4",
};

const labelOptions = [
  "Unclear / mixed",
  "Anxiety / uncertainty",
  "Anger / grievance",
  "Sadness / loneliness",
  "Ease / positive energy",
  "Warmth / connection",
];

const emotionRules = [
  {
    label: "Anger / grievance",
    key: "anger",
    terms: ["angry", "mad", "hate", "unfair", "annoyed", "生气", "愤怒", "委屈", "烦", "不公平"],
    color: palette.orchid,
    style: { weight: 900, scale: 1.7, color: palette.orchid, animation: "shake-hard" },
    vad: { valence: 0.24, arousal: 0.78, dominance: 0.56 },
  },
  {
    label: "Anxiety / uncertainty",
    key: "anxiety",
    terms: ["anxious", "worry", "afraid", "tight", "nervous", "焦虑", "担心", "紧张", "害怕", "不安"],
    color: palette.plum,
    style: { weight: 780, scale: 1.55, color: palette.plum, animation: "shake-hard" },
    vad: { valence: 0.34, arousal: 0.72, dominance: 0.42 },
  },
  {
    label: "Sadness / loneliness",
    key: "sadness",
    terms: ["sad", "cry", "lonely", "tired", "empty", "难过", "失落", "孤独", "疲惫", "累"],
    color: palette.blueMist,
    style: { weight: 360, scale: 1.42, color: palette.blueMist, animation: "sad-droop" },
    vad: { valence: 0.22, arousal: 0.34, dominance: 0.38 },
  },
  {
    label: "Ease / positive energy",
    key: "joy",
    terms: ["happy", "joy", "calm", "proud", "relieved", "开心", "高兴", "轻松", "期待", "喜欢"],
    color: palette.mint,
    style: { weight: 820, scale: 1.55, color: "#3d8f8b", animation: "pulse-scale" },
    vad: { valence: 0.78, arousal: 0.56, dominance: 0.62 },
  },
  {
    label: "Warmth / connection",
    key: "warmth",
    terms: ["love", "safe", "warm", "understood", "爱", "温暖", "安心", "被理解", "陪伴"],
    color: palette.rose,
    style: { weight: 760, scale: 1.48, color: "#b45f9f", animation: "float-drift" },
    vad: { valence: 0.74, arousal: 0.42, dominance: 0.58 },
  },
];

let entries = JSON.parse(localStorage.getItem("emomirror.entries") || "[]");
let selectedLabel = "";
let analyzeTimer = null;
let recognition = null;
let isListening = false;

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
    fragment.appendChild(span);
  });

  typeStage.appendChild(fragment);
}

function localEmotion(text) {
  const lower = text.toLowerCase();
  const scores = emotionRules
    .map((rule) => ({
      rule,
      score: rule.terms.reduce((sum, term) => sum + (lower.includes(term.toLowerCase()) ? 1 : 0), 0),
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score);

  if (!scores.length) {
    return {
      primary: "Unclear / gently mixed",
      key: "unclear",
      confidence: text.trim() ? 0.36 : 0.12,
      color: palette.mauve,
      vad: { valence: 0.5, arousal: 0.42, dominance: 0.5 },
      reflection: "The mirror is still listening for a clearer emotional shape.",
      prompts: [
        "What word feels almost right?",
        "Where do you notice it in your body?",
        "What changed before this feeling appeared?",
      ],
    };
  }

  const rule = scores[0].rule;
  return {
    primary: rule.label,
    key: rule.key,
    confidence: Math.min(0.92, 0.48 + scores[0].score * 0.18),
    color: rule.color,
    vad: rule.vad,
    reflection: "This is a possible reading. If it feels off, choose a label that fits your lived experience better.",
    prompts: [
      "What makes this label feel true or untrue?",
      "Is there a smaller, more specific feeling underneath?",
      "What would you tell a friend feeling this?",
    ],
  };
}

function localDesign(text) {
  const design = {};
  const lower = text.toLowerCase();
  let styled = 0;

  for (const rule of emotionRules) {
    for (const term of rule.terms.sort((a, b) => b.length - a.length)) {
      const index = lower.indexOf(term.toLowerCase());
      if (index === -1 || styled >= 4) continue;
      for (let offset = 0; offset < term.length; offset += 1) {
        design[String(index + offset)] = rule.style;
      }
      styled += 1;
    }
  }

  if (!styled) {
    const match = text.match(/[A-Za-z']{5,}|[\u4e00-\u9fff]{2,4}/);
    if (match) {
      const emotion = localEmotion(text);
      const index = match.index || 0;
      for (let offset = 0; offset < match[0].length; offset += 1) {
        design[String(index + offset)] = {
          weight: 720,
          scale: 1.25,
          color: emotion.color,
          animation: "float-drift",
        };
      }
    }
  }

  return design;
}

function applyAnalysis(payload) {
  const emotion = payload.emotion || localEmotion(journalText.value);
  selectedLabel = emotion.primary;
  primaryEmotion.textContent = selectedLabel;
  reflectionText.textContent = emotion.reflection;
  confidenceMeter.style.width = `${Math.round((emotion.confidence || 0) * 100)}%`;
  emotionDot.style.background = emotion.color || palette.mauve;
  renderTypography(journalText.value, payload.llm_design || localDesign(journalText.value));
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
    applyAnalysis({ emotion: localEmotion(text), llm_design: {} });
    setStatus("Ready");
    return;
  }

  setStatus("Mirroring");
  applyAnalysis({ emotion: localEmotion(text), llm_design: localDesign(text) });

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
  renderTypography(journalText.value, localDesign(journalText.value));
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
    latestEmotion.textContent = "Unclear";
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

setupSpeechRecognition();
renderChips("");
renderPrompts(localEmotion("").prompts);
renderTypography(journalText.value, localDesign(journalText.value));
renderHome();
scheduleAnalysis();
