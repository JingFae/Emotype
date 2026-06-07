from pathlib import Path

path = Path("emotion_rec/static/body_sensation.html")
html = path.read_text(encoding="utf-8")

if "async function ensureParticipantSession" not in html:
    marker = "async function loadRecentDiaries() {"
    helper = r'''
async function ensureParticipantSession() {
  const code = document.getElementById("participantCode").value.trim();
  if (!code) return false;

  try {
    await fetch("/participants/session", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        participant_code: code,
        consent_version: "research-v1"
      })
    });
    return true;
  } catch (error) {
    console.warn("participant session init failed", error);
    return false;
  }
}

'''
    if marker not in html:
        raise SystemExit("Cannot find loadRecentDiaries function")
    html = html.replace(marker, helper + "\n" + marker, 1)

old = '''  if (!code) {
    status.textContent = "请先填写 participant_code";
    return;
  }

  status.textContent = "Loading...";'''

new = '''  if (!code) {
    status.textContent = "请先填写 participant_code";
    return;
  }

  await ensureParticipantSession();

  status.textContent = "Loading...";'''

if old in html:
    html = html.replace(old, new, 1)

old2 = '''    const response = await fetch(`/participants/${encodeURIComponent(code)}/diaries`);
    const data = await response.json();

    loadedDiaries = Array.isArray(data)
      ? data
      : (data.diary_entries || data.diaries || data.entries || data.items || []);'''

new2 = '''    const response = await fetch(`/participants/${encodeURIComponent(code)}/diaries`);
    const data = await response.json();

    if (!response.ok) {
      loadedDiaries = [];
      status.textContent = `加载失败：${data.message || data.detail || response.status}`;
      tabs.innerHTML = '<span class="hint">当前编号还没有可读取的日记。请先在情绪日记页保存几条记录，或确认 participant_code 是否一致。</span>';
      return;
    }

    loadedDiaries = Array.isArray(data)
      ? data
      : (data.diary_entries || data.diaries || data.entries || data.items || []);'''

if old2 in html:
    html = html.replace(old2, new2, 1)

path.write_text(html, encoding="utf-8")
print("patched participant session init and diary loading error handling")
