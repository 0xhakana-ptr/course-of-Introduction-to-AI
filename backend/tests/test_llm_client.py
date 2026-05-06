import asyncio

import httpx

from backend.app.llm.client import (
    LLMProviderConfig,
    build_request_error_message,
    call_llm,
    call_llm_sync,
    failure_result,
    success_result,
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
