"""证据管线测试：品类过滤、关键词检索、响应包络、演示状态与 schema 校验。

品类过滤条数以 CSV 实际为准（README 的 488 未计入 Hobby/sports equipment，见服务常量注释）。
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from crosspilot_api.config import REPO_ROOT, settings
from crosspilot_api.domain.evidence import EvidenceLevel, Stance
from crosspilot_api.main import app
from crosspilot_api.routers.evidence import EvidenceCardOut
from crosspilot_api.services.datasets import Tier, assert_demand_side
from crosspilot_api.services.demo_evidence import (
    DEMO_CONFLICT_CARDS,
    DEMO_L1_SOURCE_KEY,
    DEMO_LIMITED_CARDS,
    DEMO_QUERY,
)
from crosspilot_api.services.safety_gate_retrieval import (
    EXPECTED_NEAR_NEIGHBOR_COUNT,
    NEAR_NEIGHBOR_CATEGORIES,
    build_real_questions,
    get_snapshot,
    parse_publication_date,
    resolve_source_url,
    search_safety_gate,
)

CSV_PATH = REPO_ROOT / "data" / "sources" / "eu_safety_gate" / "safety_gate_de_alerts_2021_2026.csv"

# evidence-card.schema.json 的字段约定（手写断言比 jsonschema 依赖更稳，.venv 未必有该库）
CARD_REQUIRED = ("excerpt", "source_url", "language", "published_on", "level", "sample_size")
# ADR-0005 卡级扩展字段（全 optional）：dedup / stance_votes / annotator_agreement /
# grade / downgrade_reasons；判定级字段（state/interval/gate）在包络 decision，不进卡。
CARD_ALLOWED = set(CARD_REQUIRED) | {
    "stance",
    "is_demo_data",
    "dedup",
    "stance_votes",
    "annotator_agreement",
    "grade",
    "downgrade_reasons",
}
OFFICIAL_URL_PREFIX = "https://ec.europa.eu/safety-gate-alerts/screen/webReport/alertDetail/"

#: raw/ 原始 XML 不入库（.gitignore 策略，凭 provenance.csv 的 SHA-256 与 URL 复现）。
#: 在位时 L3 卡 source_url 取官方 <reference> 深链；缺失（fresh clone）时走服务
#: docstring 声明的降级 URL（契约由 test_source_url_prefers_official_reference_and_
#: fallback_is_declared 独立覆盖，两种形态均为官方域内链接）。
_SAFETY_GATE_RAW_AVAILABLE = (
    REPO_ROOT / "data" / "sources" / "eu_safety_gate" / "raw"
).is_dir()


def assert_card_matches_schema(card: dict[str, Any]) -> None:
    """手写校验 evidence-card.schema.json：六必现字段 + 枚举 + additionalProperties=false。"""
    for key in CARD_REQUIRED:
        assert key in card, f"缺必现字段 {key}"
        assert card[key] not in (None, ""), f"字段 {key} 不得为空"
    assert set(card) <= CARD_ALLOWED, f"出现 schema 之外的键: {set(card) - CARD_ALLOWED}"
    assert card["level"] in {"L1", "L2", "L3"}
    assert card["stance"] in {"support", "oppose", "insufficient"}
    assert card["sample_size"] is None or isinstance(card["sample_size"], int)
    assert isinstance(card["is_demo_data"], bool)
    assert str(card["source_url"]).startswith("https://")
    datetime.strptime(card["published_on"], "%Y-%m-%d")  # schema format=date
    # ADR-0005 卡级扩展字段轻校验（optional；出现时结构须合规）
    dedup = card.get("dedup")
    if dedup is not None:
        assert set(dedup) == {"cluster_id", "dup_count", "is_canonical"}
        assert isinstance(dedup["cluster_id"], int) and dedup["cluster_id"] >= 0
        assert isinstance(dedup["dup_count"], int) and dedup["dup_count"] >= 1
        assert isinstance(dedup["is_canonical"], bool)
    votes = card.get("stance_votes")
    if votes is not None:
        assert set(votes) == {"rule", "llm"}
        assert votes["rule"] in {"support", "oppose", "insufficient"}
        assert votes["llm"] in {"support", "oppose", "insufficient", None}
    agreement = card.get("annotator_agreement")
    assert agreement is None or isinstance(agreement, bool)
    assert card.get("grade") in {None, "high", "moderate", "low", "very-low"}
    reasons = card.get("downgrade_reasons")
    assert isinstance(reasons, list) and all(isinstance(r, str) for r in reasons)


def _read_subset_rows() -> list[dict[str, str]]:
    """独立于服务重读 CSV，交叉验证品类过滤口径。"""
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if (row.get("category") or "") in NEAR_NEIGHBOR_CATEGORIES
        ]


def test_near_neighbor_filter_count() -> None:
    """品类过滤条数以 CSV 实际字符串为准：五品类合计 519。

    README 写 488 = Toys 271 + Childcare 94 + Chemical products 66 + Clothing 57，
    未计入 Hobby/sports equipment 31；按任务指定的五品类过滤，实际为 519。
    """
    assert len(NEAR_NEIGHBOR_CATEGORIES) == 5
    assert EXPECTED_NEAR_NEIGHBOR_COUNT == 519
    assert len(get_snapshot()) == EXPECTED_NEAR_NEIGHBOR_COUNT == len(_read_subset_rows())


def test_snapshot_case_numbers_match_csv_subset() -> None:
    rows = _read_subset_rows()
    assert {row["case_number"] for row in rows} == {rec.case_number for rec in get_snapshot()}


def test_search_hits_case_insensitive() -> None:
    lower = search_safety_gate("puzzle")
    assert lower, "『puzzle』在近邻品类子集应有命中"
    assert lower == search_safety_gate("PUZZLE")  # 大小写不敏感
    for card in lower:
        assert card.level is EvidenceLevel.L3
        assert card.language == "en"
        assert card.stance is Stance.INSUFFICIENT  # L3 卡 stance 恒为 insufficient
        assert card.sample_size == 1
        assert card.is_demo_data is False
        if _SAFETY_GATE_RAW_AVAILABLE:
            # 本地 raw 在位：URL 逐字取自 raw XML 官方 <reference> 字段
            assert card.source_url.startswith(OFFICIAL_URL_PREFIX)
        else:
            # fresh clone（raw 策略性不入库）：降级 URL 仍为官方域内链接
            assert card.source_url.startswith("https://ec.europa.eu/")


def test_search_other_keywords() -> None:
    assert search_safety_gate("plush")
    assert search_safety_gate("drawstring")


def test_search_empty_query_returns_empty_list() -> None:
    assert search_safety_gate("") == []
    assert search_safety_gate("   ") == []


def test_search_zero_hit_returns_empty_list() -> None:
    assert search_safety_gate("zzz-kein-treffer-xyz") == []
    # README 明言「旅行收纳包无独立品类」，真实子集应零命中
    assert search_safety_gate("packing cube") == []


def test_published_on_parsed_from_dd_mm_yyyy() -> None:
    assert parse_publication_date("08/01/2021") == date(2021, 1, 8)


def test_published_on_matches_csv_row() -> None:
    """快照卡的日期必须与主表原始值一致，且全部落在数据窗口内。"""
    rows = _read_subset_rows()
    records = {rec.case_number: rec for rec in get_snapshot()}
    row = rows[0]
    assert records[row["case_number"]].card.published_on == parse_publication_date(
        row["publication_date"]
    )
    for rec in get_snapshot():
        assert date(2020, 12, 31) < rec.card.published_on < date(2027, 1, 1)


def test_source_url_prefers_official_reference_and_fallback_is_declared() -> None:
    # 官方 <reference> 字段优先，逐字采用
    assert resolve_source_url("X", {"X": "https://example.gov/x"}) == "https://example.gov/x"
    # 降级 URL：仅在 raw/ 缺失时占位，格式未经验证（如实声明于服务 docstring）
    assert resolve_source_url("A12/00003/21", {}) == (
        "https://ec.europa.eu/safety-gate-alerts/public/web-notification/A12%2F00003%2F21"
    )


def test_every_real_card_matches_evidence_card_schema() -> None:
    """全量 519 张 L3 卡逐一过 schema 校验（手写断言，不依赖 jsonschema）。"""
    for rec in get_snapshot():
        payload = EvidenceCardOut.from_card(rec.card).model_dump(mode="json")
        assert_card_matches_schema(payload)
        assert payload["is_demo_data"] is False


def test_real_endpoint_envelope() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "puzzle"})
    assert resp.status_code == 200
    body = resp.json()
    # 2026-11-21 追加知乎 L2 两个可选字段（向后兼容）；2026-11-22 ADR-0005 判定链
    # 追加 decision（判定级字段落包络，不进卡片 schema），包络集合随之 +3；
    # 既有字段语义不变，断言强度不降（仍锁定全字段集合防漂移）。
    assert set(body) == {
        "query",
        "market",
        "data_mode",
        "scenario",
        "stance",
        "cards",
        "questions",
        "generated_at",
        "decision",
        "l2_cards",
        "l2_notice",
    }
    assert body["query"] == "puzzle"
    assert body["market"] == "de"
    assert body["data_mode"] == settings.data_mode
    assert body["scenario"] == "real"
    assert body["stance"] == "insufficient"  # L3-only，恒为证据不足（gate=no_l1）
    decision = body["decision"]
    assert decision["state"] == "insufficient"
    assert decision["gate_status"] == "no_l1"
    assert decision["support_interval"] is None
    assert decision["n_l1"] == 0
    assert decision["power_note"]  # 功效注记非空（可追溯）
    assert body["cards"]
    for card in body["cards"]:
        assert_card_matches_schema(card)
    assert body["questions"]
    assert all("待验证" in question for question in body["questions"])
    datetime.fromisoformat(body["generated_at"])  # ISO8601 可解析


def test_real_endpoint_empty_query_and_zero_hit() -> None:
    with TestClient(app) as client:
        for query in ("", "zzz-kein-treffer-xyz"):
            resp = client.get("/api/evidence", params={"query": query})
            assert resp.status_code == 200
            body = resp.json()
            assert body["cards"] == []  # 空查询/零命中不报错，返回空列表
            assert body["stance"] == "insufficient"
            assert body["questions"]  # 缺少有效数据也必须给出待验证问题


def test_demo_conflict_scenario() -> None:
    """ADR-0005 三状态演示：15:15 去重后区间重叠 → conflicting（并排展示）。

    两条重复摘录聚入既有簇（R2：计数不虚增），去重摘要进 decision 可追溯。
    """
    with TestClient(app) as client:
        resp = client.get("/api/evidence/demo", params={"scenario": "conflict"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"] == "demo_conflict"
    assert body["query"] == DEMO_QUERY
    assert body["stance"] == "conflicting"  # 冲突为独立判定状态，不降级不并值
    decision = body["decision"]
    assert decision["state"] == "conflicting"
    assert decision["gate_status"] == "pass"
    assert decision["n_polarized"] == 30  # 去重后有极性样本
    assert decision["dedup_clusters"] == 30
    assert decision["dedup_duplicated"] == 2  # 两条重复摘录被并簇
    # 区间重叠可见：两份额区间均含 0.5 附近（可追溯的冲突依据）
    assert decision["support_interval"] is not None
    assert decision["oppose_interval"] is not None
    assert decision["support_interval"]["lo"] <= 0.5 <= decision["oppose_interval"]["hi"]
    stances = {card["stance"] for card in body["cards"]}
    assert stances == {"support", "oppose"}  # 支持与反对并存
    assert len(body["cards"]) == 32  # 30 簇 + 2 条重复摘录
    assert all(card["is_demo_data"] for card in body["cards"])
    assert all(card["level"] == "L1" for card in body["cards"])
    # 去重结果回填卡面：两条重复摘录 is_canonical=False（逐卡可审计）；
    # 二者均并入被复制的 O1 簇 → 该簇 dup_count=3（复制 1 条 + 变体 1 条 + 原卡）
    non_canonical = [
        card for card in body["cards"] if card["dedup"] and not card["dedup"]["is_canonical"]
    ]
    assert len(non_canonical) == 2
    assert all(card["dedup"]["dup_count"] == 3 for card in non_canonical)
    for card in body["cards"]:
        assert_card_matches_schema(card)
    assert body["questions"]


def test_demo_limited_scenario() -> None:
    """ADR-0005 三状态演示：21:9 过门禁、份额 0.7 下界 0.521 刚过决定线 → supported。

    「有限支持」的公式化含义 = 支持占优但区间宽（0.52–0.83）。
    """
    with TestClient(app) as client:
        resp = client.get("/api/evidence/demo", params={"scenario": "limited"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"] == "demo_limited"
    assert body["stance"] == "supported"  # 已有有限支持（公式判定，非文案修饰）
    decision = body["decision"]
    assert decision["state"] == "supported"
    assert decision["gate_status"] == "pass"
    assert decision["n_polarized"] == 30
    assert decision["dedup_clusters"] == 30
    assert decision["dedup_duplicated"] == 0
    assert decision["support_interval"]["lo"] == pytest.approx(0.521, abs=1e-3)
    assert decision["support_interval"]["hi"] == pytest.approx(0.833, abs=1e-3)
    stances = {card["stance"] for card in body["cards"]}
    assert stances == {"support", "oppose"}  # 21 support + 9 oppose
    assert len(body["cards"]) == 30
    assert all(card["is_demo_data"] for card in body["cards"])
    for card in body["cards"]:
        assert_card_matches_schema(card)
    assert body["questions"]


def test_demo_scenario_validation() -> None:
    """非法或缺失的 scenario 直接 422，不做静默降级。"""
    with TestClient(app) as client:
        assert client.get("/api/evidence/demo", params={"scenario": "real"}).status_code == 422
        assert client.get("/api/evidence/demo").status_code == 422  # scenario 必填


def test_demo_cards_declared_l1_source_passes_gate() -> None:
    """demo 声明源为 amazon_reviews_2023，闸门放行且为 L1；卡片全部显式演示标识。"""
    source = assert_demand_side(DEMO_L1_SOURCE_KEY)
    assert source.tier is Tier.L1
    for card in (*DEMO_CONFLICT_CARDS, *DEMO_LIMITED_CARDS):
        assert card.is_demo_data is True
        assert card.level is EvidenceLevel.L1


def test_assert_demand_side_rejects_safety_gate() -> None:
    """Safety Gate 为 L3，不得写入消费者证据侧（硬约束 1 在闸门的落点）。"""
    with pytest.raises(PermissionError):
        assert_demand_side("eu_safety_gate")


def test_build_real_questions_marks_inference_layer() -> None:
    """问题模板必须落在「推断/待验证假设」层，不得编造统计数字。"""
    for questions in (build_real_questions("puzzle", 8), build_real_questions("", 0)):
        assert questions
        assert all("待验证" in question for question in questions)
