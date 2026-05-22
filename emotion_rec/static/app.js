const transcript = document.querySelector("#transcript");
const typeStage = document.querySelector("#typeStage");
const requestStatus = document.querySelector("#requestStatus");
const serviceStatus = document.querySelector("#serviceStatus");
const audioFile = document.querySelector("#audioFile");
const chooseFile = document.querySelector("#chooseFile");
const fileName = document.querySelector("#fileName");
const dropZone = document.querySelector("#dropZone");
const recordBtn = document.querySelector("#recordBtn");
const analyzeBtn = document.querySelector("#analyzeBtn");
const waveCanvas = document.querySelector("#waveCanvas");
const waveCtx = waveCanvas.getContext("2d");

const emojiMap = {
  HAPPY: "😃",
  SAD: "😢",
  ANGRY: "😠",
  LOVE: "😍",
  COOL: "😎",
  WINK: "😉",
  SHOCK: "😮",
  SICK: "🤢",
  DEAD: "💀",
  GHOST: "👻",
  CLOWN: "🤡",
  ALIEN: "👽",
  STAR: "🤩",
  SLEEP: "😴",
  THINK: "🤔",
  CONFUSED: "🫠",
  CLOCK: "⏰",
  PIZZA: "🍕",
  BULB: "💡",
  FIRE: "🔥",
  CUP: "☕",
  BOMB: "💣",
  MOON: "🌙",
  SUN: "☀️",
  BALL: "⚽",
  DONUT: "🍩",
  POOP: "💩",
  MIC: "🎙️",
  TENT: "⛺",
};

let selectedBlob = null;
let selectedFileName = "";
let mediaRecorder = null;
let mediaStream = null;
let analyser = null;
let animationFrame = null;
let chunks = [];

function clamp01(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return 0;
  return Math.max(0, Math.min(1, num));
}

function setStatus(text, busy = false) {
  requestStatus.textContent = text;
  serviceStatus.textContent = busy ? "Working" : "Ready";
  analyzeBtn.disabled = busy;
}

function animationClass(name) {
  if (!name) return "";
  return `anim-${String(name).replace(/[^a-z0-9-]/gi, "").toLowerCase()}`;
}

function renderTypography(text, design = {}) {
  typeStage.textContent = "";
  const fragment = document.createDocumentFragment();
  [...text].forEach((char, index) => {
    const span = document.createElement("span");
    const style = design[String(index)] || {};
    const emoji = style.emoji ? emojiMap[String(style.emoji).toUpperCase()] : null;
    const scale = Number.isFinite(Number(style.scale)) ? Math.max(0.8, Math.min(2.4, Number(style.scale))) : 1;
    span.className = `glyph ${char === " " ? "space" : ""} ${emoji ? "emoji" : ""} ${animationClass(style.animation)}`;
    span.textContent = char === " " ? "\u00a0" : emoji || char;
    span.style.setProperty("--scale", scale);
    span.style.setProperty("--glyph-weight", style.weight || 520);
    span.style.setProperty("--glyph-color", style.color || "var(--ink)");
    fragment.appendChild(span);
  });
  typeStage.appendChild(fragment);
}

function localDesign(text) {
  const rules = [
    { terms: ["angry", "mad", "hate", "urgent", "stop"], color: "#dc2626", animation: "shake-hard", emoji: "ANGRY", targets: "ao", weight: 900 },
    { terms: ["happy", "haha", "fun", "amazing", "wow", "won", "lottery"], color: "#f59e0b", animation: "pulse-scale", emoji: "HAPPY", targets: "ao", weight: 850 },
    { terms: ["sad", "cry", "lonely", "tired", "left"], color: "#475569", animation: "sad-droop", emoji: "SAD", targets: "aeo", weight: 360 },
    { terms: ["love", "heart", "like"], color: "#ec4899", animation: "float-drift", emoji: "LOVE", targets: "ov", weight: 820 },
    { terms: ["fire", "hot", "lit"], color: "#ef4444", animation: "pulse-scale", emoji: "FIRE", targets: "il", weight: 860 },
    { terms: ["time", "late", "now"], color: "#2563eb", animation: "float-drift", emoji: "CLOCK", targets: "oi", weight: 780 },
  ];
  const design = {};
  const lower = text.toLowerCase();
  let styled = 0;

  for (const rule of rules) {
    for (const term of rule.terms) {
      const index = lower.indexOf(term);
      if (index === -1 || styled >= 3) continue;
      let emojiApplied = false;
      for (let offset = 0; offset < term.length; offset += 1) {
        const char = lower[index + offset];
        design[String(index + offset)] = {
          weight: rule.weight,
          scale: 1.25 + Math.min(0.45, term.length * 0.04),
          color: rule.color,
          animation: rule.animation,
        };
        if (!emojiApplied && rule.targets.includes(char)) {
          design[String(index + offset)].emoji = rule.emoji;
          emojiApplied = true;
        }
      }
      styled += 1;
    }
  }

  return design;
}

function updateMetric(name, value) {
  const safe = clamp01(value);
  document.querySelector(`#${name}Value`).textContent = safe.toFixed(2);
  document.querySelector(`#${name}Meter`).style.width = `${safe * 100}%`;
}

function updateMetrics(payload = {}) {
  const vad = payload.vad || {};
  const acoustics = payload.acoustics || {};
  updateMetric("valence", vad.valence);
  updateMetric("arousal", vad.arousal);
  updateMetric("dominance", vad.dominance);
  updateMetric("energy", acoustics.energy_norm);
}

function paintIdleWave() {
  const width = waveCanvas.width;
  const height = waveCanvas.height;
  waveCtx.clearRect(0, 0, width, height);
  waveCtx.fillStyle = "#101513";
  waveCtx.fillRect(0, 0, width, height);
  for (let x = 0; x < width; x += 18) {
    const t = x / width;
    const bar = 18 + Math.sin(t * Math.PI * 6) * 13 + Math.sin(t * Math.PI * 15) * 8;
    waveCtx.fillStyle = x % 54 === 0 ? "#e2553f" : "#4db6aa";
    waveCtx.fillRect(x, height / 2 - bar / 2, 7, bar);
  }
}

function drawLiveWave() {
  if (!analyser) return;
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteTimeDomainData(data);

  const width = waveCanvas.width;
  const height = waveCanvas.height;
  waveCtx.clearRect(0, 0, width, height);
  waveCtx.fillStyle = "#101513";
  waveCtx.fillRect(0, 0, width, height);
  waveCtx.lineWidth = 3;
  waveCtx.strokeStyle = "#f59e0b";
  waveCtx.beginPath();

  const step = width / data.length;
  data.forEach((value, index) => {
    const x = index * step;
    const y = (value / 255) * height;
    if (index === 0) waveCtx.moveTo(x, y);
    else waveCtx.lineTo(x, y);
  });

  waveCtx.stroke();
  animationFrame = requestAnimationFrame(drawLiveWave);
}

async function startRecording() {
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(mediaStream);
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);

  chunks = [];
  mediaRecorder = new MediaRecorder(mediaStream);
  mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  mediaRecorder.onstop = () => {
    selectedBlob = new Blob(chunks, { type: "audio/webm" });
    selectedFileName = `emotype-recording-${Date.now()}.webm`;
    fileName.textContent = selectedFileName;
    mediaStream.getTracks().forEach((track) => track.stop());
    cancelAnimationFrame(animationFrame);
    analyser = null;
    paintIdleWave();
  };
  mediaRecorder.start();
  recordBtn.textContent = "Stop";
  recordBtn.classList.add("is-recording");
  setStatus("Recording");
  drawLiveWave();
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  recordBtn.innerHTML = '<span class="button-icon record-icon" aria-hidden="true"></span>Record';
  recordBtn.classList.remove("is-recording");
  setStatus("Recorded");
}

async function analyze() {
  const text = transcript.value.trim();
  const blob = selectedBlob || audioFile.files[0];
  if (!blob) {
    setStatus("Add audio");
    return;
  }

  setStatus("Analyzing", true);
  renderTypography(text, localDesign(text));

  const formData = new FormData();
  formData.append("file", blob, selectedFileName || blob.name || "audio.webm");
  formData.append("text", text);

  try {
    const response = await fetch("/predict?return_embeddings=false", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Request failed");
    }
    renderTypography(text, payload.llm_design || {});
    updateMetrics(payload);
    setStatus("Rendered");
  } catch (error) {
    setStatus(error.message || "Failed");
  }
}

chooseFile.addEventListener("click", () => audioFile.click());

audioFile.addEventListener("change", () => {
  const file = audioFile.files[0];
  selectedBlob = file || null;
  selectedFileName = file ? file.name : "";
  fileName.textContent = file ? file.name : "No file selected";
  setStatus(file ? "Audio ready" : "Idle");
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  const file = event.dataTransfer.files[0];
  if (!file) return;
  selectedBlob = file;
  selectedFileName = file.name;
  fileName.textContent = file.name;
});

recordBtn.addEventListener("click", async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopRecording();
    return;
  }

  try {
    await startRecording();
  } catch (error) {
    setStatus("Mic blocked");
  }
});

analyzeBtn.addEventListener("click", analyze);

transcript.addEventListener("input", () => {
  renderTypography(transcript.value, localDesign(transcript.value));
});

paintIdleWave();
renderTypography(transcript.value, localDesign(transcript.value));
updateMetrics({ vad: { valence: 0, arousal: 0, dominance: 0 }, acoustics: { energy_norm: 0 } });
