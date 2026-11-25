"""知乎开放平台站内搜索 live 适配器（L2 中文侧）。

合规红线（docs/CONSTRAINTS.md 第四节 + 一之二）：
- 只做实时检索 + 摘录引用 + 链接回源，**不落全文**：摘录一律 ≤300 字符截断，
  API 返回的其余长文本（ContentText 超长部分、精选评论 CommentInfoList、头像、
  认证信息等）在适配器层丢弃，不进入任何下游结构。
- 作者匿名化：不保留昵称原文，仅保留不可逆派生 ID（sha256 截断），用于同作者
  多条结果的去重审计，不构成个人数据回存。
- 适配器层剔除 PII（邮箱 / 电话）后才截断，保证占位符不会把真实联系方式挤出窗口。
- 硬约束 1：产出 L2 证据卡，只能生成待验证问题，不得单独支撑偏好结论
  （stance 一律走 domain.stance_of_card，不得手工指定）。

端点规格来源与核验程度（如实声明，不编造）：
- 端点与响应结构取自本地文档副本（仓库外工作区的 zhihu/references/http-api.md，
  知乎开放平台 HTTP API，标注核验时间 2026-07-16）：
  GET https://developer.zhihu.com/api/v1/content/zhihu_search，
  Query=关键词（必填）、Count=1..10（默认 10，超出截断为 10），
  鉴权 Authorization: Bearer <Access Secret> + X-Request-Timestamp（秒级时间戳），
  响应 {"Code": 0, "Message": "...", "Data": {"HasMore", "SearchHashId", "Items": [...]}}，
  Item 字段 Title/ContentType/ContentID/ContentText/Url/.../EditTime（秒级时间戳）。
  错误码：0 成功；10001 参数错误；20001 鉴权失败；30001 频率限制/额度耗尽；90001 内部错误。
- 2026-11-21 联网探测：developer.zhihu.com 与 /docs 页面可达（HTTP 200，约 11s），
  API 域名可解析。**端点响应结构未能用真实凭据联网核验**（本机无凭据且实测额度
  搜索 10 次/日，禁止消耗），字段名以文档副本为准；live 首跑（capture 脚本）时
  若实际响应与本文档不符，以实际响应修订本文件，并回填核验记录。
- 实测额度：zhihu_search 10 次/日（手册称 5000，差 500 倍，见
  research/crosspilot-evidence_dim04.md）。
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any

import httpx

from ..config import settings
from ..domain.evidence import EvidenceCard, EvidenceLevel, stance_of_card

#: 站内搜索端点（规格来源与核验程度见模块 docstring）。
ZHIHU_SEARCH_URL = "https://developer.zhihu.com/api/v1/content/zhihu_search"

#: 摘录截断上限（合规红线：摘录引用，不落全文）。
EXCERPT_MAX_CHARS = 300

#: 单次请求数量上限（官方文档：默认 10，超出自动截断为 10）。
REQUEST_COUNT = 10

#: 配额耗尽/限流的统一降级指引（ADR-0002 决策 4：禁止静默返回空结果）。
QUOTA_GUIDANCE = "当前为实测 10 次/日，演示请切回 snapshot 模式"


class ZhihuError(RuntimeError):
    """知乎适配器错误基类。路由层捕获后转为 l2_notice 显式提示。"""


class ZhihuCredentialError(ZhihuError):
    """凭据缺失或鉴权失败。适配器层直接抛错，不做静默降级。"""


class QuotaExhaustedError(ZhihuError):
    """配额耗尽或触发频率限制。消息必须含降级指引。"""


class ZhihuNetworkError(ZhihuError):
    """网络层失败（超时、DNS、连接被拒）。"""


class ZhihuResponseError(ZhihuError):
    """响应结构不符合文档规格（可能文档副本过时）。"""


@dataclass(frozen=True)
class ZhihuExtraction:
    """适配器从 API 响应中允许保留的字段（合规最小集）。

    title / author_anonymous_id 仅存在于适配器内部与快照文件，
    不进入 EvidenceCard（evidence-card.schema.json 不含这两个字段）。
    """

    title: str
    excerpt: str
    source_url: str
    published_on: date
    author_anonymous_id: str


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:1[3-9]\d{9}|0\d{2,3}-\d{7,8})(?!\d)")
_PII_PLACEHOLDER = "[联系方式已剔除]"


def anonymize_author(author_name: str, content_id: str) -> str:
    """作者匿名化 ID：sha256 截断派生，不保留昵称原文。"""
    digest = hashlib.sha256(f"{author_name}|{content_id}".encode()).hexdigest()
    return f"zh-author:{digest[:12]}"


def sanitize_excerpt(text: str) -> str:
    """合规清洗链：剥 HTML 标签 → 剔除 PII → 截断 ≤300 字符。

    PII 剔除必须在截断前执行：若先截断，真实邮箱/电话可能留在窗口内。
    """
    plain = _HTML_TAG_RE.sub("", text)
    plain = _EMAIL_RE.sub(_PII_PLACEHOLDER, plain)
    plain = _PHONE_RE.sub(_PII_PLACEHOLDER, plain)
    return plain.strip()[:EXCERPT_MAX_CHARS]


def _timestamp_to_date(seconds: int) -> date:
    """EditTime 秒级时间戳 → UTC 日期（快照卡 published_on）。"""
    return datetime.fromtimestamp(seconds, tz=UTC).date()


def _parse_item(item: dict[str, Any]) -> ZhihuExtraction:
    """把一条搜索结果转为合规最小集。必返字段缺失直接抛错，不静默降级。"""
    title = str(item.get("Title") or "").strip()
    content_text = str(item.get("ContentText") or "")
    url = str(item.get("Url") or "").strip()
    content_id = str(item.get("ContentID") or "").strip()
    edit_time = item.get("EditTime")
    if not title or not url or not content_id or edit_time is None:
        raise ZhihuResponseError(f"搜索结果缺少必返字段（Title/Url/ContentID/EditTime）: {item!r}")
    if not isinstance(edit_time, int):
        raise ZhihuResponseError(f"EditTime 不是秒级时间戳: {edit_time!r}")
    excerpt = sanitize_excerpt(content_text)
    if not excerpt:
        raise ZhihuResponseError(f"摘录清洗后为空，无法构建证据卡: {content_id!r}")
    return ZhihuExtraction(
        title=title,
        excerpt=excerpt,
        source_url=url,
        published_on=_timestamp_to_date(edit_time),
        author_anonymous_id=anonymize_author(str(item.get("AuthorName") or ""), content_id),
    )


def extraction_to_card(extraction: ZhihuExtraction) -> EvidenceCard:
    """合规最小集 → L2 证据卡。stance 走 stance_of_card，不得手工指定。"""
    card = EvidenceCard(
        excerpt=extraction.excerpt,
        source_url=extraction.source_url,
        language="zh-CN",  # 站内搜索结果为中文
        published_on=extraction.published_on,
        level=EvidenceLevel.L2,
        sample_size=1,  # 单条内容即单卡
    )
    return resolve_stance_preserved(card)


def resolve_stance_preserved(card: EvidenceCard) -> EvidenceCard:
    """单卡 stance 走 domain 规则（L2 必然 insufficient），不手工指定。"""
    return replace(card, stance=stance_of_card(card))


def _build_headers(secret: str) -> dict[str, str]:
    """Bearer 鉴权头 + 秒级时间戳（官方文档要求服务端校验两者）。"""
    return {
        "Authorization": f"Bearer {secret}",
        "X-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
    }


def _check_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """校验业务错误码并返回 Items。错误码语义见模块 docstring。"""
    code = payload.get("Code")
    message = str(payload.get("Message") or "")
    if code == 30001:
        raise QuotaExhaustedError(
            f"知乎检索触发频率限制或额度耗尽（Code=30001：{message}）——{QUOTA_GUIDANCE}"
        )
    if code == 20001:
        raise ZhihuCredentialError(
            f"知乎鉴权失败（Code=20001：{message}），检查 ZHIHU_ACCESS_SECRET"
        )
    if code == 10001:
        raise ZhihuResponseError(f"知乎检索参数错误（Code=10001：{message}）")
    if code != 0:
        raise ZhihuResponseError(f"知乎检索失败（Code={code}：{message}）")
    data = payload.get("Data")
    if not isinstance(data, dict):
        raise ZhihuResponseError(f"响应缺少 Data 对象: {payload!r}")
    items = data.get("Items")
    if not isinstance(items, list):
        raise ZhihuResponseError(f"响应 Data.Items 不是列表: {data!r}")
    return items


def search_zhihu_extractions(
    query: str,
    *,
    secret: str | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = 15.0,
    base_url: str | None = None,
    on_raw_payload: Callable[[dict[str, Any]], None] | None = None,
) -> list[ZhihuExtraction]:
    """执行站内搜索，返回合规最小集。测试经 transport 注入 mock 响应。

    secret 缺失直接抛 ZhihuCredentialError（不静默降级为空结果）。

    on_raw_payload（修复 D-09）：可选回调，收到原始响应 JSON 时调用一次，
    供捕获脚本落盘脱敏后的 raw payload。适配器自身仍不保留全文——回调是
    调用方的显式选择，且落盘前必须由调用方做脱敏（见 capture 脚本的
    scrub_payload）。回调异常**不被捕获**，会向上抛出：原始响应落盘失败
    属于留痕缺陷，不应被静默忽略。
    """
    keyword = query.strip()
    if not keyword:
        return []  # 空查询压根不发起请求，凭据检查无意义，直接返回空列表
    resolved_secret = secret if secret is not None else settings.zhihu_secret
    if not resolved_secret:
        raise ZhihuCredentialError(
            "live 模式需要知乎 Access Secret：developer.zhihu.com 个人中心获取后"
            "设置 ZHIHU_ACCESS_SECRET；未配置凭据时禁止调用知乎 API，"
            "演示请切回 snapshot 模式"
        )
    request = httpx.Request(
        "GET",
        ZHIHU_SEARCH_URL if base_url is None else base_url,
        params={"Query": keyword, "Count": str(REQUEST_COUNT)},
        headers=_build_headers(resolved_secret),
    )
    try:
        with httpx.Client(transport=transport, timeout=timeout_seconds) as client:
            response = client.send(request)
    except httpx.HTTPError as exc:
        raise ZhihuNetworkError(f"知乎检索网络失败: {exc}") from exc
    if response.status_code == 429:
        raise QuotaExhaustedError(f"知乎检索返回 HTTP 429——{QUOTA_GUIDANCE}")
    try:
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPStatusError, ValueError) as exc:
        raise ZhihuResponseError(f"知乎检索响应异常（HTTP {response.status_code}）: {exc}") from exc
    if on_raw_payload is not None and isinstance(payload, dict):
        on_raw_payload(payload)
    items = _check_payload(payload)
    return [_parse_item(item) for item in items]


def search_zhihu(
    query: str,
    *,
    secret: str | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = 15.0,
) -> list[EvidenceCard]:
    """站内搜索 → L2 证据卡列表（live 路径唯一入口）。

    配额耗尽抛 QuotaExhaustedError（消息含降级指引），由路由层转为 l2_notice；
    凭据缺失抛 ZhihuCredentialError，由路由层转为显式提示，禁止静默空结果。
    """
    return [
        extraction_to_card(item)
        for item in search_zhihu_extractions(
            query, secret=secret, transport=transport, timeout_seconds=timeout_seconds
        )
    ]
