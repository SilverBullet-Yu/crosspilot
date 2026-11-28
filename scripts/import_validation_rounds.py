#!/usr/bin/env python3
"""工作台验证轮次 JSON 校验与归档命令。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from crosspilot_api.services.validation_round import main

if __name__ == "__main__":
    main()
