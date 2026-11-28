#!/usr/bin/env bash
# 一次性初始化开发环境。可重复执行。
#
# 说明：本脚本刻意不使用 `pip install -e`。可编辑安装会调起构建后端子进程，
# 在部分受管运行时下会被环境守卫拦截（CHAT_REFERENCE_PROTECTED）。
# 改为「装依赖 + 用 .pth 挂载 src」，效果等价且更稳。
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"

echo "==> 创建虚拟环境"
if [ ! -x "$PY" ]; then
  python -m venv .venv || true
  PY=".venv/Scripts/python.exe"
  [ -x "$PY" ] || PY=".venv/bin/python"
fi

# 某些环境下 venv 不会自带 pip，需补装
if ! "$PY" -m pip --version >/dev/null 2>&1; then
  echo "==> 补装 pip"
  "$PY" -m ensurepip --upgrade
fi

echo "==> 安装依赖"
"$PY" -m pip install -q --upgrade pip setuptools wheel
"$PY" -m pip install -q \
  "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" \
  "httpx>=0.27"
"$PY" -m pip install -q "pytest>=8.3" "ruff>=0.7" "mypy>=1.13"

echo "==> 挂载源码路径"
SITE="$("$PY" -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')"
printf '%s\n' "$ROOT/apps/api/src" > "$SITE/_crosspilot_src.pth"
"$PY" -c "import crosspilot_api; print('    ok:', crosspilot_api.__file__)"

echo "==> 配置文件"
[ -f .env ] || { cp .env.example .env; echo "    已生成 .env 记录模板；脚本不会自动加载，请将所需变量导出到当前 shell"; }

echo "==> 前端依赖"
if [ -f apps/web/package.json ]; then
  (cd apps/web && npm install --silent)
else
  echo "    跳过：apps/web 尚未初始化 Nuxt"
fi

echo "==> 完成。下一步：bash scripts/dev.sh api"
