from typing import Any

import httpx

from backend.app.core.config import settings


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


def unconfigured_message(prompt: str, context: str | None = None) -> str:
    return (
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


def parse_chat_response(data: dict[str, Any], endpoint: str) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return (
            "大模型接口响应中缺少 choices。\n\n"
            f"endpoint: {endpoint}\n"
            f"raw_json: {data}"
        )

    message = choices[0].get("message", {})
    content = normalize_message_content(message.get("content"))
    if content:
        return content

    return (
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


async def call_llm(
    prompt: str,
    context: str | None = None,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.3,
) -> str:
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
        return build_status_error_message(exc, endpoint)
    except httpx.RequestError as exc:
        return build_request_error_message(exc, endpoint)

    try:
        data = response.json()
    except ValueError:
        return build_invalid_json_message(response.text, endpoint)

    return parse_chat_response(data, endpoint)


def call_llm_sync(
    prompt: str,
    context: str | None = None,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.3,
) -> str:
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
        return build_status_error_message(exc, endpoint)
    except httpx.RequestError as exc:
        return build_request_error_message(exc, endpoint)

    try:
        data = response.json()
    except ValueError:
        return build_invalid_json_message(response.text, endpoint)

    return parse_chat_response(data, endpoint)
