# EmoBridge / Emotype Deployment

本项目当前正式运行目录是：

```bash
cd /root/Emotype
```

FastAPI 应用入口：

```text
emotion_rec.app:app
```

## 本地 / 服务器前台启动

```bash
cd /root/Emotype
python -m uvicorn emotion_rec.app:app --host 0.0.0.0 --port 8000
```

打开页面：

```text
http://127.0.0.1:8000/
```

## 后台启动

```bash
cd /root/Emotype
nohup /root/miniconda3/bin/python3 -m uvicorn emotion_rec.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  > /tmp/emotype.log 2>&1 &
```

查看日志：

```bash
tail -f /tmp/emotype.log
```

## 健康检查

```bash
curl http://127.0.0.1:8000/healthz
```

页面检查：

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/body
curl -I http://127.0.0.1:8000/body-sensation
curl -I http://127.0.0.1:8000/body_sensation
curl -I http://127.0.0.1:8000/diary
curl -I http://127.0.0.1:8000/review
curl -I http://127.0.0.1:8000/records
curl -I http://127.0.0.1:8000/history
```

## 环境变量

生成式模型调用统一走 `emotion_rec/llm_client.py`。

```bash
export DEEPSEEK_API_KEY=your_deepseek_api_key_here
export DEEPSEEK_MODEL=deepseek-v4-flash
export ADMIN_TOKEN=your_admin_token_here
```

常用变量：

| 变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek key，缺失时走本地 fallback。 |
| `DEEPSEEK_MODEL` | 默认 LLM 模型。 |
| `DEEPSEEK_BASE_URL` | OpenAI-compatible base URL。 |
| `LLM_API_KEY` | 旧版 key alias。 |
| `DATABASE_URL` | 数据库连接，缺失时使用 SQLite。 |
| `ADMIN_TOKEN` | 管理端导出和 all users 聚合接口 token。 |
| `MODEL_NAME_OR_PATH` | 本地 Wav2Vec2 模型路径。 |

不要把真实 key 写入仓库。生产环境应通过服务管理器、平台 secret 或 shell 环境注入。

## 数据库

未设置 `DATABASE_URL` 时，默认使用：

```text
emotion_rec/emomirror_data.sqlite3
```

设置 PostgreSQL 示例：

```bash
export DATABASE_URL=postgresql://user:password@host:5432/database
```

代码会自动把 `postgres://` / `postgresql://` 转成 psycopg 兼容连接。当前主要表包括：

- `participants`
- `diary_entries`
- `formal_diaries`
- `emotion_review_reports`
- `usage_events`

## 主要页面

- `/`：Journal / 实时情绪识别与动态字体可视化。
- `/body`、`/body-sensation`、`/body_sensation`：身体感受记录。
- `/diary`：正式日记。
- `/review`：阶段性情绪复盘。
- `/records`、`/history`：我的历史记录。
- `/healthz`：健康检查。

## 关键 API 检查

```bash
curl "http://127.0.0.1:8000/api/diary?date=YYYY-MM-DD&participant_code=local"
curl "http://127.0.0.1:8000/api/review/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=local"
curl "http://127.0.0.1:8000/api/review/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=local"
curl "http://127.0.0.1:8000/api/records?participant_code=local&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&source=all"
```

管理端 all users 接口必须传 `ADMIN_TOKEN`：

```bash
curl "http://127.0.0.1:8000/api/admin/review/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=all" \
  -H "X-Admin-Token: your_admin_token_here"

curl "http://127.0.0.1:8000/api/admin/records?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&participant_code=all" \
  -H "X-Admin-Token: your_admin_token_here"
```

## 编译检查

```bash
python -m compileall emotion_rec emotion_computing hmotiongpt-api-test
```

## Docker / Render 说明

仓库保留 `Dockerfile` 和 `render.yaml`，可用于容器部署。容器需要 CPU PyTorch、FastAPI 依赖、`ffmpeg` 和 `libsndfile` 等音频依赖。

部署时至少配置：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `DATABASE_URL`
- `ADMIN_TOKEN`

如果 `/healthz` 显示 `model_loaded: false`，优先检查模型文件路径、内存和服务日志。Wav2Vec2 模型文件较大，低内存实例可能无法加载。

## 安全扫描

完成部署配置或文档变更后，应运行仓库约定的 key 扫描命令。只出现 `os.getenv(...)`、`DEEPSEEK_API_KEY=...` 或占位符示例可以接受。
