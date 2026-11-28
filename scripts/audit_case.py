#!/usr/bin/env python3
"""审计真实商品案例是否达到 blocked / exploratory / decision_ready / trial_complete。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from crosspilot_api.domain.evidence import decide_by_claim
from crosspilot_api.services.case_readiness import ReadinessLevel, assess_case_readiness
from crosspilot_api.services.claims import select_claim_ids
from crosspilot_api.services.l1_import import (
    L1_SNAPSHOT_DIR,
    L1ImportError,
    load_l1_snapshot_data,
)
from crosspilot_api.services.validation_round import (
    DEFAULT_OUTPUT_DIR,
    ValidationRoundError,
    load_validation_rounds_archive_data,
)


def render(readiness: object) -> str:
    data = asdict(readiness)  # type: ignore[arg-type]
    lines = [
        f"query={data['query']}；market={data['market']}",
        f"snapshot_sha256={data['snapshot_sha256'] or '未加载'}",
        f"rounds_archive_sha256={data['rounds_archive_sha256'] or '未加载'}",
        f"level={data['level']}",
        data["summary"],
        "",
        "检查项：",
    ]
    for check in data["checks"]:
        lines.append(f"- [{check['status']}] {check['label']}：{check['detail']}")
    lines.extend(["", "卖点："])
    for claim in data["claims"]:
        lines.append(
            f"- {claim['claim_id']}: state={claim['state']}，L1={claim['n_l1']}，"
            f"极性 n={claim['n_polarized']}，待复核={claim['review_pending']}，"
            f"已确认轮次={claim['confirmed_rounds']}"
        )
    lines.extend(["", "下一步："])
    lines.extend(f"- {action}" for action in data["next_actions"])
    lines.append(f"- 是否允许声称市场效果：{data['market_effect_claim_allowed']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="真实商品案例就绪度审计")
    parser.add_argument("--query", required=True)
    parser.add_argument("--snapshot-dir", type=Path, default=L1_SNAPSHOT_DIR)
    parser.add_argument("--rounds-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--claim-id",
        action="append",
        default=[],
        help="本次案例活跃卖点，可重复；默认检查内置三项与快照中的自定义卖点",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    gate = parser.add_mutually_exclusive_group()
    gate.add_argument(
        "--require-ready",
        action="store_true",
        help="非 decision_ready/trial_complete 时退出 1",
    )
    gate.add_argument(
        "--require-trial-complete",
        action="store_true",
        help="仅 trial_complete 时退出 0；用于真实案例 + 运营试用闭环验收",
    )
    args = parser.parse_args()
    try:
        snapshot = load_l1_snapshot_data(args.query, args.snapshot_dir)
        cards = snapshot.cards
        l1_notice = snapshot.notice
        decisions = decide_by_claim(cards, select_claim_ids(cards, args.claim_id))
        rounds_archive = load_validation_rounds_archive_data(args.rounds_dir)
        rounds = rounds_archive.records
    except (L1ImportError, ValidationRoundError) as exc:
        parser.exit(2, f"审计失败：{exc}\n")
    except ValueError as exc:
        parser.exit(2, f"审计参数错误：{exc}\n")
    readiness = assess_case_readiness(
        query=args.query,
        market="de",
        cards=cards,
        claim_decisions=decisions,
        rounds=rounds,
        snapshot_sha256=snapshot.snapshot_sha256,
        rounds_archive_sha256=rounds_archive.archive_sha256,
    )
    if args.json:
        print(json.dumps(asdict(readiness), ensure_ascii=False, indent=2))
    else:
        print(render(readiness))
        if l1_notice:
            print(f"\nL1 提示：{l1_notice}")
    if args.require_ready and readiness.level not in {
        ReadinessLevel.DECISION_READY,
        ReadinessLevel.TRIAL_COMPLETE,
    }:
        raise SystemExit(1)
    if args.require_trial_complete and readiness.level is not ReadinessLevel.TRIAL_COMPLETE:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
