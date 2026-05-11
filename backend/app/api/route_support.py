from collections.abc import Mapping
from dataclasses import asdict

from fastapi import BackgroundTasks

from ..llm.client import LLMDiagnosticsResult
from ..schemas import (
    ChatResponse,
    ClearConversationResponse,
    ClearMessagesResponse,
    ConversationMessageItem,
    ConversationSessionContextResponse,
    ConversationSessionInfo,
    ConversationSessionListResponse,
    ConversationSessionMetadataResponse,
    LLMDiagnosticsResponse,
    MessagesResponse,
)
from ..services.chat_action.types import ChatServiceResult
from ..services.run_interface import execute_run


SessionResponseT = ConversationSessionMetadataResponse | ConversationSessionContextResponse


def schedule_run_execution(background_tasks: BackgroundTasks, run_id: str) -> None:
    background_tasks.add_task(execute_run, run_id)


def _as_int(metadata: Mapping[str, object], key: str) -> int:
    return int(metadata.get(key) or 0)


def _as_bool(metadata: Mapping[str, object], key: str) -> bool:
    return bool(metadata.get(key, False))


def _as_optional_str(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


def _as_optional_int(metadata: Mapping[str, object], key: str) -> int | None:
    value = metadata.get(key)
    if value is None:
        return None
    return int(value)


def normalize_prompt_and_context(prompt: str, context: str | None) -> tuple[str, str | None]:
    return prompt.strip(), (context or "").strip() or None


def _build_session_info_payload(
    session_id: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "message_count": _as_int(metadata, "message_count"),
        "recent_message_count": _as_int(metadata, "recent_message_count"),
        "compressed_message_count": _as_int(metadata, "compressed_message_count"),
        "has_compressed_context": _as_bool(metadata, "has_compressed_context"),
        "has_summary_cache": bool(
            metadata.get("compressed_summary") or metadata.get("has_summary_cache")
        ),
        "summary_preview": _as_optional_str(metadata, "summary_preview"),
        "context_strategy_version": _as_optional_int(metadata, "context_strategy_version"),
        "last_message_at": _as_optional_str(metadata, "last_message_at"),
        "updated_at": _as_optional_str(metadata, "updated_at"),
    }


def _build_missing_session_response(
    response_cls: type[SessionResponseT],
    session_id: str,
) -> SessionResponseT:
    return response_cls(
        session_id=session_id,
        ok=True,
        exists=False,
    )


def _normalize_metadata_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _build_recent_message_items(messages: object) -> list[ConversationMessageItem]:
    if not isinstance(messages, list):
        return []
    return [
        ConversationMessageItem(
            role=str(message.get("role") or "system"),
            content=str(message.get("content") or ""),
            created_at=_as_optional_str(message, "created_at"),
        )
        for message in messages
        if isinstance(message, Mapping)
        and str(message.get("role") or "").strip()
        and str(message.get("content") or "").strip()
    ]


def build_session_info(session_id: str, metadata: Mapping[str, object]) -> ConversationSessionInfo:
    return ConversationSessionInfo(**_build_session_info_payload(session_id, metadata))


def build_session_info_list(items: list[Mapping[str, object]]) -> list[ConversationSessionInfo]:
    return [
        build_session_info(str(item.get("session_id") or ""), item)
        for item in items
    ]


def build_session_list_response(
    *,
    total: int,
    offset: int,
    limit: int,
    items: list[Mapping[str, object]],
) -> ConversationSessionListResponse:
    return ConversationSessionListResponse(
        ok=True,
        total=total,
        offset=offset,
        limit=limit,
        items=build_session_info_list(items),
    )


def build_chat_response(result: ChatServiceResult) -> ChatResponse:
    return ChatResponse(
        ok=result.ok,
        intent=result.intent,
        output=result.output,
        error=result.error,
        session_id=result.session_id,
        run_id=result.run_id,
        runtime_mode=result.runtime_mode,
        route_scope=result.route_scope,
        runtime_warning=result.runtime_warning,
    )


def build_clear_conversation_response(
    session_id: str,
    *,
    cleared: bool,
) -> ClearConversationResponse:
    return ClearConversationResponse(
        ok=True,
        session_id=session_id,
        cleared=cleared,
        message="会话已清空。" if cleared else "会话不存在或已清空。",
    )


def build_session_metadata_response(
    session_id: str,
    metadata: Mapping[str, object] | None,
) -> ConversationSessionMetadataResponse:
    if metadata is None:
        return _build_missing_session_response(ConversationSessionMetadataResponse, session_id)

    return ConversationSessionMetadataResponse(
        ok=True,
        exists=True,
        **_build_session_info_payload(session_id, metadata),
    )


def build_session_context_response(
    session_id: str,
    snapshot: Mapping[str, object] | None,
) -> ConversationSessionContextResponse:
    if snapshot is None:
        return _build_missing_session_response(ConversationSessionContextResponse, session_id)

    metadata_mapping = _normalize_metadata_mapping(snapshot.get("metadata"))
    return ConversationSessionContextResponse(
        ok=True,
        exists=True,
        context_text=_as_optional_str(snapshot, "context_text"),
        context_char_count=_as_int(snapshot, "context_char_count"),
        compressed_summary=_as_optional_str(snapshot, "compressed_summary"),
        recent_messages=_build_recent_message_items(snapshot.get("recent_messages")),
        **_build_session_info_payload(session_id, metadata_mapping),
    )


def build_messages_response(messages: list[dict[str, object]]) -> MessagesResponse:
    return MessagesResponse(
        ok=True,
        messages=messages,
        count=len(messages),
    )


def build_clear_messages_response() -> ClearMessagesResponse:
    return ClearMessagesResponse(
        ok=True,
        message="消息队列已清空",
    )


def build_llm_diagnostics_response(result: LLMDiagnosticsResult) -> LLMDiagnosticsResponse:
    return LLMDiagnosticsResponse(**asdict(result))
