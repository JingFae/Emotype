from pathlib import Path

path = Path("emotion_rec/static/body_sensation.html")
html = path.read_text(encoding="utf-8")

# 1. Add a robust helper that always prioritizes URL participant_code.
if "function getEffectiveParticipantCode()" not in html:
    marker = "async function loadRecentDiaries() {"
    helper = r'''
function getEffectiveParticipantCode() {
  const input = document.getElementById("participantCode");
  const params = new URLSearchParams(window.location.search);

  const urlCode =
    params.get("participant_code") ||
    params.get("participantCode") ||
    params.get("code") ||
    params.get("participant");

  if (urlCode && urlCode.trim()) {
    const clean = urlCode.trim();
    if (input && input.value !== clean) {
      input.value = clean;
    }
    try {
      localStorage.setItem("emotype_participant_code", clean);
      localStorage.setItem("participant_code", clean);
      localStorage.setItem("participantCode", clean);
    } catch (error) {}
    return clean;
  }

  if (input && input.value.trim()) {
    const clean = input.value.trim();
    try {
      localStorage.setItem("emotype_participant_code", clean);
      localStorage.setItem("participant_code", clean);
      localStorage.setItem("participantCode", clean);
    } catch (error) {}
    return clean;
  }

  try {
    return (
      localStorage.getItem("emotype_participant_code") ||
      localStorage.getItem("participant_code") ||
      localStorage.getItem("participantCode") ||
      "P1234"
    ).trim();
  } catch (error) {
    return "P1234";
  }
}

function syncParticipantCodeFromUrlNow() {
  const input = document.getElementById("participantCode");
  const code = getEffectiveParticipantCode();
  if (input && code) {
    input.value = code;
  }
  return code;
}

'''
    if marker not in html:
        raise SystemExit("Cannot find async function loadRecentDiaries()")
    html = html.replace(marker, helper + "\n" + marker, 1)

# 2. Force loadRecentDiaries to use URL/localStorage-aware code.
old = '''async function loadRecentDiaries() {
  const code = document.getElementById("participantCode").value.trim();
  rememberParticipantCode(code);
  const status = document.getElementById("diaryStatus");'''

new = '''async function loadRecentDiaries() {
  const code = getEffectiveParticipantCode();
  const status = document.getElementById("diaryStatus");'''

if old in html:
    html = html.replace(old, new, 1)
else:
    old2 = '''async function loadRecentDiaries() {
  const code = document.getElementById("participantCode").value.trim();
  const status = document.getElementById("diaryStatus");'''
    if old2 in html:
        html = html.replace(old2, new, 1)
    else:
        print("loadRecentDiaries code line not found; inspect manually")

# 3. Make ensureParticipantSession use the same effective code.
old = '''async function ensureParticipantSession() {
  const code = document.getElementById("participantCode").value.trim();
  if (!code) return false;'''

new = '''async function ensureParticipantSession() {
  const code = getEffectiveParticipantCode();
  if (!code) return false;'''

if old in html:
    html = html.replace(old, new, 1)

# 4. Make submitAdvice use the same code.
old = '''    participant_code: document.getElementById("participantCode").value.trim(),'''

new = '''    participant_code: getEffectiveParticipantCode(),'''

if old in html:
    html = html.replace(old, new, 1)

# 5. Ensure startup sync runs before auto-loading diaries.
if "syncParticipantCodeFromUrlNow();" not in html:
    html = html.replace(
        "renderButtons();\nrenderPairs();",
        "renderButtons();\nrenderPairs();\nsyncParticipantCodeFromUrlNow();",
        1
    )

path.write_text(html, encoding="utf-8")
print("patched body_sensation.html to prioritize URL participant_code")
