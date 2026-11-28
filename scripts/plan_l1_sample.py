#!/usr/bin/env python3
"""为授权德国 L1 生成确定性的卖点 × 立场 × 发布月份采样清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from crosspilot_api.domain.evidence import Stance, decide_by_claim
from crosspilot_api.services.claims import select_claim_ids
from crosspilot_api.services.l1_import import (
    L1_SNAPSHOT_DIR,
    L1SnapshotData,
    load_l1_snapshot_data,
)


def build_sampling_plan(
    snapshot: L1SnapshotData,
    query: str,
    *,
    target: int = 30,
    seed: int = 42,
    claim_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    if target < 1:
        raise ValueError("target 必须大于 0")
    claim_ids = select_claim_ids(snapshot.cards, claim_ids)
    decisions = decide_by_claim(snapshot.cards, claim_ids)
    plans: list[dict[str, object]] = []
    for claim_id in claim_ids:
        claim_cards = [
            card
            for card in snapshot.cards
            if card.claim_id == claim_id
            and card.relevance == "relevant"
            and card.level.value == "L1"
            and not card.is_demo_data
        ]
        dedup = decisions[claim_id].dedup_by_card
        canonical = [
            card
            for card, info in zip(claim_cards, dedup, strict=True)
            if (info is None or info.is_canonical)
            and card.stance in {Stance.SUPPORT, Stance.OPPOSE}
        ]
        strata: dict[tuple[str, str], list] = defaultdict(list)
        for card in canonical:
            strata[(card.stance.value, card.published_on.strftime("%Y-%m"))].append(card)
        claim_seed = seed + int(
            hashlib.sha256(claim_id.encode("utf-8")).hexdigest()[:8],
            16,
        )
        rng = random.Random(claim_seed)
        ordered_strata = sorted(strata)
        for items in strata.values():
            rng.shuffle(items)
        selected = []
        while len(selected) < target and any(strata.values()):
            for key in ordered_strata:
                items = strata[key]
                if items:
                    selected.append(items.pop(0))
                    if len(selected) >= target:
                        break
        plans.append(
            {
                "claim_id": claim_id,
                "target": target,
                "sufficient": len(canonical) >= target,
                "canonical_polarized_total": len(canonical),
                "selected_count": len(selected),
                "strata": [
                    {
                        "stance": key[0],
                        "published_month": key[1],
                        "available": len(
                            [
                                card
                                for card in canonical
                                if card.stance.value == key[0]
                                and card.published_on.strftime("%Y-%m") == key[1]
                            ]
                        ),
                    }
                    for key in ordered_strata
                ],
                "selected_reviews": [
                    {
                        "review_id": card.review_id,
                        "source_url": card.source_url,
                        "published_on": card.published_on.isoformat(),
                        "stance": card.stance.value,
                    }
                    for card in selected
                ],
            }
        )
    return {
        "schema_version": 1,
        "source_api": "crosspilot_l1_sampling_plan",
        "query": query,
        "market": "de",
        "snapshot_sha256": snapshot.snapshot_sha256,
        "seed": seed,
        "selection_method": "claim_id × stance × published_month deterministic round-robin",
        "unavailable_dimensions": [
            "star_rating",
            "variant",
        ],
        "dimension_note": "当前 EvidenceCard 契约无星级/变体字段；需由数据提供方另附，不得从文本猜测。",
        "market_effect_claim_allowed": False,
        "claims": plans,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="授权 L1 分层采样清单")
    parser.add_argument("--query", required=True)
    parser.add_argument("--snapshot-dir", type=Path, default=L1_SNAPSHOT_DIR)
    parser.add_argument("--target", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--claim-id", action="append", default=[],
                        help="本次采样的活跃卖点，可重复；默认全部")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.target < 1:
        parser.error("--target 必须大于 0")
    if args.output and args.output.resolve().is_relative_to(args.snapshot_dir.resolve()):
        parser.error("--output 不得写入 L1 快照目录")
    snapshot = load_l1_snapshot_data(args.query, args.snapshot_dir)
    if snapshot.notice:
        print(f"采样失败：{snapshot.notice}")
        return 1
    try:
        plan = build_sampling_plan(
            snapshot,
            args.query,
            target=args.target,
            seed=args.seed,
            claim_ids=tuple(args.claim_id),
        )
    except ValueError as exc:
        parser.exit(2, f"采样失败：{exc}\n")
    if not plan["claims"]:
        print("采样失败：快照中没有可采样的卖点评论")
        return 1
    serialized = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(f"采样清单已写入 {args.output}")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
