"""LLM 立场抽取适配器测试（全部走 httpx.MockTransport，零真实 API 调用）。

覆盖（对应 services/stance_llm.py 的合规与诚实语义）：
- 合法 JSON 契约解析（stance/reason/model）；
- 非法 stance 值、非法 JSON、缺 reason、HTTP 非 200、网络故障 → 响亮报错；
- classify_stance_with_fallback：运行时故障回退规则基线并显式标记，
  配置缺失与输入违约不参与回退；
- 输入守卫：空文本短路 insufficient 不触网；>300 字符拒绝且不触网；
- 请求规格：URL 拼接、Bearer 鉴权、response_format/temperature/max_tokens。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from crosspilot_api.domain.evidence import Stance
from crosspilot_api.services.stance_baseline import classify_stance
from crosspilot_api.services.stance_llm import (
    REASON_MAX_CHARS,
    LLMConfigError,
    LLMNetworkError,
    LLMResponseError,
    StanceInputError,
    classify_stance_llm,
    classify_stance_with_fallback,
)

CFG: dict[str, str] = {
    "api_base": "https://api.example.com/v1",
    "api_key": "test-key",
    "model": "test-model",
}

#: 规则基线判定为 support 的样本（词典多正命中、无否定），用于回退对照。
_RULE_SUPPORT_TEXT = "Der Kaffee war lecker und die Bedienung war sehr freundlich."


def _chat_transport(content: str, *, status_code: int = 200) -> httpx.MockTransport:
    """固定响应的 MockTransport：content 作为 choices[0].message.content 返回。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if status_code != 200:
            return httpx.Response(status_code, text="provider exploded")
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


def _chat_json(stance: str, reason: str) -> str:
    return json.dumps({"stance": stance, "reason": reason}, ensure_ascii=False)


def test_parses_valid_json_contract() -> None:
    transport = _chat_transport(_chat_json("oppose", "原文出现 kaputt 与 enttäuscht"))
    res = classify_stance_llm("Der Rucksack war kaputt.", transport=transport, **CFG)  # type: ignore[arg-type]
    assert res.stance is Stance.OPPOSE
    assert res.reason == "原文出现 kaputt 与 enttäuscht"
    assert res.model == "test-model"
    assert res.fallback_used is False


def test_request_url_auth_and_payload() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        content = _chat_json("support", "gut")
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    base_with_slash = CFG["api_base"] + "/"
    classify_stance_llm(
        "Alles super.",
        api_base=base_with_slash,
        api_key="test-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["max_tokens"] == 200
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert "Alles super." in captured["payload"]["messages"][1]["content"]


def test_rejects_invalid_stance_value() -> None:
    transport = _chat_transport(_chat_json("neutral", "模型自创类别"))
    with pytest.raises(LLMResponseError, match="stance 非法"):
        classify_stance_llm("irgendein Text", transport=transport, **CFG)  # type: ignore[arg-type]


def test_rejects_malformed_json() -> None:
    transport = _chat_transport("这不是 JSON")
    with pytest.raises(LLMResponseError, match="不是合法 JSON"):
        classify_stance_llm("irgendein Text", transport=transport, **CFG)  # type: ignore[arg-type]


def test_rejects_missing_reason() -> None:
    transport = _chat_transport('{"stance": "support"}')
    with pytest.raises(LLMResponseError, match="reason"):
        classify_stance_llm("irgendein Text", transport=transport, **CFG)  # type: ignore[arg-type]


def test_http_error_raises_response_error() -> None:
    transport = _chat_transport("", status_code=500)
    with pytest.raises(LLMResponseError, match="HTTP 500"):
        classify_stance_llm("irgendein Text", transport=transport, **CFG)  # type: ignore[arg-type]


def test_malformed_structure_raises_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "unexpected shape"})

    with pytest.raises(LLMResponseError, match="响应结构"):
        classify_stance_llm(
            "irgendein Text",
            api_base=CFG["api_base"],
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )


def test_network_failure_maps_to_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMNetworkError, match="网络失败"):
        classify_stance_llm(
            "irgendein Text",
            api_base=CFG["api_base"],
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )


def test_fallback_returns_rule_stance_and_marks_flag() -> None:
    transport = _chat_transport("", status_code=503)
    res = classify_stance_with_fallback(_RULE_SUPPORT_TEXT, transport=transport, **CFG)  # type: ignore[arg-type]
    rule = classify_stance(_RULE_SUPPORT_TEXT)
    assert res.stance is rule.stance
    assert res.stance is Stance.SUPPORT
    assert res.fallback_used is True
    assert res.fallback_reason is not None
    assert "HTTP 503" in (res.fallback_reason or "")


def test_config_error_does_not_fallback() -> None:
    with pytest.raises(LLMConfigError, match="LLM_API_BASE"):
        classify_stance_with_fallback(_RULE_SUPPORT_TEXT, api_base="", api_key="k", model="m")


def test_input_violation_does_not_fallback() -> None:
    long_text = "x" * 301
    with pytest.raises(StanceInputError, match="超过摘录上限"):
        classify_stance_with_fallback(long_text, api_base=CFG["api_base"], api_key="k", model="m")


def test_overlong_input_rejected_before_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("超长输入不应发起任何网络请求")

    with pytest.raises(StanceInputError):
        classify_stance_llm(
            "x" * 301,
            api_base=CFG["api_base"],
            api_key="test-key",
            model="test-model",
            transport=httpx.MockTransport(handler),
        )


def test_empty_text_short_circuits_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("空文本不应发起任何网络请求")

    res = classify_stance_llm(
        "   ",
        api_base=CFG["api_base"],
        api_key="test-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    assert res.stance is Stance.INSUFFICIENT
    assert res.fallback_used is False


def test_reason_truncated_to_limit() -> None:
    transport = _chat_transport(_chat_json("support", "正" * (REASON_MAX_CHARS + 50)))
    res = classify_stance_llm("irgendein Text", transport=transport, **CFG)  # type: ignore[arg-type]
    assert len(res.reason) == REASON_MAX_CHARS
