#!/usr/bin/env bash
set -e

# 进入脚本所在目录（可选，但很常用）
cd "$(dirname "$0")"

# 可选：设置 CORS 和模型路径（按需修改/删除）
export CORS_ALLOW_ORIGINS="*"
# export MODEL_NAME_OR_PATH="/path/to/local/model"

# 启动服务
uvicorn app:app --host 0.0.0.0 --port 8000
