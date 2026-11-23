"""前端 fixtures 同源生成器：直接调用 FastAPI 真实路由，生成三场景夹具 JSON。

为什么存在（ADR-0005 A0 连带项）：前端 fixtures（apps/web/fixtures/）历史上
手写维护，演示卡与后端 demo_evidence 数据漂移（旧夹具为聚合样本卡）。
本脚本把「夹具 = 后端响应快照」固化为可复现操作——夹具与后端逐字节同源，
fixture_note 字段留痕（前端 normalizeEnvelope 忽略未知键，不破坏契约）。

用法：.venv/Scripts/python.exe scripts/gen_web_fixtures.py
注意：跑完后提交三份 JSON；改 demo 数据或判定管道后必须重跑本脚本。
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from crosspilot_api.main import app
from fastapi.testclient import TestClient

FIXTURE_DIR = REPO_ROOT / "apps" / "web" / "fixtures"

#: 生成留痕字段（前端 normalizeEnvelope 忽略未知键）
NOTE = "由 scripts/gen_web_fixtures.py 从后端真实路由同源生成，勿手改；改 demo 数据或判定管道后重跑。"


def main() -> None:
    FIXTURE_DIR.mkdir(exist_ok=True)
    with TestClient(app) as client:
        targets = {
            "evidence_real.json": client.get("/api/evidence", params={"query": "旅行收纳包"}),
            "evidence_conflict.json": client.get("/api/evidence/demo", params={"scenario": "conflict"}),
            "evidence_limited.json": client.get("/api/evidence/demo", params={"scenario": "limited"}),
        }
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for filename, resp in targets.items():
        assert resp.status_code == 200, f"{filename}: HTTP {resp.status_code}"
        body = resp.json()
        body["fixture_note"] = NOTE
        body["fixture_generated_at"] = stamp
        out = FIXTURE_DIR / filename
        out.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] {filename}: stance={body['stance']} cards={len(body['cards'])}")


if __name__ == "__main__":
    main()
