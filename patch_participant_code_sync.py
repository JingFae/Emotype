from pathlib import Path

# -----------------------------
# 1. Patch body_sensation.html
# -----------------------------
body_path = Path("emotion_rec/static/body_sensation.html")
html = body_path.read_text(encoding="utf-8")

if "const BODY_PARTICIPANT_STORAGE_KEY" not in html:
    marker = "let loadedDiaries = [];"

    helper = r'''
const BODY_PARTICIPANT_STORAGE_KEY = "emotype_participant_code";

function normalizeParticipantCode(value) {
  return String(value || "").trim();
}

function rememberParticipantCode(code) {
  code = normalizeParticipantCode(code);
  if (!code) return;
  try {
    localStorage.setItem(BODY_PARTICIPANT_STORAGE_KEY, code);
    localStorage.setItem("participant_code", code);
    localStorage.setItem("participantCode", code);
  } catch (error) {
    console.warn("failed to persist participant code", error);
  }
}

function readParticipantCodeFromUrlOrStorage(defaultCode) {
  const params = new URLSearchParams(window.location.search);
  const fromUrl =
    params.get("participant_code") ||
    params.get("participantCode") ||
    params.get("code") ||
    params.get("participant");

  if (normalizeParticipantCode(fromUrl)) {
    return normalizeParticipantCode(fromUrl);
  }

  const keys = [
    BODY_PARTICIPANT_STORAGE_KEY,
    "participant_code",
    "participantCode",
    "currentParticipantCode",
    "emomirror_participant_code",
    "emotype_participant_code"
  ];

  for (const key of keys) {
    try {
      const value = normalizeParticipantCode(localStorage.getItem(key));
      if (value) return value;
    } catch (error) {}
  }

  return normalizeParticipantCode(defaultCode || "P1234");
}

function initParticipantCodeSync() {
  const input = document.getElementById("participantCode");
  if (!input) return;

  const resolvedCode = readParticipantCodeFromUrlOrStorage(input.value);
  input.value = resolvedCode;
  rememberParticipantCode(resolvedCode);

  input.addEventListener("input", () => {
    rememberParticipantCode(input.value);
  });

  input.addEventListener("change", () => {
    rememberParticipantCode(input.value);
    loadRecentDiaries();
  });
}

'''

    if marker not in html:
        raise SystemExit("Cannot find 'let loadedDiaries = [];' in body_sensation.html")
    html = html.replace(marker, helper + "\n" + marker, 1)

# 在 loadRecentDiaries 里，读取 code 后立刻记住当前 code
old = '''  const code = document.getElementById("participantCode").value.trim();
  const status = document.getElementById("diaryStatus");'''

new = '''  const code = document.getElementById("participantCode").value.trim();
  rememberParticipantCode(code);
  const status = document.getElementById("diaryStatus");'''

if old in html and "rememberParticipantCode(code);" not in html[html.find(old):html.find(old)+250]:
    html = html.replace(old, new, 1)

# 在 submitAdvice 前也记住 code，避免用户改了 code 但没有重新加载日记
old = '''async function submitAdvice() {
  if (!pairs.length) {'''

new = '''async function submitAdvice() {
  const participantInput = document.getElementById("participantCode");
  if (participantInput) {
    rememberParticipantCode(participantInput.value);
  }

  if (!pairs.length) {'''

if old in html:
    html = html.replace(old, new, 1)

# 页面启动时先同步 code，再加载日记
old = '''renderButtons();
renderPairs();
loadRecentDiaries();'''

new = '''renderButtons();
renderPairs();
initParticipantCodeSync();
loadRecentDiaries();'''

if old in html:
    html = html.replace(old, new, 1)
elif "initParticipantCodeSync();" not in html:
    html = html.replace("loadRecentDiaries();", "initParticipantCodeSync();\nloadRecentDiaries();", 1)

body_path.write_text(html, encoding="utf-8")
print("patched body_sensation.html participant code sync")


# -----------------------------
# 2. Patch index.html
# -----------------------------
index_path = Path("emotion_rec/static/index.html")
index_html = index_path.read_text(encoding="utf-8")

if "function resolveParticipantCodeForBodySensation" not in index_html:
    script = r'''
<script>
(function () {
  const BODY_PARTICIPANT_STORAGE_KEY = "emotype_participant_code";

  function cleanCode(value) {
    return String(value || "").trim();
  }

  function looksLikeParticipantCode(value) {
    value = cleanCode(value);
    return /^[A-Za-z0-9_-]{1,64}$/.test(value);
  }

  function resolveParticipantCodeForBodySensation() {
    const explicitSelectors = [
      "#participantCode",
      "#participant-code",
      "#participant_code",
      "[name='participant_code']",
      "[name='participantCode']"
    ];

    for (const selector of explicitSelectors) {
      const node = document.querySelector(selector);
      if (node && looksLikeParticipantCode(node.value)) {
        return cleanCode(node.value);
      }
    }

    const storageKeys = [
      BODY_PARTICIPANT_STORAGE_KEY,
      "participant_code",
      "participantCode",
      "currentParticipantCode",
      "emomirror_participant_code",
      "emotype_participant_code"
    ];

    for (const key of storageKeys) {
      try {
        const value = localStorage.getItem(key);
        if (looksLikeParticipantCode(value)) {
          return cleanCode(value);
        }
      } catch (error) {}
    }

    // Fallback: scan visible small input values.
    const inputs = Array.from(document.querySelectorAll("input"));
    for (const input of inputs) {
      const value = cleanCode(input.value);
      if (looksLikeParticipantCode(value)) {
        return value;
      }
    }

    return "";
  }

  function attachBodySensationEntrySync() {
    const link = document.getElementById("body-sensation-entry");
    if (!link) return;

    link.addEventListener("click", function () {
      const code = resolveParticipantCodeForBodySensation();
      if (!code) return;

      try {
        localStorage.setItem(BODY_PARTICIPANT_STORAGE_KEY, code);
        localStorage.setItem("participant_code", code);
        localStorage.setItem("participantCode", code);
      } catch (error) {}

      link.href = "/body-sensation?participant_code=" + encodeURIComponent(code);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachBodySensationEntrySync);
  } else {
    attachBodySensationEntrySync();
  }
})();
</script>
'''
    if "</body>" not in index_html:
        raise SystemExit("Cannot find </body> in index.html")
    index_html = index_html.replace("</body>", script + "\n</body>", 1)

index_path.write_text(index_html, encoding="utf-8")
print("patched index.html body sensation entry code sync")
