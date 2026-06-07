# EmoBridge

> 面向情感可达性与自我反思场景的多模态情绪理解系统：将文字、语音、图片与身体感受转换为可解释的 V-A 情绪坐标、动态字体反馈和连续的日记复盘。

本文档对应 `v2-new` 分支。项目名称已统一为 **EmoBridge**；代码中仍保留少量 `EmoMirror`、`Emotype` 等历史标识和本地存储键，以维持现有数据与前端兼容。

## 项目概述

普通的 speech-to-text 主要回答“用户说了什么”，单一 emotion recognition 模型主要回答“当前情绪可能是什么”，传统 emotion diary 则侧重事后记录。EmoBridge 将这些环节连接为一个可交互的情绪表达闭环：

1. 接收文字、浏览器语音、上传音频、图片和身体感受；
2. 分析显性与隐性情绪、语音 VAD、音高与能量等线索；
3. 将结果映射到统一的 Valence-Arousal 空间、情绪标签和颜色；
4. 用字符级 kinetic typography、V-A 平面和多模态对照提供即时反馈；
5. 将用户确认后的结果保存为随手记、正式日记、身体感受或对话记录；
6. 通过阶段性统计、AI 复盘和 Emo 回响支持后续回顾与表达。

因此，EmoBridge 的定位不是医学诊断工具，也不是单一模型 demo，而是一个可本地运行和容器部署的 **HCI / 情感计算研究原型与情感可达性辅助系统**。它尤其关注难以准确辨认、组织或表达自身情绪的用户，但当前仓库尚未包含针对特定临床人群的有效性验证。

## 核心功能

- **情绪感知随手记**：`emotion_rec/static/index.html` 与 `emotion_rec/static/app.js` 支持文字输入、浏览器 Web Speech API 听写和 `MediaRecorder → /api/transcribe` 回退。输入会被解析为分段 V-A、情绪候选和置信度，而不仅是保存原文。
- **动态字体情绪镜像**：`POST /analyze-text` 和 `POST /predict` 返回字符索引到字体样式的 `llm_design`。前端据此改变字重、缩放、颜色、动画和局部 emoji，使情绪线索成为可感知的视觉反馈。
- **可修正的人机协同标注**：用户可以选择候选情绪、输入自定义标签或拖动 V-A 坐标。系统同时保留原始判断与最终修正值，便于研究用户校准行为。
- **文本、语音和声学分析**：文本由 `text_emotion.py` 处理；上传音频由本地 Wav2Vec2 回归模型输出 arousal、dominance、valence，并由 `librosa` 提取 pitch 与 energy。
- **图片情绪理解与融合**：`/essay` 支持图片预览；`POST /api/uploads` 使用 Gemini 分析可见线索、人物表达、画面诱发情绪和 V-A，`POST /api/analyze-combined` 再以文字为主融合图文结果。
- **正式日记与 AI 复盘**：`/diary` 支持按日期编辑、自动保存、天气隐喻、语音输入和图片分析引用。用户主动触发复盘后，系统生成事件摘要、主/次情绪、身体信号、触发点、需要、反思问题和小行动建议。
- **身体感受整理**：`/body-sensation` 将身体部位、症状、严重程度、持续时间、当前文本和近期日记放在一起分析。红旗规则优先于 LLM，输出明确声明不构成医疗诊断。
- **历史回顾与数据可视化**：`/historyreview`、`/review` 和 `/records` 提供情绪频率、V-A 历史、日期范围统计、来源筛选、缓存复盘与 JSON / CSV 导出。
- **Emo 回响**：`/emo-echo` 提供非诊断式情感陪伴对话，可引用最近 15 天的正式日记、随手记和身体感受作为上下文，并保存会话与消息。
- **账号与研究管理**：`/login`、`/profile` 提供注册、JWT 登录、显示名和密码修改。首个注册用户自动成为管理员，可查看用户列表和研究记录。
- **离线降级路径**：文本分析、V-A 映射、动态字体、身体建议和日记复盘均保留本地规则或固定 fallback；外部模型不可用时，核心记录流程仍可工作。

## 页面入口

| 路径 | 页面与职责 |
| --- | --- |
| `/` | 首页、情绪随手记、实时动态字体、身体感受入口和本地数据概览 |
| `/essay` | 情绪随笔工作区；组合随手记、正式日记 iframe、图片分析和图文情绪对照 |
| `/body`、`/body-sensation`、`/body_sensation` | 身体部位与感受记录、低风险建议和安全提示 |
| `/diary` | 按日期管理正式日记并主动生成复盘 |
| `/review` | 日期范围情绪统计与阶段性 AI 复盘 |
| `/records`、`/history` | 已保存 Journal / Diary / Body 记录列表 |
| `/historyreview` | 将情绪回顾、历史图表、记录列表和数据导出组合在同一页面 |
| `/emo-echo` | 带近期记录上下文的情感陪伴对话 |
| `/login` | 登录与注册 |
| `/profile` | 账号设置、个人数据快捷入口和管理员用户管理 |
| `/healthz` | 服务、设备、本地语音模型和 LLM 配置状态 |

## 系统技术架构

```text
用户输入
├── 文字 / 浏览器语音 / 上传音频
├── 图片
└── 身体感受 / 日记 / 对话
        ↓
emotion_rec/static/
原生 HTML + CSS + JavaScript
        ↓ HTTP / JSON / multipart
emotion_rec/app.py
FastAPI 页面路由、鉴权、业务编排与 API
        ↓
├── text_emotion.py
│   DeepSeek → regression head → Chinese-Emotion-Small → rules
├── Wav2vec-2.0/ + librosa + pydub
│   speech VAD、pitch、energy
├── gemini_client.py
│   图片视觉线索与情绪分析
├── va_mapper.py + shared/emotion_lexicon.json
│   V-A 标准化、标签、颜色、候选和分段聚合
├── llm_client.py
│   动态字体、Diary / Review、Body、Emo 回响
└── storage.py
    SQLAlchemy + SQLite / PostgreSQL
        ↓
字符级字体反馈、V-A 图、情绪候选、复盘、历史记录与导出
```

### Frontend / UI layer

- **技术**：原生 HTML、CSS、JavaScript；不需要 Node.js 构建步骤。
- **输入**：键盘文本、麦克风、音频录制、图片、本地交互和账号操作。
- **输出**：动态字体、情绪颜色、V-A 坐标、图表、日记、建议和对话。
- **关键文件**：`emotion_rec/static/index.html`、`app.js`、`essay.html`、`diary.js`、`review.js`、`records.js`、`emo_echo.js`、`auth.js`、`i18n.js`。
- **浏览器 fallback**：`vaMapper.js` 复用 `/shared/emotion_lexicon.json`；后端暂时不可用时，前端仍可用确定性规则产生本地情绪镜像。

### Backend API layer

- **技术**：FastAPI、Pydantic、SQLAlchemy。
- **职责**：静态页面服务、JWT 鉴权、参与者隔离、模型调度、数据读写、复盘聚合和导出。
- **关键文件**：`emotion_rec/app.py`。
- **身份解析**：登录普通用户始终映射到自己的 `username / participant_code`；登录管理员可指定其他参与者；未登录请求仍保留兼容旧版的 `participant_code` 模式。

### Emotion recognition / model inference layer

- **语音情绪**：本地 `Wav2vec-2.0/` 由 `EmotionModel` 加载，mean pooling 后接回归头，输出顺序为 arousal、dominance、valence。
- **文本情绪**：`text_emotion.py` 输出每个片段的 valence、arousal、confidence、explicit_label、implicit_label、evidence 和 source。
- **映射层**：`va_mapper.py` 不执行模型推理，只将已有 V-A 映射为象限、标签、颜色、候选和整体摘要。
- **图片情绪**：`gemini_client.py` 通过 `google-genai` 分析视觉证据，并区分 expressed_emotion 与 evoked_emotion。

### LLM generation layer

`emotion_rec/llm_client.py` 使用 OpenAI-compatible SDK 连接 DeepSeek。所有调用都有关闭开关、超时和本地 fallback，主要用于：

- 文本语义情绪分析；
- 字符级 kinetic typography 设计；
- Diary 单日复盘；
- Emotion Review 阶段复盘；
- Body 身体感受建议；
- Emo 回响对话；
- 图文情绪融合的语义判断。

### Database / persistence layer

`emotion_rec/storage.py` 使用 SQLAlchemy。默认数据库为：

```text
emotion_rec/emomirror_data.sqlite3
```

设置 `DATABASE_URL` 后可使用 PostgreSQL。应用启动时执行 `Base.metadata.create_all(...)`，并为旧 SQLite 文件补充缺失字段，不需要独立 migration 命令。

### Deployment layer

- `Dockerfile`：Python 3.11、CPU PyTorch、`ffmpeg`、`libsndfile` 和 Web 依赖。
- `render.yaml`：Render Docker Web Service、`/healthz` 健康检查和主要环境变量。
- `emotion_rec/start.sh`：从 `emotion_rec/` 目录启动 `uvicorn app:app`。

## 端到端技术 Pipeline

### 1. 文字或语音随手记

1. 用户在 `/` 或 `/essay` 输入文字。
2. 浏览器优先使用 Web Speech API 转写语音；不支持时录制 WebM 并调用 `POST /api/transcribe`，由 `openai/whisper-tiny` 转写。
3. 前端先用 `vaMapper.js` 和本地规则立即渲染低延迟预览，随后以 420 ms debounce 调用 `POST /analyze-text`。
4. `text_emotion.py` 分段分析显性/隐性情绪；`va_mapper.py` 将片段聚合为 overall V-A、情绪标签、颜色和候选。
5. typography pipeline 先检查演示触发规则，再尝试 DeepSeek，失败时生成确定性的字符级样式。
6. 用户可以修正标签或拖动 V-A 坐标。
7. `POST /diaries` 保存原始判断、最终判断、候选、text_emotion 和 va_mapping；浏览器同时保留最近记录的 localStorage 副本。

### 2. 上传音频情绪分析

1. `POST /predict` 接收音频文件和可选 transcript text。
2. `pydub / ffmpeg` 将输入转为 mono 16 kHz WAV，`librosa` 读取波形。
3. 本地 Wav2Vec2 回归模型输出原始 A-D-V；`normalize_vad(...)` 根据 `VAD_SOURCE_RANGE` 标准化到 `[-1, 1]`。
4. `librosa.pyin` 与 RMS 提取 pitch 和 energy。
5. 如果同时提供 text，语音 V-A 会应用到文本分段，并生成字符索引 typography map。
6. 临时音频文件在请求结束后删除；`return_embeddings=true` 时额外返回 pooled embedding。

### 3. 图片与图文融合

1. `/essay` 将图片发送到 `POST /api/uploads`，图片本身不写入数据库或文件目录。
2. 配置 `GEMINI_API_KEY` 时，`gemini_client.py` 将图片发送给 Gemini，返回 visual_evidence、候选情绪、核验说明、人物表达、画面诱发情绪、V-A 和颜色。
3. 文字存在时，前端调用 `POST /api/analyze-combined`。
4. DeepSeek 可根据图文一致性进行融合；不可用时使用 70% text + 30% image 的 V-A 加权 fallback。
5. Diary 复盘可接收前端传入的 `image_analyses`，但当前不持久化原始图片。

### 4. 日记、身体感受与阶段复盘

1. `PUT /api/diary/by-date/{diary_date}` 保存正式日记草稿，不自动调用 LLM。
2. 用户主动调用 `/reflect` 后，系统结合文本情绪与同日 Journal / Body 上下文生成复盘并写回 `formal_diaries`。
3. Body 流程先执行红旗规则，再生成低风险建议；高风险时跳过 LLM。
4. `/api/review/overview` 聚合指定日期范围的来源、情绪、颜色、触发线索与身体信号。
5. `/api/review/reflect` 在用户主动请求时生成阶段报告，并缓存到 `emotion_review_reports`。
6. `/records` 和 `/historyreview` 只读取已保存数据，不在页面打开时自动调用模型。

## 模型与 AI 组件

| 组件 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| 本地 Wav2Vec2 regression | mono 16 kHz audio | arousal、dominance、valence、可选 embedding | 模型文件位于 `Wav2vec-2.0/`；`config.json` 声明三维 regression |
| `librosa` acoustic features | 临时 WAV | `pitch_raw`、`pitch_norm`、`energy_raw`、`energy_norm` | 为 typography 和结果解释提供声学强度线索 |
| DeepSeek text emotion | 分段文字 | V-A、置信度、显性/隐性标签、证据 | `TEXT_EMOTION_BACKEND=deepseek` 为默认路径 |
| Text regression head | multilingual sentence embedding | V-A 与 confidence | 仅在 `TEXT_EMOTION_HEAD_PATH` 存在训练权重时使用 |
| `Johnson8187/Chinese-Emotion-Small` | 中文/口语文本 | 显性情绪分类 | 与否定、身体化、关系、羞耻、压力等规则融合 |
| Deterministic rules | 文本片段 | 隐性标签、V-A、证据 | 无网络、无 key 或模型失败时的稳定 fallback |
| Gemini VLM | 图片 bytes + context | 视觉证据、图片情绪、V-A、颜色 | 通过 `google-genai`；仅在配置 key 时启用 |
| DeepSeek generation | 情绪上下文、日记、统计或对话 | typography、复盘、建议、回复 | 统一经 `llm_client.py` 调用 |
| `emotion_lexicon.json` | V-A 坐标 | 近邻标签、候选、象限和颜色 | 后端与浏览器共享的 80 标签词典 |

当前仓库提供了 Wav2Vec2 模型配置与权重加载接口，但没有完整公开训练数据、训练过程、评估协议或准确率。`text_emotion_head.pt` 也不是当前仓库中的必备文件；没有训练好的 regression head 时，系统会使用分类器与规则。

## 数据库与数据流

| 数据表 | 内容 |
| --- | --- |
| `participants` | `participant_code`、consent version、创建与最后访问时间 |
| `users` | 用户名、密码哈希、显示名、角色、激活状态和 participant 关联 |
| `user_settings` | 语言、主题和扩展偏好 |
| `diary_entries` | 随手记原文、转写、原始/最终 V-A、标签、候选和分析 JSON |
| `formal_diaries` | 按日期的正式日记、天气、复盘、情绪与身体信号 |
| `usage_events` | session、身体感受、标签修正、V-A 调整等研究交互事件 |
| `emotion_review_reports` | 日期范围统计快照和阶段复盘缓存 |
| `echo_sessions` | Emo 回响会话标识和活跃时间 |
| `echo_messages` | 用户与 assistant 的对话消息 |

主要数据流如下：

```text
Frontend localStorage
   ↕ 低延迟缓存 / 未登录兼容
FastAPI API
   ↕ participant_code 或 JWT user
SQLAlchemy Session
   ↕
SQLite（默认）或 PostgreSQL
   ↓
Records / Review / Export / Emo 回响上下文
```

隐私与安全相关实现：

- 密码优先使用 `passlib[bcrypt]` 哈希；JWT 使用 `HS256`，有效期 24 小时。
- 登录普通用户的 participant scope 会被强制绑定到自己的 username。
- `/admin/export.*` 由 `ADMIN_TOKEN` 保护；用户管理 API 需要 admin JWT。
- 音频与转写仅使用临时文件，并在请求结束后删除。
- `/api/uploads` 不保存图片，但启用 Gemini 后会将图片发送给 Google AI Studio。
- `.gitignore` 排除 `.env`、数据库、证书、私钥、日志和虚拟环境。

## API 接口

### 分析与生成

| Endpoint | Method | 功能 | 输入 | 输出 |
| --- | --- | --- | --- | --- |
| `/healthz` | GET | 服务健康检查 | 无 | device、model_loaded、llm_configured、llm_model |
| `/analyze-text` | POST | 文本情绪与 typography | JSON: text、intensity | emotion、vad、acoustics、text_emotion、va_mapping、llm_design |
| `/predict` | POST | 音频 VAD、声学特征与 typography | multipart: file、text；query: return_embeddings | vad、vad_normalized、acoustics、va_mapping、llm_design、可选 embeddings |
| `/api/transcribe` | POST | 录音转写 | multipart: file | text |
| `/api/uploads` | POST | Gemini 图片情绪分析 | multipart: file、context | analyzed、analysis |
| `/api/analyze-combined` | POST | 图文情绪融合 | JSON: text、image_analysis | combined_emotion |
| `/body-sensation/advice` | POST | 身体感受、安全规则和建议 | JSON: journal_text、selected_regions、symptoms、free_text 等 | emotion_context、possible_links、advice、safety |
| `/api/emo-echo/sessions` | GET | 获取 Emo 回响历史会话 | participant_code 或 JWT | sessions |
| `/api/emo-echo/chat` | POST | 情感陪伴对话 | message、session_id、history、participant_code | reply、session_id |

### 账号与管理员

| Endpoint | Method | 功能 | 输入 | 输出 |
| --- | --- | --- | --- | --- |
| `/api/auth/register` | POST | 注册；首个用户成为 admin | username、password、display_name | access_token、user |
| `/api/auth/login` | POST | 登录 | username、password | access_token、user |
| `/api/auth/me` | GET | 获取当前用户与设置 | Bearer token | user、settings |
| `/api/auth/me` | PUT | 修改显示名 | Bearer token、display_name | user |
| `/api/auth/me/password` | PUT | 修改密码 | current_password、new_password | message、user |
| `/api/auth/me/settings` | GET | 获取用户设置 | Bearer token | settings |
| `/api/auth/me/settings` | PUT | 修改 language / theme | Bearer token、JSON | settings |
| `/api/admin/users` | GET | 管理员获取用户列表 | admin Bearer token | users |
| `/api/admin/users/{username}` | GET | 管理员获取用户详情 | admin Bearer token | user、settings |

### 随手记、正式日记与导出

| Endpoint | Method | 功能 | 输入 | 输出 |
| --- | --- | --- | --- | --- |
| `/participants/session` | POST | 创建/刷新参与者 session | participant_code、consent_version | participant |
| `/participants/{participant_code}/diaries` | GET | 获取随手记 | path、可选 JWT | diary_entries |
| `/participants/{participant_code}/all-data` | DELETE | 删除部分参与者数据 | path、可选 JWT | 删除计数 |
| `/diaries` | POST | 保存随手记及修正结果 | DiaryEntryRequest | diary_entry |
| `/usage-events` | POST | 保存研究交互事件 | participant_code、event_type、metadata_json | usage_event |
| `/participants/{participant_code}/export.json` | GET | 导出个人数据 | path、可选 JWT | JSON bundle |
| `/participants/{participant_code}/export.csv` | GET | 导出个人数据 | path、可选 JWT | CSV |
| `/admin/export.json` | GET | 导出全部参与者数据 | `admin_token` 或 `X-Admin-Token` | JSON bundle |
| `/admin/export.csv` | GET | 导出全部参与者数据 | `admin_token` 或 `X-Admin-Token` | CSV |
| `/api/diary` | GET | 读取指定日期正式日记 | date、participant_code 或 JWT | diary |
| `/api/diary/context` | GET | 读取同日 Journal / Body 上下文 | date、participant_code 或 JWT | records |
| `/api/diary/by-date/{diary_date}` | PUT | 新建或更新正式日记 | FormalDiaryUpsertRequest | diary、save_type |
| `/api/diary/by-date/{diary_date}/reflect` | POST | 主动生成并保存单日复盘 | participant_code、image_analyses | reflection、diary、上下文 |

### 回顾与记录

| Endpoint | Method | 功能 | 输入 | 输出 |
| --- | --- | --- | --- | --- |
| `/api/review/overview` | GET | 聚合日期范围统计 | start_date、end_date、participant_code | stats |
| `/api/review/report` | GET | 读取缓存阶段报告 | start_date、end_date、participant_code | report |
| `/api/review/reflect` | POST | 生成并缓存阶段复盘 | start_date、end_date、participant_code | stats、report_json |
| `/api/records` | GET | 按日期与来源读取记录 | participant_code、start_date、end_date、source | records、summary |
| `/api/admin/review/overview` | GET | 跨参与者统计 | Bearer token；非 admin 还需 `ADMIN_TOKEN` | stats |
| `/api/admin/records` | GET | 跨参与者记录查询 | Bearer token；非 admin 还需 `ADMIN_TOKEN` | records |

完整交互式 schema 可在服务启动后访问：

```text
http://127.0.0.1:8000/docs
```

## 项目目录结构

```text
EmoBridge/
├── emotion_rec/
│   ├── app.py                       # FastAPI、页面路由、鉴权与业务编排
│   ├── storage.py                   # SQLAlchemy schema、CRUD、统计与导出
│   ├── text_emotion.py              # 文本显性/隐性情绪推理与 fallback
│   ├── va_mapper.py                 # V-A 映射、标签、颜色和候选
│   ├── llm_client.py                # DeepSeek / OpenAI-compatible 统一客户端
│   ├── gemini_client.py             # Gemini 图片情绪分析
│   ├── body_sensation.py            # 身体感受、安全规则与建议
│   ├── shared/
│   │   └── emotion_lexicon.json     # 后端与前端共享的情绪词典
│   ├── static/                      # 原生 Web UI、样式、脚本和资源
│   └── start.sh                     # Unix 启动脚本
├── Wav2vec-2.0/                     # 本地 Wav2Vec2 模型与配置
├── emotion_computing/               # 本地模型 demo 和简化 API
├── hmotiongpt-api-test/             # 独立上传测试服务
├── audio/                           # 手工测试音频
├── docs/                            # 分析报告与图表
├── Idea/                            # 产品、研究与整合方案
├── requirements.txt                 # 完整开发依赖
├── requirements-web.txt             # Docker Web runtime 依赖
├── Dockerfile                       # 生产容器
├── render.yaml                      # Render Blueprint
└── DEPLOYMENT.md                    # 补充部署说明
```

## 安装与本地运行

### 环境要求

- Python 3.11+
- `ffmpeg` 可执行文件位于 `PATH`
- 建议至少准备可加载本地 Wav2Vec2 权重的内存
- 可选：CUDA；没有 GPU 时自动使用 CPU
- 可选：DeepSeek API key、Gemini API key、PostgreSQL

### 1. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 准备模型

仓库默认从根目录下的 `Wav2vec-2.0/` 加载模型。也可以覆盖路径：

```powershell
$env:MODEL_NAME_OR_PATH = "C:\path\to\Wav2vec-2.0"
```

`/api/transcribe` 首次使用时会尝试通过 Hugging Face `transformers` 加载 `openai/whisper-tiny`。如果部署环境不能访问网络，应提前缓存模型，或不要依赖服务端转写 fallback。

### 3. 配置环境变量

最小本地模式不要求外部 API key；文本、排版、建议和复盘会使用 fallback。账号部署建议至少设置稳定的 `SECRET_KEY`：

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-secret"
$env:ADMIN_TOKEN = "replace-with-an-admin-token"
$env:DEEPSEEK_API_KEY = "your_deepseek_api_key_here"
$env:GEMINI_API_KEY = "your_gemini_api_key_here"
```

可选 PostgreSQL：

```powershell
$env:DATABASE_URL = "postgresql://user:password@host:5432/database"
```

未设置 `DATABASE_URL` 时，SQLite 数据库会在应用启动时自动创建。

### 4. 启动服务

在仓库根目录执行：

```powershell
python -m uvicorn emotion_rec.app:app --host 0.0.0.0 --port 8000
```

访问：

```text
Web UI:   http://127.0.0.1:8000/
API docs: http://127.0.0.1:8000/docs
Health:   http://127.0.0.1:8000/healthz
```

Unix-like 环境也可以使用：

```bash
cd emotion_rec
bash start.sh
```

## 使用方式

### 典型用户流程

1. 打开 `/login` 注册，或以访客模式进入 `/`。
2. 在首页或 `/essay` 写下/说出一段经历，观察动态字体、情绪候选和 V-A 坐标。
3. 在必要时修正情绪标签或坐标，再保存为随手记。
4. 使用图片分析、Body 身体感受或 `/diary` 补充当天上下文。
5. 在 `/historyreview` 查看趋势、历史记录和阶段复盘。
6. 在 `/emo-echo` 继续以对话方式整理感受。

### 文本分析示例

```bash
curl -X POST "http://127.0.0.1:8000/analyze-text" \
  -H "Content-Type: application/json" \
  -d '{"text":"我说没事，但胸口一直很紧，今晚也睡不着。","intensity":0.8}'
```

### 音频分析示例

```bash
curl -X POST "http://127.0.0.1:8000/predict?return_embeddings=false" \
  -F "file=@audio/same_text/happy03-01-03-02-01-02-02.wav" \
  -F "text=I feel happy today"
```

### 健康检查

```bash
curl "http://127.0.0.1:8000/healthz"
```

### 快速验证

```powershell
python -m compileall emotion_rec emotion_computing hmotiongpt-api-test
python emotion_computing\demo.py
```

仓库目前以编译检查、模型 demo、示例音频和手工 API 调试为主，尚未提供完整的自动化测试套件。

## 环境变量

| 变量 | 默认值 / 作用 |
| --- | --- |
| `MODEL_NAME_OR_PATH` | 默认 `Wav2vec-2.0/`；本地语音情绪模型路径 |
| `VAD_SOURCE_RANGE` | 默认 `zero_one`；控制原始 VAD 是否映射到 `[-1, 1]` |
| `SECRET_KEY` | JWT 签名密钥；缺失时每次启动随机生成，旧 token 会失效 |
| `DATABASE_URL` | 缺失时使用本地 SQLite；支持 `postgres://` / `postgresql://` |
| `ADMIN_TOKEN` | 全量导出和部分研究端接口 token |
| `DEEPSEEK_API_KEY` | DeepSeek key；兼容 `LLM_API_KEY` |
| `DEEPSEEK_MODEL` | 默认 `deepseek-v4-flash`；兼容 `LLM_MODEL` |
| `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_TIMEOUT_SECONDS` | 默认 `30` |
| `LLM_ENABLED` | 默认启用；无 key 时仍视为不可用并走 fallback |
| `LLM_TYPOGRAPHY_TEMPERATURE` | 默认 `0.6` |
| `TEXT_EMOTION_BACKEND` | 默认 `deepseek`；可选 local model / classifier / rules 路径 |
| `TEXT_EMOTION_MODEL_NAME` | 默认 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `TEXT_EMOTION_CLASSIFIER_NAME` | 默认 `Johnson8187/Chinese-Emotion-Small` |
| `TEXT_EMOTION_HEAD_PATH` | regression head 权重路径 |
| `TEXT_EMOTION_LOCAL_FILES_ONLY` | 设为 `1` 时仅加载本地缓存 |
| `TEXT_EMOTION_LLM_MODEL` | 文本情绪专用 LLM，留空继承默认模型 |
| `BODY_ADVICE_LLM_ENABLED` | 是否启用 Body LLM 建议 |
| `BODY_LLM_MODEL` | Body 专用模型，留空继承默认模型 |
| `DIARY_REFLECTION_LLM_MODEL` | Diary 复盘专用模型 |
| `REVIEW_REFLECTION_LLM_MODEL` | Review 复盘专用模型 |
| `GEMINI_API_KEY` | Gemini 图片分析 key；兼容 `GOOGLE_API_KEY` |
| `GEMINI_MODEL` | 默认 `gemini-2.5-flash` |
| `GEMINI_FALLBACK_MODELS` | Gemini 瞬时错误时的回退模型链 |
| `GEMINI_TIMEOUT_SECONDS` | 默认 `30` |
| `GEMINI_MAX_RETRIES` | 默认 `1` |
| `GEMINI_ENABLED` | 图片分析开关 |

所有 secret 都应通过本地环境、平台 secret 或服务管理器注入，不要提交到仓库。

## Docker 与 Render 部署

### Docker

```bash
docker build -t emobridge .
docker run --rm -p 8000:8000 \
  -e SECRET_KEY=replace-with-a-long-random-secret \
  -e ADMIN_TOKEN=replace-with-an-admin-token \
  -e DEEPSEEK_API_KEY=your_deepseek_api_key_here \
  -e GEMINI_API_KEY=your_gemini_api_key_here \
  emobridge
```

容器通过 `${PORT:-8000}` 启动 FastAPI，前端由同一服务直接提供，不需要单独构建或部署。

如果使用容器内 SQLite，容器删除后数据库也会丢失。生产环境应挂载持久卷，或通过 `DATABASE_URL` 使用 PostgreSQL。

### Render

`render.yaml` 定义了 Docker Web Service、`/healthz` 和模型路径。部署时需要在 Render Dashboard 补充或确认：

- `SECRET_KEY`：当前 Blueprint 未声明，但生产 JWT 必须使用稳定值；
- `DATABASE_URL`：建议使用持久 PostgreSQL，不能依赖临时容器文件系统；
- `DEEPSEEK_API_KEY`：可选，缺失时相关功能使用 fallback；
- `GEMINI_API_KEY`：可选，缺失时图片上传不会产生分析；
- `ADMIN_TOKEN`：Blueprint 自动生成；
- `MODEL_NAME_OR_PATH=/app/Wav2vec-2.0`。

`render.yaml` 中的 service name 仍为历史值 `emomirror`。这不影响应用运行，但后续可以单独迁移为 `emobridge`。Wav2Vec2、PyTorch 和 Transformers 对内存要求较高，Render free plan 可能无法稳定加载模型，应以 `/healthz` 的 `model_loaded` 为准。

## 核心创新点

1. **从转写扩展到可交互的情绪感知转写**

   EmoBridge 不只返回 transcript，而是将显性词语、隐性线索、语音 VAD、pitch 和 energy 映射到统一情绪空间。用户还能修正模型判断，使系统适合研究“机器推断与自我感受之间的差异”。

2. **将连续情绪坐标转化为字符级表达**

   `llm_design` 是字符索引到视觉参数的映射，而不是一张静态情绪卡片。它让情绪强度、正负效价和语义重点直接作用于文字形态，连接 affective computing 与 kinetic typography。

3. **分离情绪推理与视觉映射**

   `text_emotion.py` 负责语义推理，`va_mapper.py` 只负责 V-A 到标签、颜色和候选的稳定映射。这个边界让本地模型、LLM、规则和前端 fallback 可以共享同一输出语义，降低实验替换成本。

4. **多模态结果保留来源与不一致性**

   图片分析区分人物表达和画面诱发情绪，前端同时展示文字/语音、图片和综合结果。图文冲突不会被简单隐藏，有利于研究多模态情绪解释与用户信任。

5. **从即时识别延伸到纵向反思**

   随手记、正式日记、身体感受、阶段复盘和 Emo 回响共享 participant 数据，不再是彼此孤立的模型页面。即时反馈可以进入后续统计和反思，形成持续的使用闭环。

6. **安全规则优先的身体-情绪连接**

   Body 模块在调用 LLM 前检查胸痛、呼吸困难、神经症状等红旗线索，并明确避免医学诊断。它展示了情绪辅助系统在处理身体化表达时应如何设置硬性安全边界。

## 产品定位与应用场景

EmoBridge 的统一定位是：

> 一个以情绪感知沟通、情感可达性和自我反思为目标的 HCI / 情感计算研究原型。

它同时包含情绪日记能力，但不等同于普通日记应用；包含语音与文本情绪识别，但不等同于单一分类 API；包含情感陪伴对话，但不替代心理咨询或医疗服务。

与当前实现一致的潜在场景包括：

- 情绪增强的 speech-to-text 与 expressive caption 原型；
- 面向述情困难、情绪辨识困难用户的自我表达辅助研究；
- 在线沟通、课堂或会议中的情绪可视化实验；
- 情绪日记、身体感受追踪和阶段性自我反思；
- affective UI、adaptive typography 与人机协同情绪标注研究；
- 非诊断式情感陪伴和社交情绪理解实验。

## 局限性与未来工作

- **缺少系统评估**：仓库未提供模型准确率、跨语言鲁棒性、延迟、消融实验或用户研究结果，不能据此声称临床或生产有效性。
- **语音模型信息不完整**：已提供本地模型权重和 regression 配置，但训练数据、训练流程和适用语言范围未完整公开。
- **多模态融合仍较浅**：图文融合依赖 LLM 或固定 70/30 V-A 加权，尚不是联合训练的 multimodal model。
- **服务端转写依赖首次模型下载**：`openai/whisper-tiny` 未打包进 Docker image；离线或受限网络环境可能返回 503。
- **鉴权仍保留 legacy mode**：多条 participant API 在未提供 JWT 时仍接受 `participant_code`。公开部署前应强制鉴权，并检查 CORS 当前的 `allow_origins=["*"]`。
- **删除语义不完整**：`DELETE /participants/{participant_code}/all-data` 当前删除 `diary_entries`、`formal_diaries` 和 `emotion_review_reports`，但不删除 `usage_events`、账号或 Emo 回响会话。
- **图片外部传输需要明确同意**：图片不在本地持久化，但配置 Gemini 后会发送给第三方 API；正式研究部署应补充告知、同意、保留策略和审计。
- **前端存储存在历史命名与双轨状态**：localStorage 使用 `emomirror.*` 键，并与服务端数据并行；后续需要统一同步策略和品牌迁移。
- **部署配置尚未完全品牌化**：FastAPI title、SQLite 文件名、Render service name 和部分静态资源仍使用历史名称。
- **自动化测试不足**：目前缺少覆盖鉴权、数据库迁移、API contract、多模态 fallback 和前端流程的完整测试。

## Citation

如果你在研究中使用 EmoBridge，请引用本仓库或后续正式发布的相关论文。当前仓库未提供正式 BibTeX 条目。

## License

当前仓库未包含 `LICENSE` 文件。在许可证补充前，请不要假设代码已自动获得特定的复制、修改或再分发授权。

## Acknowledgements

项目使用或兼容 FastAPI、SQLAlchemy、PyTorch、Hugging Face Transformers、Wav2Vec2、Whisper、DeepSeek OpenAI-compatible API、Gemini `google-genai` SDK、`librosa`、`pydub` 和 Chart.js 等技术与生态组件。具体模型与第三方服务的使用需遵循各自许可证和服务条款。
