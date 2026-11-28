from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from crosspilot_api.domain.evidence import EvidenceCard, EvidenceLevel, Stance, StanceVotes
from crosspilot_api.services.l1_import import L1SnapshotData
from crosspilot_api.services.stance_llm import LLMStanceResult

EVAL_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "eval_stance_baseline.py"


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("crosspilot_eval_stance", EVAL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


eval_module = _load_eval_module()


def _manual_l1_card(
    index: int,
    *,
    excerpt: str,
    stance: Stance,
    rule: Stance,
) -> EvidenceCard:
    return EvidenceCard(
        excerpt=excerpt,
        source_url=f"https://example.com/reviews/{index}",
        language="de",
        published_on=date(2026, 11, 1),
        level=EvidenceLevel.L1,
        sample_size=1,
        stance=stance,
        stance_votes=StanceVotes(rule=rule),
        annotator_agreement=stance is rule,
        classification_method="manual",
        classification_note="人工复核：卖点立场已确认。",
        review_required=False,
        review_reasons=("人工复核已完成",),
        review_id=f"review-{index}",
        claim_id="capacity",
        aspect_terms=("größe",),
        market="de",
        source_id="brand-export",
        authorization="品牌授权导出",
        authorization_ref="brand-2026",
    )


def test_l1_evaluation_uses_manual_claim_gold_and_snapshot_hash() -> None:
    cards = [
        _manual_l1_card(
            0,
            excerpt="Die Größe ist sehr gut.",
            stance=Stance.SUPPORT,
            rule=Stance.SUPPORT,
        ),
        _manual_l1_card(
            1,
            excerpt="Die Größe ist schlecht.",
            stance=Stance.SUPPORT,
            rule=Stance.OPPOSE,
        ),
    ]
    report = eval_module.evaluate_l1_snapshot(
        L1SnapshotData(cards, ("internal_product_validation",), snapshot_sha256="a" * 64),
        "旅行收纳包",
    )
    assert report["snapshot_sha256"] == "a" * 64
    assert report["relevant_total"] == 2
    assert report["manual_gold_total"] == 2
    metrics = report["claims"]["capacity"]
    assert metrics["total"] == 2
    assert metrics["accuracy"] == 0.5
    rendered = eval_module.render_l1_report(report)
    assert "人工复核金标：2 条" in rendered
    assert "不代表总体消费者偏好或市场效果" in rendered
    payload = eval_module.l1_report_payload(report)
    assert payload["market_effect_claim_allowed"] is False
    assert "excerpt" not in json.dumps(payload, ensure_ascii=False)


def test_l1_evaluation_rejects_missing_manual_gold() -> None:
    card = _manual_l1_card(
        0,
        excerpt="Die Größe ist sehr gut.",
        stance=Stance.SUPPORT,
        rule=Stance.SUPPORT,
    )
    rule_card = EvidenceCard(
        **{
            **card.__dict__,
            "classification_method": "rule",
            "classification_note": None,
            "review_required": True,
            "review_reasons": ("规则待复核",),
        }
    )
    with pytest.raises(ValueError, match="人工复核 L1 金标"):
        eval_module.evaluate_l1_snapshot(
            L1SnapshotData([rule_card], ("internal_product_validation",)),
            "旅行收纳包",
        )


def test_llm_cache_isolated_by_endpoint_and_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "REPO_ROOT", tmp_path)
    calls = 0

    def classify(text: str, **_: object) -> LLMStanceResult:
        nonlocal calls
        calls += 1
        return LLMStanceResult(
            stance=Stance.SUPPORT,
            reason="明确正面",
            model="test-model",
            evidence=text,
        )

    monkeypatch.setattr(eval_module, "classify_stance_with_fallback", classify)
    first, first_stats = eval_module.make_llm_classifier("test-model", "https://a.example/v1")
    assert first("Sehr gut") is Stance.SUPPORT
    assert first("Sehr gut") is Stance.SUPPORT
    assert calls == 1
    assert first_stats == {
        "hit": 1,
        "fresh": 1,
        "fallback": 0,
        "fabricated_evidence": 0,
        "with_evidence": 1,
    }

    second, second_stats = eval_module.make_llm_classifier(
        "test-model", "https://b.example/v1"
    )
    assert second("Sehr gut") is Stance.SUPPORT
    assert calls == 2
    assert second_stats["fresh"] == 1
    assert second_stats["hit"] == 0

    monkeypatch.setattr(eval_module, "STANCE_PROMPT_FINGERPRINT", "f" * 64)
    third, third_stats = eval_module.make_llm_classifier(
        "test-model", "https://a.example/v1"
    )
    assert third("Sehr gut") is Stance.SUPPORT
    assert calls == 3
    assert third_stats["fresh"] == 1
    assert third_stats["hit"] == 0

    records = [
        json.loads(line)
        for path in (tmp_path / "data" / "sources" / "_eval_cache").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 3
    assert all(record["fallback"] is False for record in records)


def test_model_cache_namespace_does_not_collide() -> None:
    assert eval_module.model_cache_namespace("a/b") != eval_module.model_cache_namespace("a-b")


def test_claim_llm_cache_isolated_by_claim_and_terms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "REPO_ROOT", tmp_path)
    calls: list[tuple[str, str, tuple[str, ...]]] = []

    def classify(
        text: str,
        claim_id: str,
        aspect_terms: tuple[str, ...],
        **_: object,
    ) -> LLMStanceResult:
        calls.append((text, claim_id, aspect_terms))
        return LLMStanceResult(
            stance=Stance.SUPPORT,
            reason="明确正面",
            model="test-model",
            evidence=text,
        )

    monkeypatch.setattr(eval_module, "classify_claim_stance_with_fallback", classify)
    classifier, stats = eval_module.make_claim_llm_classifier(
        "test-model", "https://a.example/v1"
    )
    assert classifier("Sehr gut", "capacity", ("größe",)) is Stance.SUPPORT
    assert classifier("Sehr gut", "capacity", ("größe",)) is Stance.SUPPORT
    assert classifier("Sehr gut", "features", ("fach",)) is Stance.SUPPORT
    assert len(calls) == 2
    assert stats == {
        "hit": 1,
        "fresh": 2,
        "fallback": 0,
        "fabricated_evidence": 0,
        "with_evidence": 2,
    }
    records = [
        json.loads(line)
        for path in (tmp_path / "data" / "sources" / "_eval_cache").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert all("reason" not in record and "evidence" not in record for record in records)
    assert all(record["model"] == "test-model" for record in records)


def test_claim_cache_short_circuit_is_not_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "REPO_ROOT", tmp_path)

    def classify(
        text: str,
        claim_id: str,
        aspect_terms: tuple[str, ...],
        **_: object,
    ) -> LLMStanceResult:
        return LLMStanceResult(
            stance=Stance.INSUFFICIENT,
            reason="未调用模型",
            model="test-model",
            llm_called=False,
        )

    monkeypatch.setattr(eval_module, "classify_claim_stance_with_fallback", classify)
    classifier, stats = eval_module.make_claim_llm_classifier(
        "test-model", "https://a.example/v1"
    )
    assert classifier("Text", "features", ("fach",)) is Stance.INSUFFICIENT
    assert stats["fresh"] == 0
    assert not list((tmp_path / "data" / "sources" / "_eval_cache").glob("*.jsonl"))


def test_claim_rule_fallback_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "REPO_ROOT", tmp_path)
    calls = 0

    def classify(
        text: str,
        claim_id: str,
        aspect_terms: tuple[str, ...],
        **_: object,
    ) -> LLMStanceResult:
        nonlocal calls
        calls += 1
        return LLMStanceResult(
            stance=Stance.OPPOSE,
            reason="规则基线回退",
            model="test-model",
            fallback_used=True,
            fallback_reason="网络失败",
        )

    monkeypatch.setattr(eval_module, "classify_claim_stance_with_fallback", classify)
    classifier, stats = eval_module.make_claim_llm_classifier(
        "test-model", "https://a.example/v1"
    )
    assert classifier("Schlecht", "capacity", ("größe",)) is Stance.OPPOSE
    assert classifier("Schlecht", "capacity", ("größe",)) is Stance.OPPOSE
    assert calls == 2
    assert stats["fallback"] == 2
    assert not list((tmp_path / "data" / "sources" / "_eval_cache").glob("*.jsonl"))


def test_rule_fallback_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "REPO_ROOT", tmp_path)
    calls = 0

    def classify(text: str, **_: object) -> LLMStanceResult:
        nonlocal calls
        calls += 1
        return LLMStanceResult(
            stance=Stance.OPPOSE,
            reason="规则基线回退",
            model="test-model",
            fallback_used=True,
            fallback_reason="网络失败",
        )

    monkeypatch.setattr(eval_module, "classify_stance_with_fallback", classify)
    classifier, stats = eval_module.make_llm_classifier("test-model", "https://a.example/v1")
    assert classifier("Schlecht") is Stance.OPPOSE
    assert classifier("Schlecht") is Stance.OPPOSE
    assert calls == 2
    assert stats["fresh"] == 2
    assert stats["fallback"] == 2
    assert stats["hit"] == 0
    assert not list((tmp_path / "data" / "sources" / "_eval_cache").glob("*.jsonl"))


def test_fixed_seed_sample_is_reproducible_and_keeps_source_order() -> None:
    rows = [
        (f"review-{index}", ("support", "oppose", "insufficient")[index % 3])
        for index in range(100)
    ]
    first = eval_module.sample_rows(rows, 20, 42)
    repeated = eval_module.sample_rows(rows, 20, 42)
    different = eval_module.sample_rows(rows, 20, 43)
    assert first == repeated
    assert first != different
    indices = [int(text.removeprefix("review-")) for text, _ in first]
    assert indices == sorted(indices)


def test_llm_report_records_sample_and_inference_boundaries(tmp_path: Path) -> None:
    rows = [("Sehr gut", "support"), ("Schlecht", "oppose")]
    metrics = eval_module.evaluate(rows, lambda text: eval_module.classify_stance(text).stance)
    buckets = eval_module.error_buckets(metrics["results"])
    dataset = {
        "out_md": tmp_path / "llm_baseline_eval.md",
        "domain": "商品域",
        "gold_rule": "测试金标",
    }
    stats = {
        "hit": 0,
        "fresh": 2,
        "fallback": 0,
        "fabricated_evidence": 0,
        "with_evidence": 2,
    }
    repro_command = (
        ".venv/Scripts/python.exe scripts/eval_stance_baseline.py "
        "--classifier llm --dataset marc --sample-size 2 --seed 42"
    )
    eval_module.write_llm_report(
        dataset,
        metrics,
        buckets,
        "test-model",
        stats,
        2,
        "固定种子随机抽样 2 条（seed=42）",
        "a" * 64,
        "1234567890abcdef",
        repro_command,
    )
    report = (tmp_path / "llm_baseline_eval.md").read_text(encoding="utf-8")
    assert date.today().isoformat() in report
    assert "固定种子随机抽样 2 条（seed=42）" in report
    assert "不是 CrossPilot 的卖点级 aspect 标签" in report
    assert "规则回退不缓存" in report
    assert repro_command in report
    assert "a" * 64 in report
