const els = {
  startDate: document.getElementById("recordsStartDate"),
  endDate: document.getElementById("recordsEndDate"),
  source: document.getElementById("recordsSource"),
  loadBtn: document.getElementById("recordsLoadBtn"),
  total: document.getElementById("recordsTotal"),
  state: document.getElementById("recordsState"),
  journalCount: document.getElementById("recordsJournalCount"),
  diaryCount: document.getElementById("recordsDiaryCount"),
  bodyCount: document.getElementById("recordsBodyCount"),
  list: document.getElementById("recordsList"),
};

function todayISO() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function daysAgoISO(days) {
  const now = new Date();
  now.setDate(now.getDate() - days);
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function participantCode() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("participant_code") || params.get("participantCode") || params.get("code");
  if (fromUrl && fromUrl.trim()) return fromUrl.trim();
  try {
    const participant = JSON.parse(localStorage.getItem("emomirror.participant") || "null");
    if (participant?.participant_code) return participant.participant_code;
  } catch (error) {}
  for (const key of ["emotype_participant_code", "participant_code", "participantCode"]) {
    try {
      const value = localStorage.getItem(key);
      if (value && value.trim()) return value.trim();
    } catch (error) {}
  }
  return "local";
}

function applyUrlFilters() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("start_date")) els.startDate.value = params.get("start_date");
  if (params.get("end_date")) els.endDate.value = params.get("end_date");
  if (params.get("source")) els.source.value = params.get("source");
}

async function apiJson(url) {
  const response = await fetch(url);
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

function formatSigned(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function sourceLabel(source) {
  return {
    journal: "Journal 随手记",
    diary: "Diary 正式日记",
    body_sensation: "Body 身体感受",
    realtime_emotion: "实时情绪",
  }[source] || source || "记录";
}

function sourceClass(source) {
  return {
    journal: "is-journal",
    diary: "is-diary",
    body_sensation: "is-body",
  }[source] || "";
}

function queryString() {
  const params = new URLSearchParams({
    participant_code: participantCode(),
    start_date: els.startDate.value,
    end_date: els.endDate.value,
    source: els.source.value || "all",
  });
  return params.toString();
}

function setState(text) {
  els.state.textContent = text;
}

function renderSummary(data) {
  const counts = data.source_counts || {};
  els.total.textContent = String(data.total || 0);
  els.journalCount.textContent = String(counts.journal || 0);
  els.diaryCount.textContent = String(counts.diary || 0);
  els.bodyCount.textContent = String(counts.body_sensation || 0);
}

function textPreview(record) {
  return record.summary || record.content || "记录摘要";
}

function renderRecords(records = []) {
  els.list.textContent = "";
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "records-empty";
    empty.textContent = "这个范围内还没有符合条件的记录。";
    els.list.appendChild(empty);
    return;
  }

  records.forEach((record) => {
    const item = document.createElement("details");
    item.className = `record-item ${sourceClass(record.source)}`;

    const summary = document.createElement("summary");
    const color = document.createElement("span");
    color.className = "record-color";
    color.style.background = record.emotion_color || "#94A3B8";

    const main = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = record.primary_emotion || sourceLabel(record.source);
    const meta = document.createElement("small");
    meta.textContent = `${sourceLabel(record.source)} · ${record.time || record.date || ""} · V ${formatSigned(record.valence)} · A ${formatSigned(record.arousal)}`;
    const preview = document.createElement("p");
    preview.textContent = textPreview(record);
    main.append(title, meta, preview);
    summary.append(color, main);
    item.appendChild(summary);

    const detail = document.createElement("div");
    detail.className = "record-detail";
    appendDetailSection(detail, "内容摘要", record.content || record.summary || "-");
    if (record.source === "diary") {
      appendDetailSection(detail, "日记复盘摘要", record.reflection_summary || record.detail?.reflection_summary || "这篇日记还没有复盘摘要。");
    }
    if (record.source === "body_sensation") {
      const bodySummary = [
        ...(record.body_regions || []),
        ...(record.body_signals || []),
      ].filter(Boolean).join("、");
      appendDetailSection(detail, "身体部位 / 身体信号", bodySummary || "暂无身体信号摘要。");
    }
    if (Array.isArray(record.fine_emotions) && record.fine_emotions.length) {
      appendChipSection(detail, "细粒度情绪", record.fine_emotions);
    }
    if (Array.isArray(record.body_signals) && record.body_signals.length && record.source !== "body_sensation") {
      appendChipSection(detail, "身体信号", record.body_signals);
    }
    item.appendChild(detail);
    els.list.appendChild(item);
  });
}

function appendDetailSection(parent, label, text) {
  const section = document.createElement("section");
  section.className = "record-detail-section";
  const title = document.createElement("span");
  title.textContent = label;
  const p = document.createElement("p");
  p.textContent = text || "-";
  section.append(title, p);
  parent.appendChild(section);
}

function appendChipSection(parent, label, values) {
  const section = document.createElement("section");
  section.className = "record-detail-section";
  const title = document.createElement("span");
  title.textContent = label;
  const row = document.createElement("div");
  row.className = "record-chip-row";
  values.slice(0, 12).forEach((value) => {
    const chip = document.createElement("i");
    chip.textContent = value;
    row.appendChild(chip);
  });
  section.append(title, row);
  parent.appendChild(section);
}

async function loadRecords() {
  els.loadBtn.disabled = true;
  setState("载入中");
  try {
    const data = await apiJson(`/api/records?${queryString()}`);
    renderSummary(data);
    renderRecords(data.records || []);
    setState("已载入");
  } catch (error) {
    setState(`载入失败：${error.message}`);
  } finally {
    els.loadBtn.disabled = false;
  }
}

function bindEvents() {
  els.loadBtn.addEventListener("click", loadRecords);
  [els.startDate, els.endDate, els.source].forEach((input) => input.addEventListener("change", loadRecords));
}

function boot() {
  els.startDate.value = daysAgoISO(29);
  els.endDate.value = todayISO();
  applyUrlFilters();
  bindEvents();
  loadRecords();
}

document.addEventListener("DOMContentLoaded", boot);
