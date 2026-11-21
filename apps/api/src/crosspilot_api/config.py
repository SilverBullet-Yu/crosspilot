"""运行配置。演示安全线：默认 snapshot 模式，不走实时网络。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    data_mode: str = os.getenv("CROSSPILOT_DATA_MODE", "snapshot")
    zhihu_secret: str | None = os.getenv("ZHIHU_ACCESS_SECRET")
    comtrade_key: str | None = os.getenv("COMTRADE_SUBSCRIPTION_KEY")
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://localhost:5432/crosspilot"
    )
    snapshot_dir: Path = REPO_ROOT / "data" / "snapshots"

    # OpenAI 兼容文本推理端点（LLM 立场抽取用，ADR-0004）；三项齐备才可用
    llm_api_base: str | None = os.getenv("LLM_API_BASE")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "")

    @property
    def is_live(self) -> bool:
        return self.data_mode == "live"


settings = Settings()
