#!/usr/bin/env bash
# 提交前自检。红灯不合并。
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"
[ -x "$PY" ] || { echo "未找到虚拟环境，先跑 bash scripts/bootstrap.sh" >&2; exit 2; }

echo "==> ruff"
"$PY" -m ruff check apps/api data/sources/_scripts scripts/import_l1_reviews.py scripts/import_operator_trial.py scripts/import_validation_rounds.py scripts/audit_case.py scripts/eval_stance_baseline.py

echo "==> mypy"
"$PY" -m mypy apps/api/src

echo "==> pytest（含硬约束回归）"
"$PY" -m pytest apps/api -q

echo "==> 数据区结构校验"
"$PY" data/sources/_scripts/validate_sources.py

echo "==> 数据区时间覆盖校验"
"$PY" data/sources/_scripts/validate_coverage.py

echo "==> 数据区质量校验（主键/raw 完整性/留痕/PII 计数/快照）"
"$PY" data/sources/_scripts/validate_quality.py

echo "==> 全部通过"
