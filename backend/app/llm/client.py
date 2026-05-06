from dataclasses import dataclass
from typing import Any

import httpx

from core.config import settings


@dataclass(slots=True)
class LLMCallResult:
    ok: bool
    output: str
    error: str | None = None


@dataclass(slots=True)
class LLMDiagnosticsResult:
    configured: bool
    api_key_present: bool
    base_url: str | None
    resolved_url: str | None
    model: str | None
    timeout_seconds: int
    checked_remote: bool = False
    request_ok: bool | None = None
    status_code: int | None = None
    response_preview: str | None = None
    error_message: str | None = None


DIAGNOSTIC_PREVIEW_LIMIT = 200
DIAGNOSTIC_ERROR_LIMIT = 500


def llm_is_configured() -> bool:
    return bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)


def resolve_chat_completions_url() -> str:
    base = settings.llm_base_url.rstrip("/")
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def preview_text(text: str, limit: int = DIAGNOSTIC_PREVIEW_LIMIT) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def failure_result(message: str) -> LLMCallResult:
    return LLMCallResult(ok=False, output=message, error=message)


def success_result(message: str) -> LLMCallResult:
    return LLMCallResult(ok=True, output=message, error=None)


def unconfigured_message(prompt: str, context: str | None = None) -> LLMCallResult:
    return failure_result(
        "当前还没有配置真实大模型连接信息。\n\n"
        "请至少设置以下环境变量：\n"
        "- LLM_BASE_URL\n"
        "- LLM_API_KEY\n"
        "- LLM_MODEL\n\n"
        f"收到的 prompt: {prompt}\n"
        f"context: {context or '(none)'}"
    )


def build_messages(prompt: str, context: str | None, system_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    if context:
        messages.append(
            {
                "role": "system",
                "content": f"Recent conversation context:\n{context}",
            }
        )
    messages.append({"role": "user", "content": prompt})
    return messages


def build_payload(
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
) -> dict[str, object]:
    return {
        "model": settings.llm_model,
        "messages": build_messages(prompt, context, system_prompt),
        "temperature": temperature,
    }


def build_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def parse_chat_response(data: dict[str, Any], endpoint: str) -> LLMCallResult:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return failure_result(
            "大模型接口响应中缺少 choices。\n\n"
            f"endpoint: {endpoint}\n"
            f"raw_json: {data}"
        )

    message = choices[0].get("message", {})
    content = normalize_message_content(message.get("content"))
    if content:
        return success_result(content)

    return failure_result(
        "大模型接口已返回响应，但没有提取到有效文本内容。\n\n"
        f"endpoint: {endpoint}\n"
        f"raw_json: {data}"
    )


def build_status_error_message(exc: httpx.HTTPStatusError, endpoint: str) -> str:
    body = exc.response.text.strip()
    return (
        "大模型接口返回了错误状态码。\n\n"
        f"status: {exc.response.status_code}\n"
        f"endpoint: {endpoint}\n"
        f"body: {body or '(empty)'}"
    )


def build_request_error_message(exc: httpx.RequestError, endpoint: str) -> str:
    return (
        "调用大模型接口失败。\n\n"
        f"endpoint: {endpoint}\n"
        f"error: {exc}"
    )


def build_invalid_json_message(response_text: str, endpoint: str) -> str:
    return (
        "大模型接口返回了无法解析的响应。\n\n"
        f"endpoint: {endpoint}\n"
        f"raw: {response_text.strip() or '(empty)'}"
    )


def build_llm_diagnostics_result(
    *,
    checked_remote: bool = False,
    request_ok: bool | None = None,
    status_code: int | None = None,
    response_preview: str | None = None,
    error_message: str | None = None,
) -> LLMDiagnosticsResult:
    resolved_url = resolve_chat_completions_url()
    return LLMDiagnosticsResult(
        configured=llm_is_configured(),
        api_key_present=bool(settings.llm_api_key),
        base_url=settings.llm_base_url or None,
        resolved_url=resolved_url or None,
        model=settings.llm_model or None,
        timeout_seconds=settings.llm_timeout_seconds,
        checked_remote=checked_remote,
        request_ok=request_ok,
        status_code=status_code,
        response_preview=response_preview,
        error_message=error_message,
    )


async def diagnose_llm(*, check_remote: bool = False) -> LLMDiagnosticsResult:
    diagnostics = build_llm_diagnostics_result()
    if not check_remote:
        return diagnostics

    endpoint = diagnostics.resolved_url
    if not diagnostics.configured or not endpoint:
        return build_llm_diagnostics_result(
            checked_remote=False,
            request_ok=False,
            error_message="当前 LLM 配置不完整，无法执行远程连通性测试。",
        )

    payload = build_payload(
        prompt="ping",
        context=None,
        system_prompt="Reply with OK only.",
        temperature=0.0,
    )
    payload["max_tokens"] = 16

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(endpoint, json=payload, headers=build_headers())
            status_code = response.status_code
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return build_llm_diagnostics_result(
            checked_remote=True,
            request_ok=False,
            status_code=exc.response.status_code,
            error_message=preview_text(
                build_status_error_message(exc, endpoint),
                limit=DIAGNOSTIC_ERROR_LIMIT,
            ),
        )
    except httpx.RequestError as exc:
        return build_llm_diagnostics_result(
            checked_remote=True,
            request_ok=False,
            error_message=preview_text(
                build_request_error_message(exc, endpoint),
                limit=DIAGNOSTIC_ERROR_LIMIT,
            ),
        )

    try:
        data = response.json()
    except ValueError:
        return build_llm_diagnostics_result(
            checked_remote=True,
            request_ok=False,
            status_code=status_code,
            error_message=preview_text(
                build_invalid_json_message(response.text, endpoint),
                limit=DIAGNOSTIC_ERROR_LIMIT,
            ),
        )

    parsed = parse_chat_response(data, endpoint)
    if not parsed.ok:
        return build_llm_diagnostics_result(
            checked_remote=True,
            request_ok=False,
            status_code=status_code,
            error_message=preview_text(
                parsed.error or parsed.output,
                limit=DIAGNOSTIC_ERROR_LIMIT,
            ),
        )

    return build_llm_diagnostics_result(
        checked_remote=True,
        request_ok=True,
        status_code=status_code,
        response_preview=preview_text(parsed.output),
    )


async def call_llm(
    prompt: str,
    context: str | None = None,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.3,
) -> LLMCallResult:
    if not llm_is_configured():
        return unconfigured_message(prompt, context)

    endpoint = resolve_chat_completions_url()
    payload = build_payload(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt or settings.llm_system_prompt,
        temperature=temperature,
    )

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(endpoint, json=payload, headers=build_headers())
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return failure_result(build_status_error_message(exc, endpoint))
    except httpx.RequestError as exc:
        return failure_result(build_request_error_message(exc, endpoint))

    try:
        data = response.json()
    except ValueError:
        return failure_result(build_invalid_json_message(response.text, endpoint))

    return parse_chat_response(data, endpoint)


def call_llm_sync(
    prompt: str,
    context: str | None = None,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.3,
) -> LLMCallResult:
    if not llm_is_configured():
        return unconfigured_message(prompt, context)

    endpoint = resolve_chat_completions_url()
    payload = build_payload(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt or settings.llm_system_prompt,
        temperature=temperature,
    )

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=build_headers())
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return failure_result(build_status_error_message(exc, endpoint))
    except httpx.RequestError as exc:
        return failure_result(build_request_error_message(exc, endpoint))

    try:
        data = response.json()
    except ValueError:
        return failure_result(build_invalid_json_message(response.text, endpoint))

    return parse_chat_response(data, endpoint)