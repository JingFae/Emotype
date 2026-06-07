from pathlib import Path

path = Path("emotion_rec/body_sensation.py")
text = path.read_text(encoding="utf-8")

old = '''    normalized = {
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "state_reading": str(state_reading or "").strip(),'''

new = '''    if isinstance(state_reading, list):
        state_reading = " ".join(str(item).strip() for item in state_reading if str(item).strip())

    normalized = {
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "state_reading": str(state_reading or "").strip(),'''

if old not in text:
    print("state_reading target not found or already patched")
else:
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("patched state_reading list normalization")
