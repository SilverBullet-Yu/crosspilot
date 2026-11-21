"""知乎检索适配器测试（L2 中文侧）：快照/live 双路径、合规红线、语义红线。

覆盖面：
- 快照：加载与 schema 校验、缺失/损坏 → 空列表 + 非空降级提示（ADR-0002 决策 4）、
  演示样例全量 is_demo_data=true、演示/真实标识不得混排、摘录 ≤300 红线。
- 语义红线（硬约束 1）：L2 卡加入后 resolve_stance 结果不变（insufficient）。
- live 适配器（全部走 httpx.MockTransport，零真实 API 调用）：无凭据明确报错、
  429 / Code=30001 → QuotaExhaustedError 且消息含降级指引、PII 与全文剔除、
  作者匿名化、鉴权失败、请求形状（Bearer + 秒级时间戳）。
- 端点集成（TestClient）：/api/evidence 的 l2_cards / l2_notice 追加字段，
  snapshot 与 live 两种模式；live 模式经 monkeypatch 注入，不触网。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from crosspilot_api.config import REPO_ROOT, settings
from crosspilot_api.domain.evidence import EvidenceCard, EvidenceLevel, Stance, resolve_stance
from crosspilot_api.main import app
from crosspilot_api.routers import evidence as evidence_router
from crosspilot_api.services import zhihu_client, zhihu_snapshot
from crosspilot_api.services.zhihu_client import (
    EXCERPT_MAX_CHARS,
    ZHIHU_SEARCH_URL,
    QuotaExhaustedError,
    ZhihuCredentialError,
    ZhihuNetworkError,
    ZhihuResponseError,
    anonymize_author,
    search_zhihu,
    search_zhihu_extractions,
)
from crosspilot_api.services.zhihu_snapshot import load_zhihu_snapshot, snapshot_path

#: 演示撰写的快照样例（已迁入测试夹具；data/snapshots/zhihu/ 现存真实快照）。
SAMPLE_SNAPSHOT = REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "zhihu" / "旅行收纳包.json"
#: 演示样例所在的夹具目录（loader 的 SNAPSHOT_DIR 指到这里即可加载样例）。
SAMPLE_SNAPSHOT_DIR = REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "zhihu"
#: 真实快照（2026-11-18 CLI 采集成果转录，见 data/snapshots/README.md）。
REAL_SNAPSHOT = REPO_ROOT / "data" / "snapshots" / "zhihu" / "旅行收纳包.json"

#: 降级指引原文（ADR-0002 决策 4 + 任务约定文案）。
GUIDANCE_FRAGMENT = "当前为实测 10 次/日，演示请切回 snapshot 模式"

FAKE_SECRET = "test-secret"


# ---------- mock 构造 ----------


def _item(**overrides: Any) -> dict[str, Any]:
    """一条符合文档规格的搜索结果。ContentText 默认埋入 PII 与超长文本供清洗断言。"""
    base: dict[str, Any] = {
        "Title": "旅行收纳包出海德国的选品思路",
        "ContentType": "Answer",
        "ContentID": "1234567890",
        "ContentText": (
            "德国买家重视清晰的产品参数，决策周期长。"
            "有意向交流请联系 buyer@example.com 或来电 13812345678，"
            "座机 010-1234567 也可以。" + "细节补充。" * 80  # 远超 300 字符
        ),
        "Url": "https://www.zhihu.com/answer/1234567890?utm_medium=openapi_platform",
        "CommentCount": 5,
        "VoteUpCount": 42,
        "AuthorName": "某跨境从业者",
        "AuthorAvatar": "https://picx.zhimg.com/avatar.jpg",
        "AuthorBadge": "",
        "AuthorBadgeText": "",
        "EditTime": 1748355858,
        "AuthorityLevel": "2",
        "RankingScore": 0.9,
    }
    base.update(overrides)
    return base


def _payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"Code": 0, "Message": "success", "Data": {"HasMore": False, "Items": items}}


def _transport(
    payload: dict[str, Any] | None = None,
    status_code: int = 200,
) -> httpx.MockTransport:
    body = payload if payload is not None else _payload([_item()])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return httpx.MockTransport(handler)


def _live_cards() -> list[EvidenceCard]:
    """live 正常路径注入的 L2 卡（经适配器真实清洗链构造，不手工拼卡）。"""
    return search_zhihu("旅行收纳包", secret=FAKE_SECRET, transport=_transport())


# ---------- 快照：加载与 schema 校验 ----------


def test_sample_snapshot_loads_and_matches_schema(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """演示样例快照可加载，卡字段对齐 evidence-card.schema.json + is_demo_data。"""
    import json

    doc = json.loads(SAMPLE_SNAPSHOT.read_text(encoding="utf-8"))
    assert set(("generated_at_utc", "source_api", "cards")) <= set(doc)
    assert doc["source_api"] == ZHIHU_SEARCH_URL
    assert doc["is_demo_data"] is True
    assert doc["cards"]
    for card in doc["cards"]:
        for key in ("excerpt", "source_url", "language", "published_on", "level", "sample_size"):
            assert key in card
        assert card["level"] == "L2"
        assert card["language"] == "zh-CN"
        assert card["stance"] == "insufficient"
        assert card["is_demo_data"] is True
        assert isinstance(card["is_demo_data"], bool)
        assert card["source_url"].startswith("https://")
        assert len(card["excerpt"]) <= EXCERPT_MAX_CHARS
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", SAMPLE_SNAPSHOT_DIR)
    cards, notice = load_zhihu_snapshot("旅行收纳包")
    assert notice is None
    assert len(cards) == len(doc["cards"])
    assert all(card.level is EvidenceLevel.L2 for card in cards)
    assert all(card.language == "zh-CN" for card in cards)
    assert all(card.stance is Stance.INSUFFICIENT for card in cards)


def test_sample_snapshot_all_demo_data(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """演示样例快照：顶层与全部卡 is_demo_data=true，不含真实标识卡。"""
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", SAMPLE_SNAPSHOT_DIR)
    cards, notice = load_zhihu_snapshot("旅行收纳包")
    assert notice is None
    assert cards, "演示样例快照必须能加载出卡片"
    assert all(card.is_demo_data for card in cards)


def test_real_snapshot_all_real_data() -> None:
    """真实快照（11-18 CLI 采集转录）：全部卡 is_demo_data=false，发布日期为真实采集值。"""
    cards, notice = load_zhihu_snapshot("旅行收纳包")
    assert notice is None
    assert cards, "真实快照必须能加载出卡片"
    assert all(not card.is_demo_data for card in cards)
    assert all(card.level is EvidenceLevel.L2 for card in cards)
    assert all(card.stance is Stance.INSUFFICIENT for card in cards)
    dates = sorted(str(card.published_on) for card in cards)
    assert dates == ["2026-07-29", "2026-10-10", "2026-11-11"]


def test_snapshot_missing_returns_empty_with_notice(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """快照缺失 → 空列表 + 非空降级提示（ADR-0002 决策 4：禁止静默空结果）。"""
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", tmp_path)
    cards, notice = load_zhihu_snapshot("旅行收纳包")
    assert cards == []
    assert notice
    assert "快照缺失" in notice
    assert "capture_zhihu_snapshot.py" in notice


def test_snapshot_corrupt_returns_empty_with_notice(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """快照损坏（非法 JSON / 缺顶层字段 / 缺卡字段）→ 空列表 + 非空提示。"""
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", tmp_path)
    cases: list[str] = [
        "not-json-at-all{",
        '{"generated_at_utc": "2026-11-21T00:00:00Z"}',  # 缺 source_api / cards
        '{"generated_at_utc": "t", "source_api": "u", "cards": [{"excerpt": "x"}]}',  # 卡缺字段
    ]
    for index, content in enumerate(cases):
        broken = tmp_path / f"损坏{index}.json"
        broken.write_text(content, encoding="utf-8")
        monkeypatch.setattr(zhihu_snapshot, "snapshot_path", lambda q, p=broken: p)
        cards, notice = load_zhihu_snapshot("损坏")
        assert cards == [], f"case {index}"
        assert notice and "快照损坏" in notice, f"case {index}"


def test_snapshot_rejects_mixed_demo_flags(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """演示与真实标识不得同文件混排（CONSTRAINTS 第四节）。"""
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", tmp_path)
    mixed = {
        "generated_at_utc": "2026-11-21T00:00:00Z",
        "source_api": ZHIHU_SEARCH_URL,
        "is_demo_data": True,
        "cards": [
            {
                "excerpt": "x", "source_url": "https://www.zhihu.com/a", "language": "zh-CN",
                "published_on": "2026-01-01", "level": "L2", "sample_size": 1,
                "stance": "insufficient", "is_demo_data": False,
            }
        ],
    }
    path = tmp_path / "混排.json"
    import json as _json

    path.write_text(_json.dumps(mixed, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(zhihu_snapshot, "snapshot_path", lambda q: path)
    cards, notice = load_zhihu_snapshot("混排")
    assert cards == []
    assert notice and "快照损坏" in notice
    assert "is_demo_data" in (notice or "")


def test_snapshot_excerpt_over_limit_rejected(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """摘录超过 300 字符的快照视为损坏（不落全文红线，加载器二次校验）。"""
    monkeypatch.setattr(zhihu_snapshot, "SNAPSHOT_DIR", tmp_path)
    doc = {
        "generated_at_utc": "2026-11-21T00:00:00Z",
        "source_api": ZHIHU_SEARCH_URL,
        "is_demo_data": True,
        "cards": [
            {
                "excerpt": "长" * (EXCERPT_MAX_CHARS + 1),
                "source_url": "https://www.zhihu.com/a",
                "language": "zh-CN",
                "published_on": "2026-01-01",
                "level": "L2",
                "sample_size": 1,
                "stance": "insufficient",
                "is_demo_data": True,
            }
        ],
    }
    import json as _json

    path = tmp_path / "超限.json"
    path.write_text(_json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(zhihu_snapshot, "snapshot_path", lambda q: path)
    cards, notice = load_zhihu_snapshot("超限")
    assert cards == []
    assert notice and "300" in (notice or "")


# ---------- 语义红线（硬约束 1）----------


def _l2_card() -> EvidenceCard:
    return EvidenceCard(
        excerpt="中文从业者转述：德国买家重视参数。",
        source_url="https://www.zhihu.com/answer/1",
        language="zh-CN",
        published_on=date(2026, 9, 1),
        level=EvidenceLevel.L2,
        sample_size=1,
    )


def test_l2_cards_do_not_change_stance() -> None:
    """L2 卡加入后 stance 仍为 insufficient：L2 不参与支撑（domain 规则复验）。"""
    l3_cards = [
        EvidenceCard(
            excerpt="EN L3 alert",
            source_url="https://ec.europa.eu/x",
            language="en",
            published_on=date(2026, 1, 1),
            level=EvidenceLevel.L3,
            sample_size=1,
            stance=Stance.INSUFFICIENT,
        )
    ]
    l2_cards = [_l2_card()]
    assert resolve_stance(l3_cards) is Stance.INSUFFICIENT
    assert resolve_stance(l3_cards + l2_cards) is Stance.INSUFFICIENT
    # 即使 L2 卡被错误标成 support/oppose，聚合结果也不变
    aggressive_l2 = [replace(_l2_card(), stance=Stance.SUPPORT)]
    assert resolve_stance(l3_cards + aggressive_l2) is Stance.INSUFFICIENT


def test_l2_card_stance_is_insufficient() -> None:
    """适配器单卡 stance 走 domain 规则：L2 恒为 insufficient，不手工指定。"""
    from crosspilot_api.services.zhihu_client import extraction_to_card

    card = extraction_to_card(
        zhihu_client.ZhihuExtraction(
            title="t",
            excerpt="e",
            source_url="https://www.zhihu.com/a",
            published_on=date(2026, 1, 1),
            author_anonymous_id="zh-author:x",
        )
    )
    assert card.level is EvidenceLevel.L2
    assert card.stance is Stance.INSUFFICIENT
    assert card.language == "zh-CN"
    assert card.sample_size == 1


# ---------- live 适配器（mock transport，零真实调用）----------


def test_live_missing_secret_raises_credential_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """live 无凭据 → 明确报错，绝不静默降级为空结果。"""
    monkeypatch.setattr(zhihu_client, "settings", replace(settings, zhihu_secret=None))
    with pytest.raises(ZhihuCredentialError) as excinfo:
        search_zhihu_extractions("旅行收纳包", secret=None)
    message = str(excinfo.value)
    assert "ZHIHU_ACCESS_SECRET" in message
    assert "snapshot 模式" in message


def test_live_429_raises_quota_exhausted_with_guidance() -> None:
    """HTTP 429 → QuotaExhaustedError，消息含任务约定的降级指引。"""
    with pytest.raises(QuotaExhaustedError) as excinfo:
        search_zhihu_extractions(
            "旅行收纳包", secret=FAKE_SECRET, transport=_transport(status_code=429)
        )
    assert GUIDANCE_FRAGMENT in str(excinfo.value)


def test_live_code_30001_raises_quota_exhausted() -> None:
    """响应 Code=30001（频率限制/额度耗尽）→ QuotaExhaustedError + 降级指引。"""
    payload = {"Code": 30001, "Message": "rate limit exceeded", "Data": None}
    with pytest.raises(QuotaExhaustedError) as excinfo:
        search_zhihu_extractions("旅行收纳包", secret=FAKE_SECRET, transport=_transport(payload))
    assert GUIDANCE_FRAGMENT in str(excinfo.value)


def test_live_strips_pii_and_truncates_excerpt() -> None:
    """合规红线：mock 响应埋邮箱/电话/超长文本，断言输出被剔除与截断，不落全文。"""
    extractions = search_zhihu_extractions("旅行收纳包", secret=FAKE_SECRET, transport=_transport())
    assert len(extractions) == 1
    extraction = extractions[0]
    assert "@example.com" not in extraction.excerpt
    assert "13812345678" not in extraction.excerpt
    assert "010-1234567" not in extraction.excerpt
    assert "[联系方式已剔除]" in extraction.excerpt
    assert len(extraction.excerpt) <= EXCERPT_MAX_CHARS
    # 链接回源：source_url 原样保留（UTM 溯源参数不动）
    assert extraction.source_url == _item()["Url"]


def test_live_anonymizes_author() -> None:
    """作者匿名化：输出不含昵称原文，ID 稳定可复现（同输入同 ID）。"""
    extraction = search_zhihu_extractions(
        "旅行收纳包", secret=FAKE_SECRET, transport=_transport()
    )[0]
    assert extraction.author_anonymous_id.startswith("zh-author:")
    assert "某跨境从业者" not in extraction.author_anonymous_id
    assert extraction.author_anonymous_id == anonymize_author("某跨境从业者", "1234567890")
    assert anonymize_author("A", "1") != anonymize_author("A", "2")


def test_live_auth_failure_raises() -> None:
    """Code=20001 鉴权失败 → ZhihuCredentialError。"""
    payload = {"Code": 20001, "Message": "permission denied", "Data": None}
    with pytest.raises(ZhihuCredentialError):
        search_zhihu_extractions("旅行收纳包", secret=FAKE_SECRET, transport=_transport(payload))


def test_live_malformed_response_raises() -> None:
    """响应缺 Items / Code 非零 → ZhihuResponseError，不静默返回空。"""
    bad_missing_items = {"Code": 0, "Message": "success", "Data": {"HasMore": False}}
    with pytest.raises(ZhihuResponseError):
        search_zhihu_extractions("x", secret=FAKE_SECRET, transport=_transport(bad_missing_items))
    bad_code = {"Code": 90001, "Message": "internal", "Data": None}
    with pytest.raises(ZhihuResponseError):
        search_zhihu_extractions("x", secret=FAKE_SECRET, transport=_transport(bad_code))


def test_live_request_shape_bearer_and_timestamp() -> None:
    """请求形状：Bearer 鉴权头 + 秒级 X-Request-Timestamp + Query/Count 参数。"""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["ts"] = request.headers.get("X-Request-Timestamp")
        seen["query"] = request.url.params.get("Query")
        seen["count"] = request.url.params.get("Count")
        return httpx.Response(200, json=_payload([_item()]))

    search_zhihu_extractions(
        "旅行收纳包", secret=FAKE_SECRET, transport=httpx.MockTransport(handler)
    )
    assert seen["auth"] == f"Bearer {FAKE_SECRET}"
    assert seen["ts"] is not None and seen["ts"].isdigit()
    assert seen["query"] == "旅行收纳包"
    assert seen["count"] == "10"


def test_live_network_error_raises() -> None:
    """网络故障 → ZhihuNetworkError（路由层转显式提示，不崩端点）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(ZhihuNetworkError):
        search_zhihu_extractions("x", secret=FAKE_SECRET, transport=httpx.MockTransport(handler))


def test_live_empty_query_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """空查询不发请求直接返回空列表（无凭据也不报错：压根不调用）。"""
    monkeypatch.setattr(zhihu_client, "settings", replace(settings, zhihu_secret=None))
    assert search_zhihu_extractions("   ", secret=None) == []


# ---------- 端点集成（TestClient）----------


def test_endpoint_snapshot_mode_returns_l2_cards() -> None:
    """snapshot 模式（默认）：旅行收纳包命中真实快照，l2_cards 全部真实标识。"""
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["l2_notice"] is None
    assert body["l2_cards"]
    for card in body["l2_cards"]:
        assert card["level"] == "L2"
        assert card["language"] == "zh-CN"
        assert card["is_demo_data"] is False
        assert card["stance"] == "insufficient"
    # 语义红线：L2 卡在场，stance 仍由 L3 决定，维持 insufficient
    assert body["stance"] == "insufficient"


def test_endpoint_snapshot_missing_l2_notice() -> None:
    """snapshot 模式：无快照的查询 → l2_cards 空 + l2_notice 非空。"""
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "zzz-kein-treffer-xyz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["l2_cards"] == []
    assert body["l2_notice"]
    assert "快照缺失" in body["l2_notice"]
    # 既有字段语义不变：L3 侧照常工作
    assert body["scenario"] == "real"
    assert body["stance"] == "insufficient"


def test_endpoint_live_missing_secret_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    """live 模式缺凭据 → l2_cards 空 + l2_notice 显式提示，端点不崩。"""
    monkeypatch.setattr(
        evidence_router,
        "settings",
        replace(settings, data_mode="live", zhihu_secret=None),
    )
    monkeypatch.setattr(zhihu_client, "settings", replace(settings, zhihu_secret=None))
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["l2_cards"] == []
    assert body["l2_notice"]
    assert "ZHIHU_ACCESS_SECRET" in body["l2_notice"]
    assert body["data_mode"] == "live"


def test_endpoint_live_quota_exhausted_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    """live 模式配额耗尽 → l2_notice 含任务约定降级指引。"""
    monkeypatch.setattr(evidence_router, "settings", replace(settings, data_mode="live"))

    def exhausted(query: str, **kwargs: Any) -> list[EvidenceCard]:
        raise QuotaExhaustedError(f"知乎检索触发频率限制或额度耗尽——{GUIDANCE_FRAGMENT}")

    monkeypatch.setattr(evidence_router, "search_zhihu", exhausted)
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["l2_cards"] == []
    assert GUIDANCE_FRAGMENT in body["l2_notice"]


def test_endpoint_live_normal_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """live 模式正常路径（mock 注入）：l2_cards 返回且 stance 仍为 insufficient。"""
    monkeypatch.setattr(evidence_router, "settings", replace(settings, data_mode="live"))
    cards = _live_cards()
    assert cards, "mock 传输下应产出 L2 卡"
    monkeypatch.setattr(evidence_router, "search_zhihu", lambda query, **kwargs: cards)
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["l2_notice"] is None
    assert len(body["l2_cards"]) == len(cards)
    for card in body["l2_cards"]:
        assert card["level"] == "L2"
        assert card["is_demo_data"] is False
        assert len(card["excerpt"]) <= EXCERPT_MAX_CHARS
        assert "@example.com" not in card["excerpt"]
    assert body["stance"] == "insufficient"  # L2 卡不改变结论


def test_endpoint_snapshot_mode_never_touches_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """snapshot 模式绝不触网：live 检索函数若被调用即失败（哨兵）。"""

    def sentinel(query: str, **kwargs: Any) -> list[EvidenceCard]:
        raise AssertionError("snapshot 模式不得调用 live 检索")

    monkeypatch.setattr(evidence_router, "search_zhihu", sentinel)
    with TestClient(app) as client:
        resp = client.get("/api/evidence", params={"query": "旅行收纳包"})
    assert resp.status_code == 200
    assert resp.json()["l2_cards"]


def test_snapshot_path_sanitizes_illegal_characters() -> None:
    """查询词中的 Windows 非法字符被替换为下划线，落盘/读取不错位。"""
    assert snapshot_path("旅行收纳包").name == "旅行收纳包.json"
    assert snapshot_path('a/b:c*d').name == "a_b_c_d.json"
