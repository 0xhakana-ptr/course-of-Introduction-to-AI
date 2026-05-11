import re
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import settings
from ..core.text_utils import build_preview

THINKING_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass(slots=True)
class LLMProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    profile: str = "openai"
    chat_completions_url: str = ""


@dataclass(slots=True)
class LLMCallResult:
    ok: bool
    output: str
    error: str | None = None
    provider_name: str | None = None
    fallback_used: bool = False
    error_kind: str | None = None
    status_code: int | None = None


@dataclass(slots=True)
class LLMDiagnosticsResult:
    configured: bool
    api_key_present: bool
    base_url: str | None
    chat_completions_url: str | None
    resolved_url: str | None
    provider_profile: str
    model: str | None
    timeout_seconds: int
    fallback_configured: bool = False
    fallback_base_url: str | None = None
    fallback_chat_completions_url: str | None = None
    fallback_resolved_url: str | None = None
    fallback_provider_profile: str | None = None
    fallback_model: str | None = None
    fallback_timeout_seconds: int | None = None
    checked_remote: bool = False
    request_ok: bool | None = None
    status_code: int | None = None
    response_preview: str | None = None
    error_message: str | None = None
    provider_used: str | None = None
    fallback_used: bool = False


DIAGNOSTIC_PREVIEW_LIMIT = 200
DIAGNOSTIC_ERROR_LIMIT = 500
LLM_CONTEXT_TRUNCATED_MARKER = "... (context truncated before LLM request)\n"
OPENAI_PROVIDER_PROFILE = "openai"
MINIMAX_PROVIDER_PROFILE = "minimax"
MINIMAX_MIN_TEMPERATURE = 0.01
MINIMAX_MAX_TEMPERATURE = 1.0
PROVIDER_PROFILE_ALIASES = {
    "openai": OPENAI_PROVIDER_PROFILE,
    "openai-compatible": OPENAI_PROVIDER_PROFILE,
    "openai_compatible": OPENAI_PROVIDER_PROFILE,
    "openai compatible": OPENAI_PROVIDER_PROFILE,
    "minimax": MINIMAX_PROVIDER_PROFILE,
    "minimaxi": MINIMAX_PROVIDER_PROFILE,
    "mini-max": MINIMAX_PROVIDER_PROFILE,
    "mini_max": MINIMAX_PROVIDER_PROFILE,
    "mini max": MINIMAX_PROVIDER_PROFILE,
}


def normalize_provider_profile(value: str | None) -> str:
    text = str(value or "").strip().lower()
    return PROVIDER_PROFILE_ALIASES.get(text, "")


def infer_provider_profile(
    *,
    profile: str | None = None,
    base_url: str | None = None,
    chat_completions_url: str | None = None,
) -> str:
    normalized = normalize_provider_profile(profile)
    if normalized:
        return normalized

    probe = " ".join(item for item in (base_url, chat_completions_url) if item).lower()
    if "minimax" in probe or "minimaxi" in probe:
        return MINIMAX_PROVIDER_PROFILE
    return OPENAI_PROVIDER_PROFILE


def resolve_chat_completions_url(
    base_url: str | None = None,
    *,
    explicit_url: str | None = None,
) -> str:
    endpoint = (explicit_url or "").strip().rstrip("/")
    if endpoint:
        return endpoint
    base = (base_url or settings.llm_base_url).rstrip("/")
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def get_primary_provider() -> LLMProviderConfig:
    return LLMProviderConfig(
        name="primary",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        profile=infer_provider_profile(
            profile=settings.llm_provider_profile,
            base_url=settings.llm_base_url,
            chat_completions_url=settings.llm_chat_completions_url,
        ),
        chat_completions_url=settings.llm_chat_completions_url,
    )


def get_fallback_provider() -> LLMProviderConfig:
    return LLMProviderConfig(
        name="fallback",
        base_url=settings.llm_fallback_base_url or settings.llm_base_url,
        api_key=settings.llm_fallback_api_key or settings.llm_api_key,
        model=settings.llm_fallback_model,
        timeout_seconds=settings.llm_fallback_timeout_seconds,
        profile=infer_provider_profile(
            profile=settings.llm_fallback_provider_profile or settings.llm_provider_profile,
            base_url=settings.llm_fallback_base_url or settings.llm_base_url,
            chat_completions_url=(
                settings.llm_fallback_chat_completions_url or settings.llm_chat_completions_url
            ),
        ),
        chat_completions_url=(
            settings.llm_fallback_chat_completions_url or settings.llm_chat_completions_url
        ),
    )


def provider_is_configured(provider: LLMProviderConfig) -> bool:
    return bool((provider.base_url or provider.chat_completions_url) and provider.api_key and provider.model)


def get_provider_chain() -> list[LLMProviderConfig]:
    providers: list[LLMProviderConfig] = []
    primary = get_primary_provider()
    fallback = get_fallback_provider()

    if provider_is_configured(primary):
        providers.append(primary)

    if provider_is_configured(fallback):
        duplicate = any(
            item.base_url == fallback.base_url
            and item.api_key == fallback.api_key
            and item.model == fallback.model
            and item.timeout_seconds == fallback.timeout_seconds
            and item.profile == fallback.profile
            and item.chat_completions_url == fallback.chat_completions_url
            for item in providers
        )
        if not duplicate:
            providers.append(fallback)

    return providers


def llm_is_configured() -> bool:
    return bool(get_provider_chain())


def normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return THINKING_PATTERN.sub("", content).strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        combined = "\n".join(part for part in parts if part)
        return THINKING_PATTERN.sub("", combined).strip()
    return THINKING_PATTERN.sub("", str(content or "")).strip()


def preview_text(text: str, limit: int = DIAGNOSTIC_PREVIEW_LIMIT) -> str:
    return build_preview(text, limit=limit)


def clip_context_for_prompt(context: str | None, *, limit: int | None = None) -> str | None:
    raw = str(context or "").strip()
    if not raw:
        return None

    resolved_limit = settings.chat_context_max_chars if limit is None else limit
    if resolved_limit <= 0 or len(raw) <= resolved_limit:
        return raw

    marker = LLM_CONTEXT_TRUNCATED_MARKER
    content_limit = max(resolved_limit - len(marker), 0)
    if content_limit <= 0:
        return raw[-resolved_limit:]
    return f"{marker}{raw[-content_limit:]}"


def preview_context_for_error(context: str | None) -> str:
    raw = str(context or "").strip()
    if not raw:
        return "(none)"
    limit = min(max(settings.chat_context_max_chars, 1), DIAGNOSTIC_ERROR_LIMIT)
    return preview_text(raw, limit=limit)


def failure_result(
    message: str,
    *,
    provider_name: str | None = None,
    fallback_used: bool = False,
    error_kind: str | None = None,
    status_code: int | None = None,
) -> LLMCallResult:
    return LLMCallResult(
        ok=False,
        output=message,
        error=message,
        provider_name=provider_name,
        fallback_used=fallback_used,
        error_kind=error_kind,
        status_code=status_code,
    )


def success_result(
    message: str,
    *,
    provider_name: str | None = None,
    fallback_used: bool = False,
    status_code: int | None = None,
) -> LLMCallResult:
    return LLMCallResult(
        ok=True,
        output=message,
        error=None,
        provider_name=provider_name,
        fallback_used=fallback_used,
        error_kind=None,
        status_code=status_code,
    )


def unconfigured_message(prompt: str, context: str | None = None) -> LLMCallResult:
    return failure_result(
        "当前还没有配置可用的大模型连接信息。\n\n"
        "请至少设置以下一组环境变量：\n"
        "- LLM_BASE_URL\n"
        "- LLM_API_KEY\n"
        "- LLM_MODEL\n\n"
        "如果你希望启用自动备用模型，还可以设置：\n"
        "- LLM_FALLBACK_MODEL\n"
        "- LLM_FALLBACK_BASE_URL（可选，默认继承主模型）\n"
        "- LLM_FALLBACK_API_KEY（可选，默认继承主模型）\n\n"
        f"收到的 prompt: {prompt}\n"
        f"context: {preview_context_for_error(context)}",
        error_kind="unconfigured",
    )


def build_messages(prompt: str, context: str | None, system_prompt: str) -> list[dict[str, str]]:
    combined_system = system_prompt.strip()
    normalized_context = clip_context_for_prompt(context)
    if normalized_context:
        if combined_system:
            combined_system = f"{combined_system}\n\nRecent conversation context:\n{normalized_context}"
        else:
            combined_system = f"Recent conversation context:\n{normalized_context}"

    return [
        {"role": "system", "content": combined_system},
        {"role": "user", "content": prompt},
    ]


def normalize_temperature_for_provider(profile: str, temperature: float) -> float:
    if profile == MINIMAX_PROVIDER_PROFILE:
        if temperature <= 0:
            return MINIMAX_MIN_TEMPERATURE
        if temperature > MINIMAX_MAX_TEMPERATURE:
            return MINIMAX_MAX_TEMPERATURE
    return temperature


def build_payload(
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    profile: str = OPENAI_PROVIDER_PROFILE,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model or settings.llm_model,
        "messages": build_messages(prompt, context, system_prompt),
        "temperature": normalize_temperature_for_provider(profile, temperature),
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def build_headers(api_key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key or settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def build_provider_request_parts(
    provider: LLMProviderConfig,
    *,
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    max_tokens: int | None = None,
) -> tuple[str, dict[str, object], dict[str, str]]:
    endpoint = resolve_chat_completions_url(
        provider.base_url,
        explicit_url=provider.chat_completions_url,
    )
    payload = build_payload(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        temperature=temperature,
        model=provider.model,
        max_tokens=max_tokens,
        profile=provider.profile,
    )
    headers = build_headers(provider.api_key)
    return endpoint, payload, headers


def parse_chat_response(
    data: dict[str, Any],
    endpoint: str,
    *,
    provider_name: str,
    status_code: int | None = None,
    fallback_used: bool = False,
) -> LLMCallResult:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return failure_result(
            "大模型接口响应中缺少 choices。\n\n"
            f"endpoint: {endpoint}\n"
            f"raw_json: {data}",
            provider_name=provider_name,
            fallback_used=fallback_used,
            error_kind="invalid_response",
            status_code=status_code,
        )

    message = choices[0].get("message", {})
    content = normalize_message_content(message.get("content"))
    if content:
        return success_result(
            content,
            provider_name=provider_name,
            fallback_used=fallback_used,
            status_code=status_code,
        )

    return failure_result(
        "大模型接口已返回响应，但没有提取到有效文本内容。\n\n"
        f"endpoint: {endpoint}\n"
        f"raw_json: {data}",
        provider_name=provider_name,
        fallback_used=fallback_used,
        error_kind="empty_response",
        status_code=status_code,
    )


def build_status_error_message(exc: httpx.HTTPStatusError, endpoint: str) -> str:
    body = exc.response.text.strip()
    return (
        "大模型接口返回了错误状态码。\n\n"
        f"status: {exc.response.status_code}\n"
        f"endpoint: {endpoint}\n"
        f"body: {body or '(empty)'}"
    )


def build_request_error_message(
    exc: httpx.RequestError,
    endpoint: str,
    *,
    timeout_seconds: int,
) -> str:
    error_type = type(exc).__name__
    error_detail = str(exc).strip()
    if not error_detail:
        if isinstance(exc, httpx.TimeoutException):
            error_detail = f"上游模型服务在 {timeout_seconds} 秒内未返回响应。"
        else:
            error_detail = repr(exc)

    message = (
        "调用大模型接口失败。\n\n"
        f"endpoint: {endpoint}\n"
        f"error_type: {error_type}\n"
        f"error: {error_detail}"
    )
    if isinstance(exc, httpx.TimeoutException):
        message += (
            "\n"
            f"timeout_seconds: {timeout_seconds}\n"
            "hint: 这通常表示上游模型响应过慢，或者当前模型/服务暂时不可用。"
        )
    return message


def build_invalid_json_message(response_text: str, endpoint: str) -> str:
    return (
        "大模型接口返回了无法解析的响应。\n\n"
        f"endpoint: {endpoint}\n"
        f"raw: {response_text.strip() or '(empty)'}"
    )


def build_combined_provider_failure_message(results: list[LLMCallResult]) -> str:
    lines = ["主模型调用失败，备用模型也未成功。", ""]
    for result in results:
        provider_name = result.provider_name or "unknown"
        lines.append(f"provider: {provider_name}")
        lines.append(result.error or result.output or "(empty)")
        lines.append("")
    return "\n".join(lines).strip()


def should_attempt_next_provider(result: LLMCallResult) -> bool:
    if result.error_kind == "request":
        return True
    if result.error_kind == "http_status" and result.status_code is not None:
        return result.status_code in {408, 429} or result.status_code >= 500
    return False


def build_status_failure_result(
    exc: httpx.HTTPStatusError,
    *,
    endpoint: str,
    provider_name: str,
    fallback_used: bool,
) -> LLMCallResult:
    return failure_result(
        build_status_error_message(exc, endpoint),
        provider_name=provider_name,
        fallback_used=fallback_used,
        error_kind="http_status",
        status_code=exc.response.status_code,
    )


def build_request_failure_result(
    exc: httpx.RequestError,
    *,
    endpoint: str,
    provider_name: str,
    fallback_used: bool,
    timeout_seconds: int,
) -> LLMCallResult:
    return failure_result(
        build_request_error_message(exc, endpoint, timeout_seconds=timeout_seconds),
        provider_name=provider_name,
        fallback_used=fallback_used,
        error_kind="request",
    )


def parse_provider_http_response(
    response: httpx.Response,
    endpoint: str,
    *,
    provider_name: str,
    fallback_used: bool,
) -> LLMCallResult:
    status_code = response.status_code
    try:
        data = response.json()
    except ValueError:
        return failure_result(
            build_invalid_json_message(response.text, endpoint),
            provider_name=provider_name,
            fallback_used=fallback_used,
            error_kind="invalid_json",
            status_code=status_code,
        )

    return parse_chat_response(
        data,
        endpoint,
        provider_name=provider_name,
        status_code=status_code,
        fallback_used=fallback_used,
    )


def finalize_provider_chain_step(
    results: list[LLMCallResult],
    result: LLMCallResult,
    *,
    is_last_provider: bool,
) -> LLMCallResult | None:
    if result.ok:
        return result

    if not is_last_provider and should_attempt_next_provider(result):
        return None

    if len(results) == 1:
        return result

    return failure_result(
        build_combined_provider_failure_message(results),
        provider_name=result.provider_name,
        fallback_used=result.fallback_used,
        error_kind=result.error_kind,
        status_code=result.status_code,
    )


def build_llm_diagnostics_result(
    *,
    checked_remote: bool = False,
    request_ok: bool | None = None,
    status_code: int | None = None,
    response_preview: str | None = None,
    error_message: str | None = None,
    provider_used: str | None = None,
    fallback_used: bool = False,
) -> LLMDiagnosticsResult:
    primary = get_primary_provider()
    fallback = get_fallback_provider()
    return LLMDiagnosticsResult(
        configured=llm_is_configured(),
        api_key_present=bool(primary.api_key or fallback.api_key),
        base_url=primary.base_url or None,
        chat_completions_url=primary.chat_completions_url or None,
        resolved_url=resolve_chat_completions_url(
            primary.base_url,
            explicit_url=primary.chat_completions_url,
        ) or None,
        provider_profile=primary.profile,
        model=primary.model or None,
        timeout_seconds=primary.timeout_seconds,
        fallback_configured=provider_is_configured(fallback),
        fallback_base_url=(fallback.base_url or None) if provider_is_configured(fallback) else None,
        fallback_chat_completions_url=(
            fallback.chat_completions_url or None
        ) if provider_is_configured(fallback) else None,
        fallback_resolved_url=(
            resolve_chat_completions_url(
                fallback.base_url,
                explicit_url=fallback.chat_completions_url,
            ) or None
        ) if provider_is_configured(fallback) else None,
        fallback_provider_profile=(
            fallback.profile if provider_is_configured(fallback) else None
        ),
        fallback_model=(fallback.model or None) if provider_is_configured(fallback) else None,
        fallback_timeout_seconds=(
            fallback.timeout_seconds if provider_is_configured(fallback) else None
        ),
        checked_remote=checked_remote,
        request_ok=request_ok,
        status_code=status_code,
        response_preview=response_preview,
        error_message=error_message,
        provider_used=provider_used,
        fallback_used=fallback_used,
    )


async def _request_provider_async(
    provider: LLMProviderConfig,
    *,
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    max_tokens: int | None = None,
    fallback_used: bool = False,
) -> LLMCallResult:
    endpoint, payload, headers = build_provider_request_parts(
        provider,
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return build_status_failure_result(
            exc,
            endpoint=endpoint,
            provider_name=provider.name,
            fallback_used=fallback_used,
        )
    except httpx.RequestError as exc:
        return build_request_failure_result(
            exc,
            endpoint=endpoint,
            provider_name=provider.name,
            fallback_used=fallback_used,
            timeout_seconds=provider.timeout_seconds,
        )

    return parse_provider_http_response(
        response,
        endpoint,
        provider_name=provider.name,
        fallback_used=fallback_used,
    )


def _request_provider_sync(
    provider: LLMProviderConfig,
    *,
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    max_tokens: int | None = None,
    fallback_used: bool = False,
) -> LLMCallResult:
    endpoint, payload, headers = build_provider_request_parts(
        provider,
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        with httpx.Client(timeout=provider.timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return build_status_failure_result(
            exc,
            endpoint=endpoint,
            provider_name=provider.name,
            fallback_used=fallback_used,
        )
    except httpx.RequestError as exc:
        return build_request_failure_result(
            exc,
            endpoint=endpoint,
            provider_name=provider.name,
            fallback_used=fallback_used,
            timeout_seconds=provider.timeout_seconds,
        )

    return parse_provider_http_response(
        response,
        endpoint,
        provider_name=provider.name,
        fallback_used=fallback_used,
    )


async def _call_with_provider_chain_async(
    *,
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    max_tokens: int | None = None,
) -> LLMCallResult:
    providers = get_provider_chain()
    if not providers:
        return unconfigured_message(prompt, context)

    results: list[LLMCallResult] = []
    for index, provider in enumerate(providers):
        result = await _request_provider_async(
            provider,
            prompt=prompt,
            context=context,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            fallback_used=index > 0,
        )
        results.append(result)

        final_result = finalize_provider_chain_step(
            results,
            result,
            is_last_provider=index == len(providers) - 1,
        )
        if final_result is not None:
            return final_result

    return failure_result("调用大模型接口失败，但没有得到可用结果。", error_kind="unknown")


def _call_with_provider_chain_sync(
    *,
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    max_tokens: int | None = None,
) -> LLMCallResult:
    providers = get_provider_chain()
    if not providers:
        return unconfigured_message(prompt, context)

    results: list[LLMCallResult] = []
    for index, provider in enumerate(providers):
        result = _request_provider_sync(
            provider,
            prompt=prompt,
            context=context,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            fallback_used=index > 0,
        )
        results.append(result)

        final_result = finalize_provider_chain_step(
            results,
            result,
            is_last_provider=index == len(providers) - 1,
        )
        if final_result is not None:
            return final_result

    return failure_result("调用大模型接口失败，但没有得到可用结果。", error_kind="unknown")


async def diagnose_llm(*, check_remote: bool = False) -> LLMDiagnosticsResult:
    diagnostics = build_llm_diagnostics_result()
    if not check_remote:
        return diagnostics

    if not llm_is_configured():
        return build_llm_diagnostics_result(
            checked_remote=False,
            request_ok=False,
            error_message="当前 LLM 配置不完整，无法执行远程连通性测试。",
        )

    result = await _call_with_provider_chain_async(
        prompt="ping",
        context=None,
        system_prompt="Reply with OK only.",
        temperature=0.0,
        max_tokens=16,
    )

    if not result.ok:
        return build_llm_diagnostics_result(
            checked_remote=True,
            request_ok=False,
            status_code=result.status_code,
            error_message=preview_text(
                result.error or result.output,
                limit=DIAGNOSTIC_ERROR_LIMIT,
            ),
            provider_used=result.provider_name,
            fallback_used=result.fallback_used,
        )

    return build_llm_diagnostics_result(
        checked_remote=True,
        request_ok=True,
        status_code=result.status_code,
        response_preview=preview_text(result.output),
        provider_used=result.provider_name,
        fallback_used=result.fallback_used,
    )


async def call_llm(
    prompt: str,
    context: str | None = None,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
) -> LLMCallResult:
    return await _call_with_provider_chain_async(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt or settings.llm_system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def call_llm_sync(
    prompt: str,
    context: str | None = None,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
) -> LLMCallResult:
    return _call_with_provider_chain_sync(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt or settings.llm_system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
