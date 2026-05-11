import asyncio

import httpx

from backend.app.core.config import settings
from backend.app.llm.client import (
    LLMProviderConfig,
    LLM_CONTEXT_TRUNCATED_MARKER,
    MINIMAX_PROVIDER_PROFILE,
    build_request_error_message,
    build_messages,
    build_payload,
    call_llm,
    call_llm_sync,
    clip_context_for_prompt,
    failure_result,
    infer_provider_profile,
    normalize_provider_profile,
    resolve_chat_completions_url,
    success_result,
    unconfigured_message,
)


def test_build_request_error_message_includes_timeout_details(monkeypatch):
    request = httpx.Request("POST", "https://example.com/chat/completions")
    exc = httpx.ReadTimeout("", request=request)

    message = build_request_error_message(
        exc,
        "https://example.com/chat/completions",
        timeout_seconds=30,
    )

    assert "error_type: ReadTimeout" in message
    assert "timeout_seconds:" in message
    assert "上游模型服务在" in message


def test_build_request_error_message_preserves_non_empty_error_text():
    request = httpx.Request("POST", "https://example.com/chat/completions")
    exc = httpx.ConnectError("dns failed", request=request)

    message = build_request_error_message(
        exc,
        "https://example.com/chat/completions",
        timeout_seconds=30,
    )

    assert "error_type: ConnectError" in message
    assert "dns failed" in message


def test_build_messages_combines_context_into_single_system_message():
    messages = build_messages("你好", "上一轮对话", "你是助手")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "你是助手" in messages[0]["content"]
    assert "Recent conversation context:\n上一轮对话" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "你好"}


def test_clip_context_for_prompt_keeps_recent_tail(monkeypatch):
    monkeypatch.setattr(settings, "chat_context_max_chars", 80)
    context = "old-context-" + ("x" * 120) + "-recent-tail"

    clipped = clip_context_for_prompt(context)

    assert clipped is not None
    assert len(clipped) <= 80
    assert clipped.startswith(LLM_CONTEXT_TRUNCATED_MARKER)
    assert clipped.endswith("-recent-tail")
    assert "old-context-" not in clipped


def test_build_messages_clips_context_before_payload(monkeypatch):
    monkeypatch.setattr(settings, "chat_context_max_chars", 90)
    messages = build_messages(
        "你好",
        "old-context-" + ("x" * 160) + "-recent-tail",
        "你是助手",
    )

    system_content = messages[0]["content"]

    assert LLM_CONTEXT_TRUNCATED_MARKER in system_content
    assert "-recent-tail" in system_content
    assert "old-context-" not in system_content


def test_unconfigured_message_uses_context_preview(monkeypatch):
    monkeypatch.setattr(settings, "chat_context_max_chars", 2000)

    result = unconfigured_message("hello", "context-" + ("z" * 900))

    assert result.ok is False
    assert result.error_kind == "unconfigured"
    assert result.output is not None
    assert len(result.output) < 900
    assert "z" * 700 not in result.output


def test_resolve_chat_completions_url_prefers_explicit_endpoint():
    assert (
        resolve_chat_completions_url(
            "https://api.example.com/v1",
            explicit_url="https://gateway.example.com/custom/chat",
        )
        == "https://gateway.example.com/custom/chat"
    )


def test_resolve_chat_completions_url_appends_standard_endpoint():
    assert (
        resolve_chat_completions_url("https://api.minimaxi.com/v1/")
        == "https://api.minimaxi.com/v1/chat/completions"
    )


def test_resolve_chat_completions_url_keeps_full_chat_endpoint():
    assert (
        resolve_chat_completions_url("https://api.longcat.chat/openai/v1/chat/completions/")
        == "https://api.longcat.chat/openai/v1/chat/completions"
    )


def test_normalize_provider_profile_accepts_common_aliases():
    assert normalize_provider_profile("openai-compatible") == "openai"
    assert normalize_provider_profile("MiniMax") == MINIMAX_PROVIDER_PROFILE
    assert normalize_provider_profile("mini-max") == MINIMAX_PROVIDER_PROFILE


def test_infer_provider_profile_detects_minimax_from_url():
    assert (
        infer_provider_profile(base_url="https://api.minimaxi.com/v1")
        == MINIMAX_PROVIDER_PROFILE
    )


def test_build_payload_clamps_zero_temperature_for_minimax():
    payload = build_payload(
        "hello",
        None,
        "You are helpful.",
        0.0,
        model="MiniMax-M2.7",
        profile=MINIMAX_PROVIDER_PROFILE,
    )

    assert payload["temperature"] == 0.01


def test_call_llm_falls_back_after_primary_request_error(monkeypatch):
    async def fake_request(provider, **kwargs):
        if provider.name == "primary":
            return failure_result(
                "primary timeout",
                provider_name="primary",
                error_kind="request",
            )
        return success_result(
            "fallback ok",
            provider_name="fallback",
            fallback_used=True,
            status_code=200,
        )

    monkeypatch.setattr(
        "backend.app.llm.client.get_provider_chain",
        lambda: [
            LLMProviderConfig("primary", "https://primary.example/v1", "k1", "model-a", 20),
            LLMProviderConfig("fallback", "https://fallback.example/v1", "k2", "model-b", 30),
        ],
    )
    monkeypatch.setattr("backend.app.llm.client._request_provider_async", fake_request)

    result = asyncio.run(call_llm("hello"))

    assert result.ok is True
    assert result.output == "fallback ok"
    assert result.provider_name == "fallback"
    assert result.fallback_used is True


def test_call_llm_sync_falls_back_after_primary_request_error(monkeypatch):
    def fake_request(provider, **kwargs):
        if provider.name == "primary":
            return failure_result(
                "primary timeout",
                provider_name="primary",
                error_kind="request",
            )
        return success_result(
            "fallback sync ok",
            provider_name="fallback",
            fallback_used=True,
            status_code=200,
        )

    monkeypatch.setattr(
        "backend.app.llm.client.get_provider_chain",
        lambda: [
            LLMProviderConfig("primary", "https://primary.example/v1", "k1", "model-a", 20),
            LLMProviderConfig("fallback", "https://fallback.example/v1", "k2", "model-b", 30),
        ],
    )
    monkeypatch.setattr("backend.app.llm.client._request_provider_sync", fake_request)

    result = call_llm_sync("hello")

    assert result.ok is True
    assert result.output == "fallback sync ok"
    assert result.provider_name == "fallback"
    assert result.fallback_used is True


def test_call_llm_sync_stops_after_non_retryable_http_status(monkeypatch):
    called_providers: list[str] = []

    def fake_request(provider, **kwargs):
        called_providers.append(provider.name)
        if provider.name == "primary":
            return failure_result(
                "primary bad request",
                provider_name="primary",
                error_kind="http_status",
                status_code=400,
            )
        return success_result(
            "fallback should not run",
            provider_name="fallback",
            fallback_used=True,
            status_code=200,
        )

    monkeypatch.setattr(
        "backend.app.llm.client.get_provider_chain",
        lambda: [
            LLMProviderConfig("primary", "https://primary.example/v1", "k1", "model-a", 20),
            LLMProviderConfig("fallback", "https://fallback.example/v1", "k2", "model-b", 30),
        ],
    )
    monkeypatch.setattr("backend.app.llm.client._request_provider_sync", fake_request)

    result = call_llm_sync("hello")

    assert called_providers == ["primary"]
    assert result.ok is False
    assert result.provider_name == "primary"
    assert result.status_code == 400


def test_call_llm_sync_combines_primary_and_fallback_failures(monkeypatch):
    def fake_request(provider, **kwargs):
        if provider.name == "primary":
            return failure_result(
                "primary timeout",
                provider_name="primary",
                error_kind="request",
            )
        return failure_result(
            "fallback timeout",
            provider_name="fallback",
            fallback_used=True,
            error_kind="request",
        )

    monkeypatch.setattr(
        "backend.app.llm.client.get_provider_chain",
        lambda: [
            LLMProviderConfig("primary", "https://primary.example/v1", "k1", "model-a", 20),
            LLMProviderConfig("fallback", "https://fallback.example/v1", "k2", "model-b", 30),
        ],
    )
    monkeypatch.setattr("backend.app.llm.client._request_provider_sync", fake_request)

    result = call_llm_sync("hello")

    assert result.ok is False
    assert result.provider_name == "fallback"
    assert result.fallback_used is True
    assert result.error is not None
    assert "provider: primary" in result.error
    assert "provider: fallback" in result.error
