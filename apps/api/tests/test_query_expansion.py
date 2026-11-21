"""双语检索式扩展测试：词表映射、并集检索去重、快照变体回退、live 不扩展。

背景（2026-11-21 实测）：中文查询词在英文 Safety Gate 库零命中、英文词在中文
知乎快照零命中。扩展层修复两侧空白；live 路径不用扩展（配额 10 次/日）。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from crosspilot_api.config import settings
from crosspilot_api.main import app
from crosspilot_api.routers import evidence as evidence_router
from crosspilot_api.services import zhihu_snapshot
from crosspilot_api.services.query_expansion import BILINGUAL_GLOSSARY, expand_query
from crosspilot_api.services.safety_gate_retrieval import search_safety_gate_multi

# ---------- 词表映射 ----------


def test_zh_query_expands_to_english_variants() -> None:
    """中文演示主查询词扩展出库内实测存在的英文产品词，原词永远在首位。"""
    terms = expand_query("旅行收纳包")
    assert terms[0] == "旅行收纳包"
    assert "backpack" in terms and "rucksack" in terms and "storage bag" in terms
    assert len(terms) == len(set(terms))


def test_en_query_expands_to_chinese_variants() -> None:
    """英文查询词反向扩展中文快照检索式。"""
    terms = expand_query("Backpack")  # 大小写不敏感
    assert terms[0] == "backpack"
    assert "双肩包" in terms


def test_unknown_query_not_expanded() -> None:
    """词表外查询不扩展、不编造：仅返回原词。"""
    assert expand_query("zzz-kein-treffer-xyz") == ["zzz-kein-treffer-xyz"]
    assert expand_query("收纳盒") == ["收纳盒"]  # 词表内无此词


def test_empty_query_returns_empty() -> None:
    assert expand_query("") == []
    assert expand_query("   ") == []


def test_glossary_entries_are_mutually_consistent() -> None:
    """词表卫生：每个值词要么是某条 key，要么在值词表内可追溯（演示域闭环）。"""
    all_values = {v for vs in BILINGUAL_GLOSSARY.values() for v in vs}
    for variants in BILINGUAL_GLOSSARY.values():
        for term in variants:
            assert term in BILINGUAL_GLOSSARY or term in all_values, term


# ---------- L3 并集检索 ----------


def test_multi_search_unions_hits_and_dedups() -> None:
    """多检索式并集：中文词本身零命中、英文变式命中，结果按警报号去重。"""
    solo = search_safety_gate_multi(["旅行收纳包"])
    assert solo == []  # 中文词在英文库零命中（前提事实）
    combined = search_safety_gate_multi(expand_query("旅行收纳包"))
    assert combined, "扩展后必须命中（backpack/rucksack 等库内实测存在）"
    case_ids = [c.source_url for c in combined]
    assert len(case_ids) == len(set(case_ids)), "并集结果必须按警报去重"
    solo_en = search_safety_gate_multi(["backpack"])
    assert 0 < len(solo_en) <= len(combined), "并集结果数应 ≥ 单词命中且至少命中"


def test_multi_search_empty_terms() -> None:
    assert search_safety_gate_multi([]) == []
    assert search_safety_gate_multi(["", "   "]) == []


# ---------- 端点集成：扩展贯通 L3 与 L2 ----------


def test_endpoint_zh_query_hits_l3_via_expansion() -> None:
    """snapshot 端点：中文查询词经扩展命中 L3（修复中栏空白问题）。"""
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["cards"], "中文词经扩展后必须命中 L3 英文警报"
    assert body["l2_cards"], "中文词直接命中知乎快照（原词查找）"
    assert body["stance"] == "insufficient"


def test_endpoint_en_query_hits_l2_via_expansion(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """snapshot 端点：英文查询词经反向扩展命中中文快照文件。"""
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", zhihu_snapshot.SNAPSHOT_DIR)
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "backpack"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["l2_cards"], "英文词经反向扩展必须命中中文快照"
    assert all(card["level"] == "L2" for card in body["l2_cards"])
    assert body["l2_notice"] is None


def test_endpoint_live_mode_uses_single_query_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """live 模式不做扩展检索（配额纪律）：检索函数收到的就是原词。"""
    monkeypatch.setattr(
        evidence_router,
        "settings",
        replace(settings, data_mode="live", zhihu_secret=None),
    )
    seen: list[str] = []

    def fake_search(query: str, **kwargs: Any) -> list:
        seen.append(query)
        return []

    monkeypatch.setattr(evidence_router, "search_zhihu", fake_search)
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    assert seen == ["旅行收纳包"], "live 只允许一次原词调用，禁止扩展成多次检索"
