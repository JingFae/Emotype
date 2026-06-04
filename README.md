# EmoBridge / EmoMirror

EmoType 是一个面向“语音情绪识别 + 情绪文字日记 + 动态字体可视化”的实验项目。项目当前已经实现了基础的音频情绪 VAD 推理、文本情绪分析、V-A 坐标映射、动态字体渲染、日记数据保存与 Docker/Render 部署配置。

项目仍处于中期开发阶段，后续会继续在模型效果、映射规则、前端体验、数据库设计和部署稳定性等方面迭代。

## 项目目标

本项目希望把用户的语音、文本和主观情绪记录转化为可感知的视觉反馈：

- 通过本地 Wav2Vec2 模型从音频中预测情绪维度：
  - `arousal`
  - `dominance`
  - `valence`
- 通过文本情绪模块分析日记内容中的显性和隐性情绪线索。
- 将 Valence-Arousal 坐标映射到情绪标签、候选标签、颜色和象限。
- 使用 LLM 或本地 fallback 规则生成字符级动态字体设计图。
- 在网页端提供日记输入、语音输入、情绪镜像、V-A 坐标调整、标签修正和数据导出能力。

## 当前实现概览

### 1. 情绪识别模型

当前音频情绪识别位于 `emotion_rec/app.py` 和 `emotion_computing/`。

已经实现：

- 使用本地 `Wav2vec-2.0/` 模型加载 Hugging Face Wav2Vec2 结构。
- 自定义 `RegressionHead` 输出三维情绪值。
- `/predict` 接口支持上传音频并返回：
  - 原始 `vad`
  - 归一化后的 `vad_normalized`
  - 声学特征 `acoustics`
  - V-A 映射结果 `va_mapping`
  - 字符级字体设计 `llm_design`
- 使用 `librosa` 提取 pitch 和 energy。
- 使用 `pydub`/`ffmpeg` 将浏览器录音格式转换为 WAV 后再推理。
- `emotion_computing/demo.py` 和 `emotion_computing/check.py` 保留了模型推理 demo 和简化 API，便于单独测试模型。

待完善：

- 增加更完整的音频测试集评估，例如不同说话人、不同情绪类别、不同录音设备。
- 明确当前模型输出范围，并持续校准 `VAD_SOURCE_RANGE`。
- 优化 WebM、WAV、MP3 等输入格式的兼容测试。
- 后续可加入模型量化、ONNX、缓存或异步推理，降低部署资源压力。

### 2. 文本情绪分析

文本情绪分析逻辑集中在 `emotion_rec/text_emotion.py`。

已经实现：

- `/analyze-text` 调用 `analyze_text_emotion(...)` 对输入日记文本做情绪分析。
- 支持按句段切分文本，并返回每个 segment 的：
  - `text`
  - `valence`
  - `arousal`
  - `confidence`
  - `explicit_label`
  - `implicit_label`
  - `evidence`
  - `source`
- 当前采用多层 fallback 策略：
  - 如果存在训练好的文本情绪回归头，优先使用 multilingual sentence transformer + regression head。
  - 如果回归头不可用，尝试加载 `Johnson8187/Chinese-Emotion-Small` 做显性情绪分类。
  - 如果分类器不可用，继续使用确定性规则。
- 规则层已覆盖：
  - 否认式表达
  - 弱化表达
  - 转折表达
  - 身体紧绷
  - 压力过载
  - 羞耻/自责
  - 压抑愤怒
  - 孤独
  - 关系评价
  - 逃避冲动
  - 中英文常见情绪提示词

待完善：

- 训练并接入真正稳定的文本 V-A 回归头，建议路径为 `emotion_rec/models/text_emotion_head.pt`。
- 用真实日记/访谈数据标注 Valence-Arousal，建立文本情绪评估集。
- 增加中文语义细粒度处理，例如反讽、压抑、矛盾表达、上下文延续。
- 修复部分源码和页面中的中文编码异常注释或文案。

### 3. V-A 映射规则

映射规则集中在 `emotion_rec/va_mapper.py` 和前端 `emotion_rec/static/vaMapper.js`。

已经实现：

- 将输入的 Valence-Arousal 坐标映射到：
  - 情绪象限
  - 情绪颜色
  - 最近情绪标签
  - 候选情绪标签
  - 置信度
- 使用 `emotion_rec/shared/emotion_lexicon.json` 作为后端和前端共享的 80 个情绪标签词典。
- 后端支持 segment 级映射，并计算整体情绪坐标。
- 前端保留了一套本地 fallback 映射逻辑，当后端请求失败时仍可渲染基础反馈。

待完善：

- 继续优化 80 标签词典的分布，使标签在 V-A 平面上更均匀、更符合中文用户理解。
- 增加用户手动修正后的反馈数据，用于反向校准映射规则。
- 对颜色、动画和标签之间的关系做用户研究，避免“模型正确但视觉感受不匹配”。
- 将后端和前端映射逻辑进一步统一，减少双端规则漂移。

### 4. 动态字体生成

动态字体生成主要在 `emotion_rec/app.py` 和 `emotion_rec/static/app.js`。

已经实现：

- 后端提供 `process_typography_request(...)` 作为排版设计入口。
- 优先检查 demo 触发句，命中后返回固定字符级设计。
- 未命中 demo 时调用 LLM 生成关键词级设计，再转成字符索引 map。
- 当没有配置 `DEEPSEEK_API_KEY` 或外部接口失败时，使用本地 fallback 设计。
- 前端根据 `llm_design` 对每个字符应用：
  - font weight
  - scale
  - color
  - animation
  - emoji 替换
- 当前支持的动画包括 `shake-hard`、`pulse-scale`、`sad-droop`、`float-drift` 等。

待完善：

- 将 prompt、demo trigger、fallback 样式从 `app.py` 中拆分到独立模块，便于维护。
- 增加 LLM 输出 JSON schema 校验，避免异常格式影响前端渲染。
- 让动态字体生成更多依赖稳定的 V-A 映射结果，而不是过度依赖 LLM 自由判断。
- 增加不同文本长度下的排版策略，例如短句、长日记、多段落。

### 5. 前端界面

前端位于 `emotion_rec/static/`，当前使用原生 HTML/CSS/JavaScript 实现。

已经实现：

- `/` 直接服务 Web UI。
- 首页展示最近日记、最新情绪和反馈强度。
- Journal 页面支持：
  - 文本输入
  - 浏览器语音识别输入
  - 实时文本情绪分析
  - 动态字体镜像
  - 情绪候选标签
  - 自定义情绪标签
  - V-A 坐标手动拖拽调整
  - 反馈强度调整
  - 日记保存
- 支持 Local mode，本地使用 `localStorage` 保存日记。
- 输入实验编号后，可连接后端保存参与者、日记和使用事件。
- 支持按参与者导出 JSON/CSV。

待完善：

- 修复页面中部分中文文案编码异常。
- 增加移动端适配和不同屏幕尺寸下的排版测试。
- 增加 loading、错误提示、空状态和保存成功提示的细节。
- 将前端拆分为更清晰的模块，后续如果功能继续增多可考虑迁移到 React/Vue/Svelte。
- 增加可视化调试面板，用于查看当前 V-A、segment、evidence 和设计 map。

### 6. 后端 API 与数据库

主后端服务位于 `emotion_rec/app.py`，数据库逻辑位于 `emotion_rec/storage.py`。

已经实现的主要接口：

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | 返回前端页面 |
| `/healthz` | GET | 服务健康检查 |
| `/analyze-text` | POST | 文本情绪分析和动态字体设计 |
| `/predict` | POST | 音频情绪推理 |
| `/participants/session` | POST | 创建或恢复参与者会话 |
| `/participants/{participant_code}/diaries` | GET | 获取参与者日记 |
| `/diaries` | POST | 保存日记 |
| `/usage-events` | POST | 保存交互事件 |
| `/participants/{participant_code}/export.json` | GET | 导出个人 JSON |
| `/participants/{participant_code}/export.csv` | GET | 导出个人 CSV |
| `/admin/export.json` | GET | 管理员导出全部 JSON |
| `/admin/export.csv` | GET | 管理员导出全部 CSV |

数据库已经实现：

- 默认使用 SQLite：`emotion_rec/emomirror_data.sqlite3`
- 可通过 `DATABASE_URL` 切换到 PostgreSQL。
- 使用 SQLAlchemy 定义：
  - `participants`
  - `diary_entries`
  - `usage_events`
- 管理员导出接口通过 `ADMIN_TOKEN` 保护。

待完善：

- 增加数据库迁移工具，例如 Alembic。
- 补充更严格的隐私保护策略，例如脱敏、删除个人数据、实验同意版本管理。
- 区分开发环境、测试环境和生产环境数据库。
- 为研究数据增加更清晰的数据字典和字段说明。

### 7. 部署

项目当前提供 Docker 和 Render 部署配置。

已经实现：

- `Dockerfile` 基于 `python:3.11-slim`。
- Docker 镜像中安装：
  - CPU PyTorch
  - FastAPI 运行依赖
  - ffmpeg
  - libsndfile
- `render.yaml` 配置了一个 Docker Web Service。
- `/healthz` 可用于 Render 健康检查。
- `requirements-web.txt` 用于 Docker 部署时在 CPU PyTorch 之后安装其他依赖。
- `DEPLOYMENT.md` 记录了本地运行、Render Blueprint 和 Docker 运行方式。

待完善：

- 确认 Render 免费实例的内存是否足够加载 Wav2Vec2 模型。
- 将模型文件管理方式标准化，例如 Git LFS、外部模型下载或部署前构建。
- 增加 CI 检查，至少自动运行 Python 语法检查和基础接口测试。
- 为 LLM API、数据库、管理员 token 等环境变量补充生产配置说明。

## 项目结构

```text
Emotype/
├── emotion_rec/
│   ├── app.py                     # 主 FastAPI 服务，包含前端服务、模型推理、文本分析接口和排版生成
│   ├── text_emotion.py            # 文本情绪分析：回归头、分类器、规则 fallback
│   ├── va_mapper.py               # V-A 坐标到标签、颜色、象限、候选情绪的映射
│   ├── storage.py                 # SQLAlchemy 数据库模型与导出逻辑
│   ├── shared/
│   │   └── emotion_lexicon.json   # 后端和前端共用的情绪词典
│   ├── static/
│   │   ├── index.html             # 前端页面
│   │   ├── app.js                 # 前端交互、分析请求、本地 fallback 和渲染逻辑
│   │   ├── vaMapper.js            # 前端 V-A 映射工具
│   │   └── styles.css             # 页面样式和动画
│   └── start.sh                   # Unix-like 启动脚本
├── emotion_computing/
│   ├── demo.py                    # 本地 Wav2Vec2 推理 demo
│   └── check.py                   # 简化版音频情绪 API
├── hmotiongpt-api-test/
│   └── app.py                     # 文件上传测试服务
├── Wav2vec-2.0/                   # 本地 Hugging Face 模型文件
├── audio/                         # 测试音频样本
├── Dockerfile                     # 生产容器构建配置
├── render.yaml                    # Render Blueprint
├── requirements.txt               # 本地开发依赖
├── requirements-web.txt           # Docker/部署依赖
└── DEPLOYMENT.md                  # 部署说明
```

## 运行方式

建议使用 Python 3.11+。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

启动主服务：

```powershell
uvicorn emotion_rec.app:app --host 0.0.0.0 --port 8000
```

或者进入 `emotion_rec/` 后启动：

```powershell
Set-Location emotion_rec
uvicorn app:app --host 0.0.0.0 --port 8000
```

打开前端：

```text
http://localhost:8000/
```

查看接口文档：

```text
http://localhost:8000/docs
```

健康检查：

```text
http://localhost:8000/healthz
```

## 关键环境变量

生成式大模型调用统一走 `emotion_rec/llm_client.py`，通过 OpenAI SDK 访问 DeepSeek。默认模型是 `deepseek-v4-flash`；文本情绪默认优先调用 DeepSeek，失败或无 key 时自动回退本地分类器/规则。音频情绪识别仍使用本地 Wav2Vec2。

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `MODEL_NAME_OR_PATH` | Wav2Vec2 模型路径 | `Wav2vec-2.0/` |
| `VAD_SOURCE_RANGE` | 模型输出归一化方式 | `zero_one` |
| `DEEPSEEK_API_KEY` | DeepSeek API key，缺失时使用本地 fallback | 空 |
| `DEEPSEEK_MODEL` | 全局默认 LLM 模型 | `deepseek-v4-flash` |
| `DEEPSEEK_BASE_URL` | OpenAI-compatible base URL | `https://api.deepseek.com` |
| `DEEPSEEK_TIMEOUT_SECONDS` | LLM 超时时间 | `30` |
| `LLM_ENABLED` | 是否启用 LLM 调用 | `1` |
| `LLM_TYPOGRAPHY_TEMPERATURE` | 动态字体生成温度 | `0.6` |
| `DATABASE_URL` | 数据库连接，缺失时使用本地 SQLite | `emotion_rec/emomirror_data.sqlite3` |
| `ADMIN_TOKEN` | 管理员导出接口 token | 空 |
| `TEXT_EMOTION_BACKEND` | 文本情绪后端：`deepseek` / `auto` / `classifier` / `rules` | `deepseek` |
| `TEXT_EMOTION_LLM_MODEL` | 文本情绪专用模型，留空继承 `DEEPSEEK_MODEL` | 空 |
| `TEXT_EMOTION_LLM_TEMPERATURE` | 文本情绪分析温度 | `0.0` |
| `TEXT_EMOTION_MAX_TOKENS` | 文本情绪 JSON 输出上限 | `8192` |
| `TEXT_EMOTION_MODEL_NAME` | 本地文本语义编码模型，fallback 用 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `TEXT_EMOTION_CLASSIFIER_NAME` | 本地文本显性情绪分类器，fallback 用 | `Johnson8187/Chinese-Emotion-Small` |
| `TEXT_EMOTION_HEAD_PATH` | 本地文本情绪回归头路径，fallback 用 | `emotion_rec/models/text_emotion_head.pt` |
| `BODY_ADVICE_LLM_ENABLED` | 身体感受建议是否调用 DeepSeek，高风险红旗仍走安全 fallback | `1` |
| `BODY_LLM_MODEL` | 身体感受建议专用模型，留空继承 `DEEPSEEK_MODEL` | 空 |
| `BODY_LLM_TEMPERATURE` | 身体感受建议温度 | `0.15` |
| `BODY_LLM_MAX_TOKENS` | 身体感受建议 JSON 输出上限 | `4096` |
| `DIARY_REFLECTION_LLM_MODEL` | 正式日记复盘专用模型，留空继承 `DEEPSEEK_MODEL` | 空 |
| `DIARY_REFLECTION_LLM_TEMPERATURE` | 正式日记复盘温度 | `0.18` |
| `DIARY_REFLECTION_LLM_MAX_TOKENS` | 正式日记复盘 JSON 输出上限 | `4096` |

## 中期汇报可用流程

一个完整的演示流程可以是：

1. 打开 `http://localhost:8000/`。
2. 在 Journal 页面输入一段情绪日记。
3. 展示系统如何返回文本情绪、候选标签和动态字体。
4. 拖动 V-A 坐标，说明用户可以修正模型判断。
5. 保存日记，展示数据进入本地或后端数据库。
6. 使用参与者编号导出 JSON/CSV。
7. 上传一段音频到 `/predict`，展示音频模型返回的 VAD 与排版结果。

## 后续优化路线

### 情绪识别模型优化

- 建立音频情绪测试集和文本情绪测试集。
- 训练文本 V-A regression head，替代目前偏 demo 的规则 fallback。
- 校准 Wav2Vec2 输出，使不同输入设备和说话人之间更稳定。
- 增加模型推理耗时、失败率和置信度统计。

### 映射规则优化

- 重新审视 80 个情绪词在 V-A 平面的位置。
- 将用户手动修改后的标签作为校准数据。
- 统一后端 `va_mapper.py` 和前端 `vaMapper.js` 的逻辑来源。
- 建立“情绪标签、颜色、动画、字体参数”的设计规范。

### 前端优化

- 修复编码异常的中文文案。
- 强化移动端体验。
- 增加更清晰的错误提示和状态提示。
- 增加调试/研究视图，显示 segment、evidence、V-A 坐标和设计 map。
- 后续可组件化重构，降低 `app.js` 继续变大的维护压力。

### 后端与数据库优化

- 拆分 `app.py` 中的模型、排版、路由和配置逻辑。
- 引入 Alembic 管理数据库 schema 变更。
- 增加 API 测试和接口契约文档。
- 增加研究数据隐私策略和删除机制。

### 部署与工程化优化

- 使用 GitHub Actions 做基础检查。
- 使用 Git LFS 或外部存储管理大模型文件。
- 为 Render 部署准备生产级数据库和环境变量说明。
- 持续监控内存占用，必要时做模型压缩或换更高配置实例。

## 当前已知问题

- 部分中文注释和页面文案存在编码异常，需要后续统一修复。
- 文本情绪回归头目前不是稳定主路径，更多依赖分类器和规则 fallback。
- `app.py` 当前承担了较多职责，后续应拆分模块。
- LLM 排版结果依赖外部 API，必须保留 timeout 和本地 fallback。
- 本地 SQLite 适合开发和演示，正式研究数据建议使用 PostgreSQL。
- Wav2Vec2 模型文件较大，部署时要注意内存和仓库体积。

## 适合组员分工的模块

| 方向 | 主要文件 | 可负责内容 |
| --- | --- | --- |
| 音频情绪模型 | `emotion_rec/app.py`, `emotion_computing/` | 模型评估、音频格式兼容、VAD 校准 |
| 文本情绪模型 | `emotion_rec/text_emotion.py` | 文本数据标注、回归头训练、隐性情绪规则优化 |
| 映射规则 | `emotion_rec/va_mapper.py`, `emotion_rec/shared/emotion_lexicon.json`, `emotion_rec/static/vaMapper.js` | 情绪词典、颜色、象限、候选标签 |
| 动态字体 | `emotion_rec/app.py`, `emotion_rec/static/app.js`, `emotion_rec/static/styles.css` | LLM prompt、fallback 样式、动画和 emoji |
| 前端体验 | `emotion_rec/static/` | 页面交互、移动端、可视化调试、文案修复 |
| 数据库 | `emotion_rec/storage.py` | 表结构、导出、隐私、迁移 |
| 部署 | `Dockerfile`, `render.yaml`, `DEPLOYMENT.md` | Render 部署、环境变量、CI/CD、模型文件管理 |

## 开发注意事项

- 不要提交 `.env`、证书、私钥、日志、缓存和本地虚拟环境。
- 不要随意移动 `Wav2vec-2.0/`，除非同步更新模型路径逻辑。
- 修改 API 返回结构前，需要确认前端是否依赖当前字段。
- 修改情绪映射时，要同时考虑后端和前端 fallback。
- 改动后建议至少运行：

```powershell
python -m compileall emotion_rec emotion_computing hmotiongpt-api-test
```
