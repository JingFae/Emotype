# Emotype 部署说明

本项目现在按一个 FastAPI Web Service 部署：

- `/` 提供 EmoType Studio 网页
- `/predict` 提供音频情绪识别和排版生成 API
- `/healthz` 提供部署健康检查

## 本地运行

```powershell
pip install -r requirements.txt
uvicorn emotion_rec.app:app --host 0.0.0.0 --port 8000
```

打开：

```text
http://localhost:8000/
```

## Render 部署

仓库根目录已提供 `render.yaml`，可以通过 Render Blueprint 创建公网服务。

1. 提交并推送代码到 GitHub：

```powershell
git add .gitignore AGENTS.md DEPLOYMENT.md render.yaml emotion_rec/app.py emotion_rec/static requirements.txt
git commit -m "Add EmoType web studio and Render deployment"
git push origin main
```

2. 打开 Render Blueprint：

```text
https://dashboard.render.com/blueprint/new?repo=https://github.com/JingFae/Emotype
```

3. 在 Render 页面填写 secret 环境变量：

```text
LLM_API_KEY
```

如果暂时不填写，后端会使用本地 fallback 生成基础排版效果。

## 模型和资源注意事项

- `Wav2vec-2.0/model.safetensors` 很大，并通过 Git LFS 管理。部署前确认 GitHub 上是真实 LFS 对象，不是损坏的指针文件。
- Torch + Wav2Vec2 模型内存占用较高。Render Free 实例可能不足以稳定承载模型推理；如果启动失败或 OOM，升级到更高内存实例。
- Render Native Runtime 已包含 `ffmpeg`，浏览器录音产生的 WebM 音频可以由当前 `pydub` 转换流程处理。

