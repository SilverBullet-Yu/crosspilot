"""LLM 立场抽取适配器：规则基线（stance_baseline.py）的可替换正式方案。

定位（STATUS 待办 #4，ADR-0004）：规则基线在双域对照靶上已知短板（GERestaurant
oppose 召回不足、商品域词典覆盖缺口），正式立场抽取方案为 LLM API。本模块提供
供应商无关的接入层与评测入口，**本机无凭据，未做真实调用核验**——live 首跑若
响应结构与本文档不符，以实际响应修订本文件并回填核验记录（与 zhihu_client 同口径）。

合规与诚实语义（docs/CONSTRAINTS.md + ADR-0002 决策 4 同源）：
- LLM 是**判定工具，不是证据源**：输出不携带证据层级、不进入证据卡；三类口径
  （support/oppose/insufficient）与规则基线、resolve_stance 完全一致。
- 输入只接受**已清洗摘录**（≤300 字符，zhihu_client.sanitize_excerpt 口径）：
  本模块再次断言长度上限，超长直接拒绝，不发送全文、不发送作者/PII 字段。
- 失败语义：网络失败 / HTTP 非 200 / 响应结构不符 / JSON 解析失败 →
  `classify_stance_with_fallback` 回退规则基线并显式标记 fallback_used 与原因，
  绝不编造立场；配置缺失（LLMConfigError）与输入违约（StanceInputError）响亮
  失败，不参与回退——前者是部署问题，后者是调用方编程错误。
- 成本守卫：单条输入 ≤300 字符 + max_tokens 上限 + 评测脚本带磁盘缓存
  （data/sources/_eval_cache/，sha256 键，可中断续跑）与 --limit 参数。

端点规格（如实声明）：OpenAI 兼容 chat/completions——POST {LLM_API_BASE}
/chat/completions，Bearer 鉴权，response_format={"type":"json_object"}，
temperature=0。主流供应商（智谱 / DeepSeek / Moonshot / OpenAI 等）均提供兼容
端点；若目标供应商不支持 response_format（HTTP 400），删除该字段重试并回填
核验记录。输出契约：{"stance": "support|oppose|insufficient", "reason": "≤160字符"}。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from ..config import settings
from ..domain.evidence import Stance
from .stance_baseline import classify_stance
from .zhihu_client import EXCERPT_MAX_CHARS

#: 判定依据的最大保留长度（展示与留痕口径，超长截断）。
REASON_MAX_CHARS = 160

#: 单次请求生成上限（一条判定 + 简短依据足够，控制成本）。
MAX_TOKENS = 200

#: 请求超时（秒）。
DEFAULT_TIMEOUT_SECONDS = 30.0

_SYSTEM_PROMPT = (
    "你是德语消费者评论的立场标注器。对给定评论输出 JSON，只输出 JSON，"
    '格式：{"stance": "...", "reason": "..."}。'
    "stance 取值仅限 support / oppose / insufficient："
    "support = 对所评对象的正面评价或推荐倾向；"
    "oppose = 负面评价或不推荐；"
    "insufficient = 无极性信号、正负混合且无主导方向（如三星中评、既有表扬又有"
    "抱怨）。不要推断文本未提及的属性；文本可能被截断，以可见部分为准。"
    "reason 用不超过 160 字符的中文说明判定依据，必须引用原文中的关键词。"
)


class StanceLLMError(RuntimeError):
    """LLM 立场抽取错误基类。"""


class StanceInputError(StanceLLMError, ValueError):
    """调用方违反输入契约（空文本之外的非法输入，如超长未清洗文本）。"""


class LLMConfigError(StanceLLMError):
    """LLM 端点配置缺失。部署问题，响亮失败，不静默降级。"""


class LLMNetworkError(StanceLLMError):
    """网络层失败（超时、DNS、连接被拒）。"""


class LLMResponseError(StanceLLMError):
    """响应结构不符合 chat/completions 规格或 JSON 契约不满足。"""


@dataclass(frozen=True)
class LLMStanceResult:
    """一条 LLM 立场判定结果（或回退到规则基线的结果）。

    fallback_used=True 时 stance/reason 来自规则基线，reason 前缀标明回退原因，
    不与 LLM 判定混同——评测脚本按此口径统计回退率。
    """

    stance: Stance
    reason: str
    model: str
    fallback_used: bool = False
    fallback_reason: str | None = None


def _resolved_config(
    api_base: str | None, api_key: str | None, model: str | None
) -> tuple[str, str, str]:
    """合并显式参数与环境配置；三项任一缺失即响亮报错。"""
    base = api_base if api_base is not None else settings.llm_api_base
    key = api_key if api_key is not None else settings.llm_api_key
    mdl = model if model is not None else settings.llm_model
    missing = [
        name
        for name, val in (("LLM_API_BASE", base), ("LLM_API_KEY", key), ("LLM_MODEL", mdl))
        if not val
    ]
    if missing:
        raise LLMConfigError(
            f"LLM 端点未配置（缺 {', '.join(missing)}）；"
            "LLM 立场抽取需要 .env 中配置 OpenAI 兼容端点后才能使用"
        )
    return base or "", key or "", mdl or ""


def _build_messages(text: str) -> list[dict[str, str]]:
    """构造 chat/completions 消息；输入调用方保证为已清洗摘录。"""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"评论原文：\n{text}\n\n只输出 JSON。"},
    ]


def _parse_content(content: str) -> tuple[Stance, str]:
    """解析并校验模型输出的 JSON 契约；不满足即 LLMResponseError。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"LLM 输出不是合法 JSON：{content[:200]!r}") from exc
    if not isinstance(data, dict):
        raise LLMResponseError(f"LLM 输出 JSON 不是对象：{content[:200]!r}")
    stance_raw = data.get("stance")
    reason = data.get("reason")
    valid = {s.value for s in Stance}
    if stance_raw not in valid:
        raise LLMResponseError(
            f"LLM 输出 stance 非法（{stance_raw!r}），仅限 {sorted(valid)}"
        )
    if not isinstance(reason, str) or not reason.strip():
        raise LLMResponseError("LLM 输出缺少非空 reason（可解释性为硬要求）")
    return Stance(stance_raw), reason.strip()[:REASON_MAX_CHARS]


def classify_stance_llm(
    text: str,
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> LLMStanceResult:
    """严格版单条判定：配置缺失 / 网络失败 / 响应不符均抛错，由调用方决定降级。

    空文本短路返回 insufficient（与规则基线口径一致），不发网络请求；
    超长输入抛 StanceInputError（先于任何网络调用）。
    """
    base, key, mdl = _resolved_config(api_base, api_key, model)
    if not text or not text.strip():
        return LLMStanceResult(stance=Stance.INSUFFICIENT, reason="空文本，无立场信号", model=mdl)
    if len(text) > EXCERPT_MAX_CHARS:
        raise StanceInputError(
            f"输入 {len(text)} 字符超过摘录上限 {EXCERPT_MAX_CHARS}："
            "LLM 立场抽取只接受已清洗摘录（zhihu_client.sanitize_excerpt 口径），禁止发送全文"
        )
    payload = {
        "model": mdl,
        "messages": _build_messages(text),
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    url = base.rstrip("/") + "/chat/completions"
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as exc:
        raise LLMNetworkError(f"LLM 请求网络失败：{exc}") from exc
    if resp.status_code != 200:
        raise LLMResponseError(f"LLM 端点返回 HTTP {resp.status_code}：{resp.text[:200]!r}")
    try:
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError(
            f"响应结构不符合 chat/completions 规格：{resp.text[:200]!r}"
        ) from exc
    stance, reason = _parse_content(str(content))
    return LLMStanceResult(stance=stance, reason=reason, model=mdl)


def classify_stance_with_fallback(
    text: str,
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> LLMStanceResult:
    """批处理入口（评测脚本用）：运行时故障回退规则基线并显式标记。

    配置缺失（LLMConfigError）与输入违约（StanceInputError）不参与回退，
    响亮抛出；其余 StanceLLMError（网络 / HTTP / 响应结构 / JSON 契约）回退
    规则基线，fallback_used=True 与原因逐条留痕，保证回退率可统计、可审计。
    """
    try:
        return classify_stance_llm(
            text, api_base=api_base, api_key=api_key, model=model,
            timeout=timeout, transport=transport,
        )
    except (LLMConfigError, StanceInputError):
        raise
    except StanceLLMError as exc:
        rule = classify_stance(text)
        return LLMStanceResult(
            stance=rule.stance,
            reason=f"规则基线回退（{exc}）；规则净分 {rule.score}",
            model=model if model is not None else "rule-fallback",
            fallback_used=True,
            fallback_reason=str(exc),
        )
