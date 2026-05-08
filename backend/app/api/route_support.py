from collections.abc import Mapping
from dataclasses import asdict

from fastapi import BackgroundTasks

from ..llm.client import LLMDiagnosticsResult
from ..schemas import ChatResponse, ConversationSessionInfo, LLMDiagnosticsResponse
from ..services.chat_action.types import ChatServiceResult
from ..services.run_interface import execute_run


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


def build_session_info(session_id: str, metadata: Mapping[str, object]) -> ConversationSessionInfo:
    return ConversationSessionInfo(
        session_id=session_id,
        message_count=_as_int(metadata, "message_count"),
        recent_message_count=_as_int(metadata, "recent_message_count"),
        compressed_message_count=_as_int(metadata, "compressed_message_count"),
        has_compressed_context=_as_bool(metadata, "has_compressed_context"),
        has_summary_cache=bool(
            metadata.get("compressed_summary") or metadata.get("has_summary_cache")
        ),
        summary_preview=_as_optional_str(metadata, "summary_preview"),
        context_strategy_version=_as_optional_int(metadata, "context_strategy_version"),
        last_message_at=_as_optional_str(metadata, "last_message_at"),
        updated_at=_as_optional_str(metadata, "updated_at"),
    )


def build_chat_response(result: ChatServiceResult) -> ChatResponse:
    return ChatResponse(
        ok=result.ok,
        intent=result.intent,
        output=result.output,
        error=result.error,
        session_id=result.session_id,
        run_id=result.run_id,
    )


def build_llm_diagnostics_response(result: LLMDiagnosticsResult) -> LLMDiagnosticsResponse:
    return LLMDiagnosticsResponse(**asdict(result))
