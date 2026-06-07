# Changelog

## 2026-06-05

- Added and documented unified DeepSeek / `emotion_rec/llm_client.py` model wrapper.
- Added Body Sensation frontend integration and route aliases:
  - `/body`
  - `/body-sensation`
  - `/body_sensation`
- Added Diary formal journal workflow:
  - `/diary`
  - date-based editing
  - weather fields
  - autosave / manual save
  - AI reflection with local fallback
- Added Emotion Review workflow:
  - `/review`
  - date range overview
  - trend visualization
  - emotion color palette
  - daily emotion distribution donut chart
  - source detail panel
  - cached AI period report
- Added Records personal history workflow:
  - `/records`
  - `/history`
  - date and source filtering
  - expandable Journal / Diary / Body records
- Added admin / research aggregation APIs protected by `ADMIN_TOKEN`:
  - `/api/admin/review/overview`
  - `/api/admin/records`
- Updated README, deployment notes, and Body Sensation API documentation for the latest EmoBridge feature set.

## Earlier

- Added Journal realtime text / voice emotion recognition.
- Added Valence-Arousal mapping and emotion color output.
- Added dynamic typography emotion visualization.
- Added participant session, diary entry storage, usage events, and JSON / CSV export.
- Added Docker / Render deployment files and `/healthz` health check.
