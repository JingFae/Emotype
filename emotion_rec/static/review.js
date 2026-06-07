const els = {
  startDate: document.getElementById("reviewStartDate"),
  endDate: document.getElementById("reviewEndDate"),
  loadBtn: document.getElementById("loadReviewBtn"),
  reflectBtn: document.getElementById("reflectReviewBtn"),
  loadState: document.getElementById("reviewLoadState"),
  reportState: document.getElementById("reviewReportState"),
  totalCount: document.getElementById("reviewTotalCount"),
  periodLabel: document.getElementById("reviewPeriodLabel"),
  journalCount: document.getElementById("reviewJournalCount"),
  diaryCount: document.getElementById("reviewDiaryCount"),
  bodyCount: document.getElementById("reviewBodyCount"),
  canvas: document.getElementById("reviewTrendCanvas"),
  trendEmpty: document.getElementById("trendEmpty"),
  daySelect: document.getElementById("reviewDaySelect"),
  donut: document.getElementById("reviewDonut"),
  donutCenter: document.getElementById("reviewDonutCenter"),
  donutLegend: document.getElementById("reviewDonutLegend"),
  donutEmpty: document.getElementById("reviewDonutEmpty"),
  palette: document.getElementById("reviewColorPalette"),
  primaryEmotions: document.getElementById("reviewPrimaryEmotions"),
  fineEmotions: document.getElementById("reviewFineEmotions"),
  triggers: document.getElementById("reviewTriggers"),
  bodySignals: document.getElementById("reviewBodySignals"),
  sourceDetails: document.getElementById("reviewSourceDetails"),
  aiSummary: document.getElementById("aiPeriodSummary"),
  aiPattern: document.getElementById("aiPattern"),
  aiTriggers: document.getElementById("aiTriggers"),
  aiBodySignals: document.getElementById("aiBodySignals"),
  aiQuestions: document.getElementById("aiQuestions"),
  aiSmallSteps: document.getElementById("aiSmallSteps"),
  aiNonDiagnostic: document.getElementById("aiNonDiagnostic"),
};

const state = {
  stats: null,
  report: null,
  selectedDay: "",
  trendHits: [],
  resizeTimer: null,
};

function participantCode() {
  try {
    const participant = JSON.parse(localStorage.getItem("emomirror.participant") || "null");
    return participant?.participant_code || "local";
  } catch (error) {
    return "local";
  }
}

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

function dateSpanLabel(start, end) {
  const startDate = new Date(`${start}T00:00:00`);
  const endDate = new Date(`${end}T00:00:00`);
  const days = Math.round((endDate - startDate) / 86400000) + 1;
  if (!Number.isFinite(days) || days <= 0) return "自定义";
  return days === 7 ? "近 7 天" : `${days} 天`;
}

function queryString() {
  const params = new URLSearchParams({
    start_date: els.startDate.value,
    end_date: els.endDate.value,
  });
  const code = participantCode();
  params.set("participant_code", code);
  return params.toString();
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

function setLoadState(text) {
  els.loadState.textContent = text;
}

function setReportState(text) {
  els.reportState.textContent = text;
}

function formatSigned(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function sourceLabel(source) {
  return {
    journal: "随手记",
    diary: "正式日记",
    body_sensation: "身体感受",
    realtime_emotion: "实时情绪",
  }[source] || source || "记录";
}

function clearNode(node) {
  node.textContent = "";
}

function emptyText(node, text) {
  clearNode(node);
  const p = document.createElement("p");
  p.className = "review-empty-line";
  p.textContent = text;
  node.appendChild(p);
}

function renderSummary(stats) {
  const counts = stats?.source_counts || {};
  els.totalCount.textContent = String(stats?.total_records || 0);
  els.periodLabel.textContent = dateSpanLabel(stats?.start_date || els.startDate.value, stats?.end_date || els.endDate.value);
  els.journalCount.textContent = String(counts.journal || 0);
  els.diaryCount.textContent = String(counts.diary || 0);
  els.bodyCount.textContent = String(counts.body_sensation || 0);
}

function renderPalette(colors = []) {
  clearNode(els.palette);
  if (!colors.length) {
    emptyText(els.palette, "这段时间还没有情绪颜色记录。");
    return;
  }
  colors.forEach((item) => {
    const swatch = document.createElement("article");
    swatch.className = "review-color-item";
    const chip = document.createElement("span");
    chip.className = "review-color-chip";
    chip.style.background = item.color || "#94A3B8";
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.name || (item.labels || []).slice(0, 2).join("、") || item.color || "情绪颜色";
    const meta = document.createElement("small");
    meta.textContent = `${item.count || 0} 次${item.color ? ` · ${item.color}` : ""}`;
    body.append(title, meta);
    swatch.append(chip, body);
    els.palette.appendChild(swatch);
  });
}

function renderRankedList(node, items = []) {
  clearNode(node);
  if (!items.length) {
    emptyText(node, "暂无统计。");
    return;
  }
  const PALETTE = ["#F59E0B","#EF4444","#3B82F6","#10B981","#8B5CF6","#EC4899","#F97316","#06B6D4","#84CC16","#6366F1"];
  const max = Math.max(...items.map((item) => Number(item.count) || 0), 1);
  items.forEach((item, idx) => {
    const row = document.createElement("article");
    row.className = "review-rank-row";
    const head = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = item.label || "未命名";
    const count = document.createElement("span");
    count.textContent = `${item.count || 0} 次`;
    head.append(label, count);
    const bar = document.createElement("i");
    bar.style.width = `${Math.max(8, ((Number(item.count) || 0) / max) * 100)}%`;
    bar.style.background = item.color || PALETTE[idx % PALETTE.length];
    row.append(head, bar);
    node.appendChild(row);
  });
}

function renderFineEmotions(items = []) {
  clearNode(els.fineEmotions);
  if (!items.length) {
    emptyText(els.fineEmotions, "暂无细粒度情绪。");
    return;
  }
  items.slice(0, 18).forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "emotion-chip";
    chip.textContent = `${item.label || "未命名"} · ${item.count || 0}`;
    els.fineEmotions.appendChild(chip);
  });
}

function renderDetailedList(node, items = [], empty) {
  clearNode(node);
  if (!items.length) {
    emptyText(node, empty);
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "review-detail-row";
    const head = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.label || "线索";
    const count = document.createElement("span");
    count.textContent = `${item.count || 0} 次`;
    head.append(title, count);
    row.appendChild(head);
    const sourceLine = document.createElement("small");
    const sources = Object.entries(item.sources || {})
      .filter(([, value]) => value)
      .map(([key, value]) => `${sourceLabel(key)} ${value}`);
    sourceLine.textContent = sources.join(" · ") || "来自记录文本";
    row.appendChild(sourceLine);
    (item.samples || []).slice(0, 2).forEach((sample) => {
      const p = document.createElement("p");
      p.textContent = sample;
      row.appendChild(p);
    });
    node.appendChild(row);
  });
}

function renderListItems(node, items = [], fallback = "-") {
  clearNode(node);
  const list = Array.isArray(items) ? items : [];
  if (!list.length) {
    const li = document.createElement("li");
    li.textContent = fallback;
    node.appendChild(li);
    return;
  }
  list.slice(0, 6).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = typeof item === "string" ? item : (item?.note || item?.label || fallback);
    node.appendChild(li);
  });
}

function renderReport(reportLike) {
  const report = reportLike?.report_json || reportLike || null;
  state.report = report;
  if (!report || !Object.keys(report).length) {
    setReportState("未生成");
    els.reflectBtn.textContent = "生成复盘";
    els.aiSummary.textContent = "还没有生成这段时间的复盘";
    els.aiPattern.textContent = "打开页面只会加载统计数据；点击生成后会保存复盘，下次优先读取缓存。";
    renderListItems(els.aiTriggers, []);
    els.aiBodySignals.textContent = "-";
    renderListItems(els.aiQuestions, []);
    renderListItems(els.aiSmallSteps, []);
    els.aiNonDiagnostic.textContent = "这份复盘只是帮助整理线索，不用于诊断。";
    return;
  }

  setReportState("已缓存");
  els.reflectBtn.textContent = "更新复盘";
  els.aiSummary.textContent = report.period_summary || "阶段性复盘";
  els.aiPattern.textContent = report.emotional_pattern || report.color_story || "";
  renderListItems(els.aiTriggers, report.possible_triggers || []);
  els.aiBodySignals.textContent = report.body_signal_summary || "-";
  renderListItems(els.aiQuestions, report.reflection_questions || []);
  renderListItems(els.aiSmallSteps, report.small_steps || []);
  els.aiNonDiagnostic.textContent = report.non_diagnostic_note || "这份复盘只是帮助整理线索，不用于诊断。";
}

function renderStats(stats) {
  state.stats = stats || null;
  if (!state.selectedDay || !stats?.per_day_distribution?.[state.selectedDay]) {
    const days = stats?.days || [];
    const latestWithData = days.slice().reverse().find((day) => Number(day.count) > 0);
    state.selectedDay = latestWithData?.date || days[days.length - 1]?.date || els.endDate.value;
  }
  renderSummary(stats || {});
  renderDayOptions(stats || {});
  renderDayDistribution();
  renderSourceDetails(stats || {});
  renderPalette(stats?.colors || []);
  renderRankedList(els.primaryEmotions, stats?.primary_emotions || []);
  renderFineEmotions(stats?.fine_emotions || []);
  renderDetailedList(els.triggers, stats?.triggers || [], "这段时间还没有明显触发因素。");
  renderDetailedList(els.bodySignals, stats?.body_signals || [], "这段时间还没有明显身体信号。");
  drawTrend();
}

function renderDayOptions(stats) {
  clearNode(els.daySelect);
  (stats.days || []).forEach((day) => {
    const option = document.createElement("option");
    option.value = day.date;
    option.textContent = `${day.date}${day.count ? ` · ${day.count} 条` : ""}`;
    els.daySelect.appendChild(option);
  });
  els.daySelect.value = state.selectedDay || "";
}

function renderDayDistribution() {
  const distribution = state.stats?.per_day_distribution?.[state.selectedDay] || null;
  const items = distribution?.items || [];
  const total = items.reduce((sum, item) => sum + (Number(item.count) || 0), 0);
  els.donutCenter.textContent = String(distribution?.count || 0);
  els.donutLegend.textContent = "";

  if (!items.length || total <= 0) {
    els.donut.style.background = "conic-gradient(#E7E5E4 0deg 360deg)";
    els.donutEmpty.style.display = "block";
    return;
  }

  els.donutEmpty.style.display = "none";
  let cursor = 0;
  const stops = items.map((item) => {
    const start = cursor;
    const end = cursor + ((Number(item.count) || 0) / total) * 360;
    cursor = end;
    return `${item.emotion_color || "#94A3B8"} ${start.toFixed(2)}deg ${end.toFixed(2)}deg`;
  });
  els.donut.style.background = `conic-gradient(${stops.join(", ")})`;

  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "review-donut-row";
    const color = document.createElement("span");
    color.style.background = item.emotion_color || "#94A3B8";
    const body = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.label || "未命名";
    const sources = Object.entries(item.sources || {})
      .filter(([, value]) => value)
      .map(([source, count]) => `${sourceLabel(source)} ${count}`)
      .join(" · ");
    const meta = document.createElement("small");
    meta.textContent = `${item.count || 0} 次${sources ? ` · ${sources}` : ""}`;
    body.append(title, meta);
    row.append(color, body);
    els.donutLegend.appendChild(row);
  });
}

function renderSourceDetails(stats) {
  clearNode(els.sourceDetails);
  const records = stats.records || [];
  const groups = [
    { key: "journal", label: "Journal 随手记" },
    { key: "diary", label: "Diary 正式日记" },
    { key: "body_sensation", label: "Body 身体感受" },
  ];

  groups.forEach((group) => {
    const rows = records.filter((record) => record.source === group.key).slice(-6).reverse();
    const details = document.createElement("details");
    details.className = "review-source-group";
    if (rows.length) details.open = group.key === "journal";
    const summary = document.createElement("summary");
    summary.textContent = `${group.label} · ${rows.length}`;
    details.appendChild(summary);

    if (!rows.length) {
      const empty = document.createElement("p");
      empty.textContent = "这段时间暂无该来源记录。";
      details.appendChild(empty);
    } else {
      rows.forEach((record) => {
        const link = document.createElement("a");
        link.href = `/records?start_date=${encodeURIComponent(els.startDate.value)}&end_date=${encodeURIComponent(els.endDate.value)}&source=${encodeURIComponent(group.key)}`;
        link.className = "review-source-record";
        const title = document.createElement("strong");
        title.textContent = record.primary_emotion || sourceLabel(record.source);
        const meta = document.createElement("span");
        meta.textContent = `${record.date || ""} · V ${formatSigned(record.valence)} · A ${formatSigned(record.arousal)}`;
        const text = document.createElement("p");
        text.textContent = record.summary || "记录摘要";
        link.append(title, meta, text);
        details.appendChild(link);
      });
    }
    els.sourceDetails.appendChild(details);
  });
}

function pointValue(point, key) {
  const value = Number(point?.[key]);
  if (!Number.isFinite(value)) return null;
  return Math.max(-1, Math.min(1, value));
}

function drawLine(ctx, points, key, color, chart) {
  const usable = points
    .map((point, index) => ({ point, index, value: pointValue(point, key) }))
    .filter((item) => item.value !== null);
  if (usable.length < 2) return;
  ctx.beginPath();
  usable.forEach((item, drawIndex) => {
    const x = chart.left + (item.index / Math.max(points.length - 1, 1)) * chart.width;
    const y = chart.top + ((1 - item.value) / 2) * chart.height;
    if (drawIndex === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.4;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();
}

function drawTrend() {
  const canvas = els.canvas;
  const points = state.stats?.trend_points || [];
  state.trendHits = [];
  els.trendEmpty.style.display = points.length ? "none" : "grid";
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, rect.width || canvas.parentElement.clientWidth || 640);
  const height = Math.max(260, rect.height || 320);
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const chart = { left: 46, top: 26, width: width - 72, height: height - 70 };
  ctx.fillStyle = "rgba(255,255,255,0.78)";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(120,113,108,0.22)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = chart.top + (i / 4) * chart.height;
    ctx.beginPath();
    ctx.moveTo(chart.left, y);
    ctx.lineTo(chart.left + chart.width, y);
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.moveTo(chart.left, chart.top + chart.height / 2);
  ctx.lineTo(chart.left + chart.width, chart.top + chart.height / 2);
  ctx.strokeStyle = "rgba(245,158,11,0.42)";
  ctx.stroke();

  ctx.fillStyle = "#78716C";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText("+1", 14, chart.top + 4);
  ctx.fillText("0", 22, chart.top + chart.height / 2 + 4);
  ctx.fillText("-1", 16, chart.top + chart.height + 4);
  ctx.fillText("Valence", chart.left, height - 20);
  ctx.fillText("Arousal", chart.left + 86, height - 20);

  if (!points.length) return;
  drawLine(ctx, points, "valence", "#D97706", chart);
  drawLine(ctx, points, "arousal", "#2563EB", chart);

  points.forEach((point, index) => {
    const value = pointValue(point, "valence");
    if (value === null) return;
    const x = chart.left + (index / Math.max(points.length - 1, 1)) * chart.width;
    const y = chart.top + ((1 - value) / 2) * chart.height;
    state.trendHits.push({ x, y, date: point.date });
    ctx.beginPath();
    ctx.fillStyle = point.emotion_color || "#94A3B8";
    ctx.arc(x, y, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });

  ctx.fillStyle = "#D97706";
  ctx.fillRect(chart.left + 52, height - 28, 24, 3);
  ctx.fillStyle = "#2563EB";
  ctx.fillRect(chart.left + 138, height - 28, 24, 3);
}

async function loadReport() {
  try {
    const data = await apiJson(`/api/review/report?${queryString()}`);
    renderReport(data.report);
  } catch (error) {
    setReportState("缓存读取失败");
    renderReport(null);
  }
}

async function loadOverview() {
  setLoadState("载入中");
  els.loadBtn.disabled = true;
  try {
    const data = await apiJson(`/api/review/overview?${queryString()}`);
    renderStats(data.stats || {});
    setLoadState("已载入");
    await loadReport();
  } catch (error) {
    setLoadState(`载入失败：${error.message}`);
  } finally {
    els.loadBtn.disabled = false;
  }
}

async function reflectReview() {
  setReportState("生成中");
  els.reflectBtn.disabled = true;
  els.loadBtn.disabled = true;
  try {
    const data = await apiJson("/api/review/reflect", {
      method: "POST",
      body: JSON.stringify({
        participant_code: participantCode() || null,
        start_date: els.startDate.value,
        end_date: els.endDate.value,
      }),
    });
    renderStats(data.stats || state.stats || {});
    renderReport(data.report_json || data.report);
    setReportState(data.llm_used ? "已生成" : "已生成，本地兜底");
  } catch (error) {
    setReportState(`生成失败：${error.message}`);
  } finally {
    els.reflectBtn.disabled = false;
    els.loadBtn.disabled = false;
  }
}

function bindEvents() {
  els.loadBtn.addEventListener("click", loadOverview);
  els.reflectBtn.addEventListener("click", reflectReview);
  els.daySelect.addEventListener("change", () => {
    state.selectedDay = els.daySelect.value;
    renderDayDistribution();
  });
  els.canvas.addEventListener("click", (event) => {
    const rect = els.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = state.trendHits
      .map((item) => ({ ...item, distance: Math.hypot(item.x - x, item.y - y) }))
      .filter((item) => item.date && item.distance <= 16)
      .sort((left, right) => left.distance - right.distance)[0];
    if (!hit) return;
    state.selectedDay = hit.date;
    els.daySelect.value = hit.date;
    renderDayDistribution();
  });
  [els.startDate, els.endDate].forEach((input) => {
    input.addEventListener("change", () => {
      setReportState("待读取");
      loadOverview();
    });
  });
  window.addEventListener("resize", () => {
    clearTimeout(state.resizeTimer);
    state.resizeTimer = setTimeout(drawTrend, 140);
  });
}

function boot() {
  els.startDate.value = daysAgoISO(6);
  els.endDate.value = todayISO();
  bindEvents();
  loadOverview();
}

document.addEventListener("DOMContentLoaded", boot);

window.addEventListener("message", function (e) {
  if (e.data && e.data.type === "emb-refresh") loadOverview();
});
