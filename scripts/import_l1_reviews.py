#!/usr/bin/env python3
"""授权德国 L1 评论导入命令。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from crosspilot_api.services.l1_import import main

if __name__ == "__main__":
    main()
