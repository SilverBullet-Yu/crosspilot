from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from crosspilot_api.domain.evidence import decide_by_claim
from crosspilot_api.services.case_readiness import ReadinessLevel, assess_case_readiness
from crosspilot_api.services.l1_import import (
    load_l1_snapshot_data,
    parse_import_document,
    write_snapshot,
)
from crosspilot_api.services.validation_round import (
    ValidationRoundRecord,
    load_validation_rounds_archive_data,
    write_validation_round,
)

ROOT = Path(__file__).resolve().parents[3]
SCOPE = ("internal_product_validation",)


def _load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sample_module = _load_script("crosspilot_sample_workflow", "plan_l1_sample.py")
eval_module = _load_script("crosspilot_eval_workflow", "eval_stance_baseline.py")


def test_contract_valid_case_pipeline_reaches_trial_complete(tmp_path: Path) -> None:
    cards = []
    for index in range(30):
        stance = "support" if index % 2 == 0 else "oppose"
        excerpt = (
            "Die Größe ist sehr gut."
            if stance == "support"
            else "Die Größe ist schlecht."
        )
        cards.append(
            {
                "review_id": f"workflow-{index}",
                "claim_id": "capacity",
                "excerpt": (
                    f"{excerpt} Testfall {index} "
                    f"{hashlib.sha256(str(index).encode()).hexdigest()}."
                ),
                "source_url": f"https://example.com/reviews/workflow-{index}",
                "published_on": "2026-11-01",
                "language": "de",
                "stance": stance,
                "stance_note": "测试构造的人工复核金标，不是真实消费者记录。",
            }
        )
    query, imported = parse_import_document(
        {
            "query": "旅行收纳包",
            "market": "de",
            "source_id": "contract-test",
            "authorization": "测试授权导出",
            "authorization_ref": "contract-test-2026",
            "authorization_scope": list(SCOPE),
            "cards": cards,
        }
    )
    snapshot_dir = tmp_path / "snapshots"
    snapshot_path = write_snapshot(
        imported,
        query=query,
        source_id="contract-test",
        authorization="测试授权导出",
        authorization_ref="contract-test-2026",
        authorization_scope=SCOPE,
        output_dir=snapshot_dir,
    )
    snapshot_sha256 = json.loads(snapshot_path.read_text(encoding="utf-8"))["record_sha256"]
    snapshot = load_l1_snapshot_data(query, snapshot_dir)

    plan = sample_module.build_sampling_plan(
        snapshot,
        query,
        target=30,
        claim_ids=("capacity",),
    )
    assert plan["claims"][0]["sufficient"] is True
    assert plan["claims"][0]["selected_count"] == 30

    evaluation = eval_module.evaluate_l1_snapshot(snapshot, query)
    assert evaluation["manual_gold_total"] == 30
    assert evaluation["claims"]["capacity"]["total"] == 30

    rounds_dir = tmp_path / "rounds"
    write_validation_round(
        ValidationRoundRecord(
            id="round-workflow-20261128",
            createdAt="2026-11-28T00:00:00Z",
            scenario="real",
            query=query,
            claimId="capacity",
            hypothesisTitle="容量越大越好",
            status="conflicting",
            evidenceRefs=(
                "claim_id=capacity; workflow-0: "
                "https://example.com/reviews/workflow-0"
            ),
            observation="测试构造：完成装载与取物任务。",
            decision="modify",
            rationale="测试构造：样本存在分歧。",
            nextAction="测试构造：扩大真实样本复测。",
            owner="测试运营角色",
            confirmation="confirmed",
            market="de",
            l1SnapshotSha256=snapshot_sha256,
        ),
        rounds_dir,
    )
    archive = load_validation_rounds_archive_data(rounds_dir)
    readiness = assess_case_readiness(
        query=query,
        market="de",
        cards=snapshot.cards,
        claim_decisions=decide_by_claim(snapshot.cards, ("capacity",)),
        rounds=archive.records,
        snapshot_sha256=snapshot.snapshot_sha256,
        rounds_archive_sha256=archive.archive_sha256,
    )
    assert readiness.level is ReadinessLevel.TRIAL_COMPLETE
    assert readiness.market_effect_claim_allowed is False
