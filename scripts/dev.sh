#!/usr/bin/env bash
# 启动开发服务：dev.sh api | dev.sh web
set -euo pipefail
cd "$(dirname "$0")/.."
target="${1:-api}"

PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"

case "$target" in
  api)
    [ -x "$PY" ] || { echo "未找到虚拟环境，先跑 bash scripts/bootstrap.sh" >&2; exit 2; }
    exec "$PY" -m uvicorn crosspilot_api.main:app --reload --app-dir apps/api/src --port 8000
    ;;
  web)
    exec npm --prefix apps/web run dev
    ;;
  *)
    echo "用法: dev.sh [api|web]" >&2
    exit 2
    ;;
esac
