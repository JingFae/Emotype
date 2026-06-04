const WEATHER_OPTIONS = ["sunny", "cloudy", "overcast", "rainy", "stormy", "snowy", "windy", "foggy"];
const WEATHER_LABELS = {
  sunny: "晴朗",
  cloudy: "多云",
  overcast: "阴天",
  rainy: "下雨",
  stormy: "暴风雨",
  snowy: "下雪",
  windy: "有风",
  foggy: "有雾",
};

const els = {
  participant: document.getElementById("diaryParticipant"),
  date: document.getElementById("diaryDate"),
  physicalWeather: document.getElementById("physicalWeather"),
  moodWeather: document.getElementById("moodWeather"),
  title: document.getElementById("diaryEntryTitle"),
  content: document.getElementById("diaryContent"),
  saveState: document.getElementById("saveState"),
  saveBtn: document.getElementById("saveDiaryBtn"),
  reflectBtn: document.getElementById("reflectDiaryBtn"),
  voiceBtn: document.getElementById("voiceDiaryBtn"),
  refreshContextBtn: document.getElementById("refreshContextBtn"),
  insertContextBtn: document.getElementById("insertContextBtn"),
  contextList: document.getElementById("contextList"),
  contextCount: document.getElementById("contextCount"),
  reflectionState: document.getElementById("reflectionState"),
  reflectionCard: document.getElementById("reflectionCard"),
  reflectionPrimary: document.getElementById("reflectionPrimary"),
  reflectionSummary: document.getElementById("reflectionSummary"),
  reflectionGentle: document.getElementById("reflectionGentle"),
  reflectionTrigger: document.getElementById("reflectionTrigger"),
  reflectionNeed: document.getElementById("reflectionNeed"),
  weatherReflection: document.getElementById("weatherReflection"),
  vaReadout: document.getElementById("diaryVAReadout"),
  vaHandle: document.getElementById("diaryVAHandle"),
  colorSwatch: document.getElementById("emotionColorSwatch"),
  colorName: document.getElementById("emotionColorName"),
  secondaryEmotionChips: document.getElementById("secondaryEmotionChips"),
  fineEmotionChips: document.getElementById("fineEmotionChips"),
  bodySignalChips: document.getElementById("bodySignalChips"),
  questions: document.getElementById("reflectionQuestions"),
  smallAction: document.getElementById("smallActionSuggestion"),
};

const state = {
  diary: null,
  contextRecords: [],
  selectedSourceIds: new Set(),
  autosaveTimer: null,
  idleReflectTimer: null,
  dirty: false,
  hydrating: false,
  saving: false,
  savePromise: null,
  reflecting: false,
  recognition: null,
  listening: false,
  lastReflectHash: "",
};

function participantCode() {
  try {
    const participant = JSON.parse(localStorage.getItem("emomirror.participant") || "null");
    return participant?.participant_code || "";
  } catch (error) {
    return "";
  }
}

function todayISO() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function queryWithParticipant(url) {
  const code = participantCode();
  if (!code) return url;
  const joiner = url.includes("?") ? "&" : "?";
  return `${url}${joiner}participant_code=${encodeURIComponent(code)}`;
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let message = response.statusText || "request failed";
    try {
      const body = await response.json();
      message = body.detail || body.error || message;
    } catch (error) {}
    throw new Error(message);
  }
  return response.json();
}

function setSaveState(text) {
  els.saveState.textContent = text;
}

function setReflectionState(text) {
  els.reflectionState.textContent = text;
}

function formatSigned(value) {
  const number = Number.isFinite(Number(value)) ? Math.max(-1, Math.min(1, Number(value))) : 0;
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function hexToRgba(hex, alpha) {
  const clean = String(hex || "").replace("#", "");
  if (clean.length !== 6) return `rgba(148, 163, 184, ${alpha})`;
  const r = Number.parseInt(clean.slice(0, 2), 16);
  const g = Number.parseInt(clean.slice(2, 4), 16);
  const b = Number.parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function sourceLabel(source) {
  return {
    journal: "随手记",
    body_sensation: "身体感受",
    realtime_emotion: "实时情绪",
    local_journal: "本地随手记",
  }[source] || source || "记录";
}

function contextKey(record) {
  return `${record.source}:${record.id}`;
}

function currentSourceIds() {
  return Array.from(state.selectedSourceIds);
}

function currentPayload(saveType = "autosave") {
  return {
    participant_code: participantCode() || null,
    title: els.title.value.trim(),
    content: els.content.value,
    physical_weather: els.physicalWeather.value,
    mood_weather: els.moodWeather.value,
    source_entry_ids_json: currentSourceIds(),
    save_type: saveType,
    auto_analyze: false,
    is_draft: saveType === "autosave",
  };
}

function reflectHash() {
  return JSON.stringify({
    date: els.date.value,
    title: els.title.value.trim(),
    content: els.content.value,
    physical_weather: els.physicalWeather.value,
    mood_weather: els.moodWeather.value,
    sources: currentSourceIds().sort(),
  });
}

function populateWeatherSelect(select) {
  select.textContent = "";
  WEATHER_OPTIONS.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = WEATHER_LABELS[value];
    select.appendChild(option);
  });
}

function setVA(valence = 0, arousal = 0, color = "#94A3B8") {
  const v = Number.isFinite(Number(valence)) ? Math.max(-1, Math.min(1, Number(valence))) : 0;
  const a = Number.isFinite(Number(arousal)) ? Math.max(-1, Math.min(1, Number(arousal))) : 0;
  const x = ((v + 1) / 2) * 100;
  const y = ((1 - a) / 2) * 100;
  document.documentElement.style.setProperty("--reflection-color", color || "#94A3B8");
  document.body.style.setProperty("--diary-emotion-bg", hexToRgba(color, 0.12));
  els.reflectionCard.style.setProperty("--soft-reflection", hexToRgba(color, 0.15));
  els.vaHandle.style.left = `${x}%`;
  els.vaHandle.style.top = `${y}%`;
  els.vaHandle.style.background = color || "#94A3B8";
  els.colorSwatch.style.background = color || "#94A3B8";
  els.vaReadout.textContent = `V ${formatSigned(v)} · A ${formatSigned(a)}`;
}

function renderChipList(container, items = []) {
  if (!container) return;
  const list = Array.isArray(items) ? items : (items ? [items] : []);
  container.textContent = "";
  list.slice(0, 8).forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "emotion-chip";
    chip.textContent = String(item);
    container.appendChild(chip);
  });
}

function renderQuestions(items = []) {
  els.questions.textContent = "";
  items.slice(0, 4).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = String(item);
    els.questions.appendChild(li);
  });
}

function applyReflectionFromDiary(diary) {
  const reflection = diary?.reflection_json || {};
  const hasReflection = Object.keys(reflection).length > 0;
  const color = diary?.emotion_color || reflection.emotion_color || "#94A3B8";
  const primary = diary?.primary_emotion || reflection.primary_emotion || "尚无结果";
  setVA(diary?.valence ?? reflection.valence ?? 0, diary?.arousal ?? reflection.arousal ?? 0, color);
  els.colorName.textContent = diary?.emotion_color_name || reflection.emotion_color_name || "雾灰中性";
  els.reflectionPrimary.textContent = primary;
  els.reflectionSummary.textContent = reflection.event_summary || (hasReflection ? "今日复盘" : "写完后会生成当天复盘");
  els.reflectionGentle.textContent = reflection.gentle_reflection || "复盘会参考正文、所选天气和今日情绪记录，但不会把情绪强行归因于天气。";
  els.reflectionTrigger.textContent = reflection.possible_trigger || "-";
  els.reflectionNeed.textContent = reflection.possible_need || "-";
  els.weatherReflection.textContent = reflection.weather_reflection || "-";
  els.smallAction.textContent = reflection.small_action_suggestion || "-";
  renderChipList(els.secondaryEmotionChips, reflection.secondary_emotions || diary?.secondary_emotions_json || []);
  renderChipList(els.fineEmotionChips, reflection.fine_grained_emotions || diary?.fine_emotions_json || []);
  renderChipList(els.bodySignalChips, reflection.body_signals || diary?.body_signals_json || []);
  renderQuestions(reflection.reflection_questions || []);
  setReflectionState(diary?.analysis_pending ? "待更新" : (hasReflection ? "已复盘" : "待复盘"));
}

function applyDiary(diary) {
  state.hydrating = true;
  state.diary = diary || {};
  els.title.value = state.diary.title || "";
  els.content.value = state.diary.content || "";
  els.physicalWeather.value = state.diary.physical_weather || "sunny";
  els.moodWeather.value = state.diary.mood_weather || "sunny";
  state.selectedSourceIds = new Set((state.diary.source_entry_ids_json || []).map(String));
  state.dirty = false;
  state.lastReflectHash = state.diary.analysis_pending ? "" : reflectHash();
  applyReflectionFromDiary(state.diary);
  setSaveState(state.diary.id ? "已载入" : "空草稿");
  state.hydrating = false;
}

function localJournalContext() {
  if (participantCode()) return [];
  try {
    const entries = JSON.parse(localStorage.getItem("emomirror.entries") || "[]");
    return entries.slice(0, 8).map((entry, index) => ({
      source: "local_journal",
      id: entry.id || `local-${index}`,
      time: entry.date || "本地记录",
      summary: entry.text || "本地随手记记录",
      valence: entry.valence,
      arousal: entry.arousal,
      primary_emotion: entry.label || "中性",
    }));
  } catch (error) {
    return [];
  }
}

function renderContext() {
  els.contextList.textContent = "";
  els.contextCount.textContent = String(state.contextRecords.length);
  if (!state.contextRecords.length) {
    const empty = document.createElement("p");
    empty.className = "context-empty";
    empty.textContent = "今天还没有可查询的随手记、身体感受或实时情绪记录。";
    els.contextList.appendChild(empty);
    return;
  }

  state.contextRecords.forEach((record) => {
    const key = contextKey(record);
    const label = document.createElement("label");
    label.className = "context-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedSourceIds.has(key);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selectedSourceIds.add(key);
      else state.selectedSourceIds.delete(key);
      scheduleAutosave();
    });

    const body = document.createElement("div");
    const meta = document.createElement("div");
    meta.className = "context-meta";
    const source = document.createElement("span");
    source.className = "context-source";
    source.textContent = sourceLabel(record.source);
    const time = document.createElement("span");
    time.textContent = record.time ? new Date(record.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
    if (Number.isNaN(new Date(record.time).getTime())) time.textContent = record.time || "";
    const emotion = document.createElement("span");
    emotion.textContent = record.primary_emotion || "中性";
    meta.append(source, time, emotion);

    const summary = document.createElement("p");
    summary.className = "context-summary";
    summary.textContent = record.summary || "记录";

    const va = document.createElement("div");
    va.className = "context-va";
    va.textContent = `V ${formatSigned(record.valence ?? 0)} · A ${formatSigned(record.arousal ?? 0)}`;

    body.append(meta, summary, va);
    label.append(checkbox, body);
    els.contextList.appendChild(label);
  });
}

async function loadContext() {
  const url = queryWithParticipant(`/api/diary/context?date=${encodeURIComponent(els.date.value)}`);
  try {
    const data = await apiJson(url);
    state.contextRecords = [...(data.records || []), ...localJournalContext()];
  } catch (error) {
    state.contextRecords = localJournalContext();
  }
  renderContext();
}

async function loadDiary() {
  clearTimeout(state.autosaveTimer);
  clearTimeout(state.idleReflectTimer);
  setSaveState("载入中");
  const url = queryWithParticipant(`/api/diary?date=${encodeURIComponent(els.date.value)}`);
  try {
    const data = await apiJson(url);
    applyDiary(data.diary || {});
  } catch (error) {
    setSaveState(`载入失败：${error.message}`);
    applyDiary({ diary_date: els.date.value, physical_weather: "sunny", mood_weather: "sunny" });
  }
  await loadContext();
}

async function saveDiary(saveType = "autosave") {
  if (state.saving) return state.savePromise || state.diary;
  state.saving = true;
  els.saveBtn.disabled = true;
  setSaveState(saveType === "autosave" ? "自动保存中" : "保存中");
  state.savePromise = (async () => {
    const payload = currentPayload(saveType);
    const payloadHash = reflectHash();
    const data = await apiJson(`/api/diary/by-date/${encodeURIComponent(els.date.value)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.diary = data.diary;
    state.dirty = reflectHash() !== payloadHash;
    setSaveState(state.dirty ? "有未保存修改" : (saveType === "autosave" ? "已自动保存" : "已保存"));
    applyReflectionFromDiary(state.diary);
    return state.diary;
  })();
  try {
    return await state.savePromise;
  } catch (error) {
    setSaveState(`保存失败：${error.message}`);
    throw error;
  } finally {
    state.saving = false;
    state.savePromise = null;
    els.saveBtn.disabled = false;
  }
}

async function reflectDiary(reason = "manual") {
  const hash = reflectHash();
  const contentLength = els.content.value.trim().length;
  if (state.reflecting) return;
  if (!contentLength) {
    setReflectionState("待复盘");
    if (reason === "manual") setSaveState("先写一点内容再复盘");
    return;
  }
  if (reason === "idle" && contentLength < 24) {
    setReflectionState("待复盘");
    return;
  }
  if (reason === "idle" && hash === state.lastReflectHash) return;

  state.reflecting = true;
  els.reflectBtn.disabled = true;
  els.saveBtn.disabled = true;
  setReflectionState("复盘中");
  try {
    if (state.saving) await saveDiary(reason === "manual" ? "manual" : "autosave");
    for (let attempts = 0; state.dirty && attempts < 2; attempts += 1) {
      await saveDiary(reason === "manual" ? "manual" : "autosave");
    }
    if (state.dirty) {
      setReflectionState("待更新");
      setSaveState("有未保存修改");
      return;
    }
    const data = await apiJson(`/api/diary/by-date/${encodeURIComponent(els.date.value)}/reflect`, {
      method: "POST",
      body: JSON.stringify({ participant_code: participantCode() || null }),
    });
    state.diary = data.diary;
    state.lastReflectHash = reflectHash();
    state.dirty = false;
    applyReflectionFromDiary(state.diary);
    setSaveState("复盘已保存");
  } catch (error) {
    setReflectionState("复盘失败");
    setSaveState(`复盘失败：${error.message}`);
  } finally {
    state.reflecting = false;
    els.reflectBtn.disabled = false;
    els.saveBtn.disabled = false;
  }
}

function scheduleAutosave() {
  if (state.hydrating) return;
  state.dirty = true;
  setSaveState("等待自动保存");
  if ((state.diary?.reflection_json && Object.keys(state.diary.reflection_json).length) || state.diary?.last_analyzed_at) {
    setReflectionState("待更新");
  }
  clearTimeout(state.autosaveTimer);
  clearTimeout(state.idleReflectTimer);
  state.autosaveTimer = setTimeout(() => saveDiary("autosave").catch(() => {}), 2200);
  state.idleReflectTimer = setTimeout(async () => {
    try {
      if (state.dirty) await saveDiary("autosave");
      await reflectDiary("idle");
    } catch (error) {}
  }, 6800);
}

function insertSelectedContext() {
  const selected = state.contextRecords.filter((record) => state.selectedSourceIds.has(contextKey(record)));
  if (!selected.length) return;
  const lines = selected.map((record) => `- ${sourceLabel(record.source)}｜${record.primary_emotion || "中性"}：${record.summary || "记录"}`);
  const prefix = els.content.value.trim() ? "\n\n" : "";
  els.content.value += `${prefix}今日参考素材：\n${lines.join("\n")}\n`;
  els.content.focus();
  scheduleAutosave();
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    els.voiceBtn.disabled = true;
    els.voiceBtn.textContent = "语音不可用";
    return;
  }
  state.recognition = new SpeechRecognition();
  state.recognition.lang = "zh-CN";
  state.recognition.continuous = true;
  state.recognition.interimResults = true;
  let finalText = "";

  state.recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0].transcript;
      if (event.results[index].isFinal) finalText += transcript;
      else interim += transcript;
    }
    if (finalText) {
      const separator = els.content.value.trim() ? "\n" : "";
      els.content.value += `${separator}${finalText}`;
      finalText = "";
      scheduleAutosave();
    }
    els.voiceBtn.textContent = interim ? "正在听写" : "停止听写";
  };
  state.recognition.onend = () => {
    state.listening = false;
    els.voiceBtn.textContent = "语音转文字";
  };
}

function toggleSpeech() {
  if (!state.recognition) return;
  if (state.listening) {
    state.recognition.stop();
    return;
  }
  state.listening = true;
  els.voiceBtn.textContent = "停止听写";
  state.recognition.start();
}

function bindEvents() {
  [els.title, els.content, els.physicalWeather, els.moodWeather].forEach((el) => {
    el.addEventListener("input", scheduleAutosave);
    el.addEventListener("change", scheduleAutosave);
  });
  els.date.addEventListener("change", loadDiary);
  els.refreshContextBtn.addEventListener("click", loadContext);
  els.insertContextBtn.addEventListener("click", insertSelectedContext);
  els.saveBtn.addEventListener("click", async () => {
    try {
      await saveDiary("manual");
      await reflectDiary("manual");
    } catch (error) {}
  });
  els.reflectBtn.addEventListener("click", () => reflectDiary("manual"));
  els.voiceBtn.addEventListener("click", toggleSpeech);
}

function boot() {
  populateWeatherSelect(els.physicalWeather);
  populateWeatherSelect(els.moodWeather);
  els.date.value = todayISO();
  const code = participantCode();
  els.participant.textContent = code || "local";
  bindEvents();
  setupSpeechRecognition();
  loadDiary();
}

document.addEventListener("DOMContentLoaded", boot);
