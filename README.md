# EmoBridge / Emotype

EmoBridge / Emotype 是一个情绪理解与可视化项目，用来把用户的文字、语音、身体感受和日记记录整理成可观察的情绪线索。当前核心能力包括：

- 实时文字 / 语音情绪识别
- 动态字体情绪可视化
- Journal 随手记
- Body 身体感受记录
- Diary 正式日记
- Emotion Review 阶段性情绪复盘
- Records 我的历史记录
- DeepSeek / `emotion_rec/llm_client.py` 统一模型调用封装

项目后端基于 FastAPI，前端位于 `emotion_rec/static/`，数据库逻辑位于 `emotion_rec/storage.py`。默认本地数据库是 SQLite，也可以通过 `DATABASE_URL` 切换到 PostgreSQL。

## 页面入口

| 路径 | 说明 |
| --- | --- |
| `/` | Journal / 实时情绪识别与动态字体可视化 |
| `/body` | 身体感受记录 |
| `/body-sensation` | 身体感受记录 |
| `/body_sensation` | 身体感受记录 |
| `/diary` | 正式日记 / Diary |
| `/review` | 情绪复盘 / Emotion Review |
| `/records` | 我的历史记录 |
| `/history` | 我的历史记录别名 |
| `/healthz` | 健康检查 |

## 核心功能

### Journal 随手记

Journal 是首页的实时情绪记录入口，适合碎片化输入和即时可视化。

- 支持文本随手记输入。
- 支持浏览器语音输入，并把识别文本用于情绪分析。
- 实时分析文本情绪线索。
- 展示 Valence-Arousal V-A 坐标。
- 生成情绪标签、候选情绪和情绪颜色。
- 通过动态字体把情绪映射到字体粗细、缩放、颜色、动画和局部视觉强调。
- 支持用户修正情绪标签、调整 V-A 坐标并保存记录。

主要接口：

- `POST /analyze-text`
- `POST /predict`
- `POST /diaries`
- `POST /usage-events`

### Body 身体感受

Body 页面用于记录身体部位和身体感受，并把身体信号与情绪线索放在一起看。

- 支持选择身体部位。
- 支持选择或补充身体感受，例如胸口闷、肩颈紧、疲惫等。
- 可以结合当前文本、最近记录和情绪线索生成温和建议。
- 保留安全 fallback，不做医疗诊断。
- 出现高风险红旗时优先提示寻求专业帮助。

主要页面：

- `/body`
- `/body-sensation`
- `/body_sensation`

主要接口：

- `POST /body-sensation/advice`

### Diary 正式日记

Diary 是独立的正式日记页面，适合一天结束后补写、整理和复盘。

- 支持按日期查看、补写和修改正式日记。
- 支持现实天气和心情天气。
- 支持自动保存和手动保存。
- 修改后可以重新复盘。
- 可以引用当天 Journal / Body 等上下文记录。
- AI 复盘输出包括事件总结、主情绪、细粒度情绪、身体信号、V-A 坐标、情绪颜色、可能触发点、可能需要、反思问题和小行动建议。
- 所有模型调用都走 `emotion_rec/llm_client.py`，无 key 或调用失败时使用本地 fallback。

主要接口：

- `GET /api/diary?date=YYYY-MM-DD&participant_code=local`
- `GET /api/diary/context?date=YYYY-MM-DD&participant_code=local`
- `PUT /api/diary/by-date/YYYY-MM-DD`
- `POST /api/diary/by-date/YYYY-MM-DD/reflect`

### Emotion Review 情绪复盘

Emotion Review 用于汇总一段时间内的 Journal / Diary / Body 数据，帮助用户观察情绪变化模式。

- 默认查看近 7 天。
- 展示情绪趋势。
- 展示情绪颜色色板。
- 展示主要情绪、细粒度情绪、触发因素和身体信号。
- 支持选择某一天，查看该日期情绪分布环形图。
- 展示当前时间范围内的 Journal / Diary / Body 来源明细。
- 支持 AI 阶段性复盘。
- 打开 `/review` 时只加载统计数据，不自动调用大模型。
- 只有用户点击“生成复盘 / 更新复盘”时才调用模型。
- 复盘结果会缓存到 `emotion_review_reports`，下次优先读取缓存。
- 复盘文案保持温和、非诊断式，避免把用户直接定义为某种病理状态。

主要接口：

- `GET /api/review/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=local`
- `POST /api/review/reflect`
- `GET /api/review/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=local`

### Records 我的历史记录

Records 页面用于当前用户查看自己的历史记录，不调用大模型，只读取已有数据。

- 默认展示当前 `participant_code` 的 Journal / Diary / Body 记录。
- 支持日期范围筛选。
- 支持来源筛选：全部、Journal、Diary、Body。
- 记录按时间倒序展示。
- 每条记录展示来源类型、日期时间、摘要、主情绪、V-A 坐标和情绪颜色。
- Diary 记录展示复盘摘要。
- Body 记录展示身体部位和身体信号摘要。
- 支持点击展开详情。

主要页面：

- `/records`
- `/history`

主要接口：

- `GET /api/records?participant_code=local&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&source=all`

### Admin / 研究端数据查看

普通用户接口只能查看自己的 `participant_code` 数据。查看所有用户数据必须使用管理端接口，并通过 `ADMIN_TOKEN` 校验。

管理端接口：

- `GET /api/admin/review/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=all`
- `GET /api/admin/records?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=all`
- `GET /admin/export.json`
- `GET /admin/export.csv`

管理端 token 可通过 query 参数或 `X-Admin-Token` 请求头传入。未设置或校验失败时接口会返回 401 / 403。不要把所有用户数据暴露给普通前端。

## 模型调用

所有生成式模型调用统一封装在：

```text
emotion_rec/llm_client.py
```

当前默认模型以代码为准：

```text
deepseek-v4-flash
```

主要环境变量：

| 变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API key。缺失时使用本地 fallback。 |
| `DEEPSEEK_MODEL` | 默认 LLM 模型，默认 `deepseek-v4-flash`。 |
| `DEEPSEEK_BASE_URL` | OpenAI-compatible base URL，默认 `https://api.deepseek.com`。 |
| `DEEPSEEK_TIMEOUT_SECONDS` | LLM 超时时间，默认 `30`。 |
| `LLM_API_KEY` | 兼容旧 alias。 |
| `LLM_MODEL` | 兼容旧 alias。 |
| `LLM_API_BASE_URL` | 兼容旧 alias。 |
| `LLM_ENABLED` | 是否启用 LLM 调用，默认启用。 |

图片上传分析（Gemini / Google AI Studio）环境变量：

| 变量 | 说明 |
| --- | --- |
| `GEMINI_API_KEY` | Google AI Studio key，用于 `/api/uploads` 的图片 VLM 分析。缺失时图片仅上传不分析（前端不显示分析结果）。 |
| `GOOGLE_API_KEY` | `GEMINI_API_KEY` 的兼容 alias。 |
| `GEMINI_MODEL` | Gemini 模型，默认 `gemini-2.5-flash`（如 AI Studio 显示的名称不同，请以此为准修改）。 |
| `GEMINI_FALLBACK_MODELS` | 主模型连续返回 503「高负载」等瞬时错误时，按序回退的模型，默认 `gemini-2.0-flash,gemini-flash-latest`。 |
| `GEMINI_TIMEOUT_SECONDS` | Gemini 调用超时，默认 `30`。 |
| `GEMINI_MAX_RETRIES` | 每个模型遇到瞬时错误的重试次数，默认 `1`。 |
| `GEMINI_ENABLED` | 是否启用图片分析，默认启用。 |

图片分析统一封装在 `emotion_rec/gemini_client.py`，通过官方 `google-genai` SDK 调用 Gemini；与 `llm_client.py` 一样，无 key 或调用失败时返回 `None`，上传接口仍正常返回。

功能专用环境变量：

| 变量 | 说明 |
| --- | --- |
| `TEXT_EMOTION_BACKEND` | 文本情绪后端选择。 |
| `BODY_ADVICE_LLM_ENABLED` | 身体感受建议是否启用 LLM。 |
| `BODY_LLM_MODEL` | 身体感受建议专用模型，留空继承默认模型。 |
| `DIARY_REFLECTION_LLM_MODEL` | Diary 复盘专用模型，留空继承默认模型。 |
| `REVIEW_REFLECTION_LLM_MODEL` | Review 阶段复盘专用模型，留空继承默认模型。 |

无 key 或调用失败时，文本情绪、身体建议、日记复盘和阶段复盘都会使用本地 fallback。业务代码中不要直接写 DeepSeek / OpenAI API 调用。

示例环境变量只使用占位符：

```bash
export DEEPSEEK_API_KEY=your_deepseek_api_key_here
export DEEPSEEK_MODEL=deepseek-v4-flash
export GEMINI_API_KEY=your_gemini_api_key_here
export ADMIN_TOKEN=your_admin_token_here
```

## 运行方式

进入正式运行目录：

```bash
cd /root/Emotype
```

前台启动：

```bash
python -m uvicorn emotion_rec.app:app --host 0.0.0.0 --port 8000
```

后台启动：

```bash
nohup /root/miniconda3/bin/python3 -m uvicorn emotion_rec.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  > /tmp/emotype.log 2>&1 &
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

页面检查：

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/body
curl -I http://127.0.0.1:8000/diary
curl -I http://127.0.0.1:8000/review
curl -I http://127.0.0.1:8000/records
```

## 测试命令

基础编译检查：

```bash
python -m compileall emotion_rec emotion_computing hmotiongpt-api-test
```

关键 API 示例：

```bash
curl "http://127.0.0.1:8000/api/diary?date=YYYY-MM-DD&participant_code=local"
```

```bash
curl -X PUT "http://127.0.0.1:8000/api/diary/by-date/YYYY-MM-DD" \
  -H "Content-Type: application/json" \
  -d '{
    "participant_code": "local",
    "title": "今天的标题",
    "content": "今天发生的事和我的感受。",
    "physical_weather": "sunny",
    "mood_weather": "cloudy",
    "is_draft": false
  }'
```

```bash
curl -X POST "http://127.0.0.1:8000/api/diary/by-date/YYYY-MM-DD/reflect" \
  -H "Content-Type: application/json" \
  -d '{"participant_code":"local"}'
```

```bash
curl "http://127.0.0.1:8000/api/review/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=local"
```

```bash
curl -X POST "http://127.0.0.1:8000/api/review/reflect" \
  -H "Content-Type: application/json" \
  -d '{"participant_code":"local","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}'
```

```bash
curl "http://127.0.0.1:8000/api/review/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=local"
```

```bash
curl "http://127.0.0.1:8000/api/records?participant_code=local&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&source=all"
```

管理端接口示例：

```bash
curl "http://127.0.0.1:8000/api/admin/review/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=all" \
  -H "X-Admin-Token: your_admin_token_here"
```

## 数据库 / 数据结构

数据库模型以 `emotion_rec/storage.py` 为准。

当前主要表：

| 表名 | 说明 |
| --- | --- |
| `participants` | 参与者 / 用户编号。 |
| `diary_entries` | Journal 随手记记录。 |
| `formal_diaries` | 正式日记、Diary 复盘结果和情绪分析字段。 |
| `emotion_review_reports` | Emotion Review 阶段性复盘报告缓存。 |
| `usage_events` | 身体感受、交互事件和其他使用日志。 |

默认数据库：

```text
emotion_rec/emomirror_data.sqlite3
```

设置 `DATABASE_URL` 后可以使用 PostgreSQL。旧 SQLite 文件会在启动时做轻量 schema 兼容补齐。

## 项目结构

```text
Emotype/
├── emotion_rec/
│   ├── app.py                         # FastAPI 应用、页面路由、主要 API
│   ├── body_sensation.py              # Body 身体感受建议
│   ├── llm_client.py                  # DeepSeek / LLM 统一封装
│   ├── gemini_client.py               # Gemini VLM 图片分析统一封装
│   ├── storage.py                     # SQLAlchemy 数据库模型与聚合查询
│   ├── text_emotion.py                # 文本情绪分析与 fallback
│   ├── va_mapper.py                   # V-A 坐标映射
│   ├── shared/
│   │   └── emotion_lexicon.json       # 情绪词典
│   └── static/
│       ├── index.html                 # Journal 首页
│       ├── body_sensation.html        # Body 页面
│       ├── diary.html                 # Diary 页面
│       ├── review.html                # Emotion Review 页面
│       ├── records.html               # Records 页面
│       ├── app.js
│       ├── body_sensation.js
│       ├── diary.js
│       ├── review.js
│       ├── records.js
│       └── styles.css
├── emotion_computing/                 # 音频情绪模型 demo / check
├── hmotiongpt-api-test/               # 上传测试服务
├── Wav2vec-2.0/                       # 本地 Wav2Vec2 模型文件
├── DEPLOYMENT.md
└── CHANGELOG.md
```

## 安全注意事项

- 不要提交 `.env`、证书、私钥、日志、缓存、本地数据库或虚拟环境。
- 不要写入真实 `DEEPSEEK_API_KEY`。
- 不要写入任何真实 `OPENAI_API_KEY`。
- 不要在文档或代码中写入任何真实平台 secret key。
- 文档示例统一使用占位符。
- 管理端数据聚合接口必须使用 `ADMIN_TOKEN`。
- 普通用户接口只返回自己的 `participant_code` 数据。

完成文档或配置变更后，应运行仓库约定的 key 扫描命令。若结果只包含 `os.getenv(...)`、`DEEPSEEK_API_KEY=...` 或文档占位符示例，可以接受。
