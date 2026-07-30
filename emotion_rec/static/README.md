# Static frontend module map

This directory is mounted unchanged at `/static`. Keeping the public paths flat
avoids breaking deployed HTML, cached links, and inline iframe references.

| Page/feature | HTML | JavaScript | CSS |
| --- | --- | --- | --- |
| Home journal and kinetic type | `index.html` | `app.js`, `vaMapper.js`, `auth.js` | `styles.css` |
| Essay/image workspace | `essay.html` | `app.js`, `vaMapper.js`, `auth.js`, inline upload/fusion code | `styles.css` |
| Formal diary | `diary.html` | `diary.js`, `auth.js`, inline image upload code | `styles.css`, `diary.css` |
| Body sensation | `body_sensation.html` | `body_sensation.js`, `auth.js` | `styles.css`, `body_sensation.css` |
| Emotion review | `review.html` | `review.js`, `auth.js` | `styles.css`, `review.css` |
| Records/history | `records.html` | `records.js`, `auth.js` | `styles.css`, `records.css` |
| Combined history review | `historyreview.html` | `records.js`, `auth.js`, inline review/export code | `styles.css`, `records.css` |
| Emo Echo | `emo_echo.html` | `emo_echo.js`, `auth.js` | `styles.css`, `emo_echo.css` |
| Login/register | `login.html` | `login.js`, `auth.js` | `styles.css`, `login.css` |
| Profile/admin | `profile.html` | `profile.js`, `auth.js` | `styles.css`, `profile.css` |
| Embedded intro/game | `game.html` | inline page code | inline styles; `game-*.mp4` |

Shared files:

- `auth.js`: token storage, authenticated fetch helpers, and nav state.
- `i18n.js`: language dictionary and DOM translation.
- `vaMapper.js`: browser runtime fallback for V-A mapping.
- `vaMapper.ts`: typed authoring/reference source; the browser loads the JS file.
- `styles.css`: shared brand, navigation, layout, and typography styles.
- `people.svg` and `people-body.svg`: body diagrams.
- `brand-lockup.png`: combined brand lockup image.
- `icon2-only.png`: compact brand icon used by page navigation.
- `name-text.png`: wordmark paired with the compact icon.
- `icon_chatbox.png`: Emo Echo assistant/avatar artwork.
- `people.svg` and `people-body.svg`: body diagrams used by journal/body UI.
- `game-bg.mp4` and `game-main.mp4`: embedded game background/foreground media.
- `video.mp4`: standalone presentation/background media retained as a public asset.
- `chatbox_guide.md`: implementation notes; not loaded by the app.
