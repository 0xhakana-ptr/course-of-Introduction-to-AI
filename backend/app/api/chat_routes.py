from fastapi import APIRouter, BackgroundTasks, Query

from .error_responses import COMMON_ERROR_RESPONSES
from ..schemas import (
    ChatRequest,
    ChatResponse,
    ClearConversationResponse,
    ConversationSessionInfo,
    ConversationSessionListResponse,
    ConversationSessionMetadataResponse,
)
from ..services.chat_interface import generate_chat_response
from ..services.run_interface import execute_run
from ..storage.conversation_store import conversation_store


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses=COMMON_ERROR_RESPONSES,
)


def _build_session_info(session_id: str, metadata: dict[str, object]) -> ConversationSessionInfo:
    return ConversationSessionInfo(
        session_id=session_id,
        message_count=int(metadata.get("message_count") or 0),
        recent_message_count=int(metadata.get("recent_message_count") or 0),
        compressed_message_count=int(metadata.get("compressed_message_count") or 0),
        has_compressed_context=bool(metadata.get("has_compressed_context", False)),
        has_summary_cache=bool(metadata.get("compressed_summary") or metadata.get("has_summary_cache")),
        summary_preview=(
            str(metadata.get("summary_preview"))
            if metadata.get("summary_preview") is not None
            else None
        ),
        context_strategy_version=(
            int(metadata.get("context_strategy_version"))
            if metadata.get("context_strategy_version") is not None
            else None
        ),
        last_message_at=(
            str(metadata.get("last_message_at"))
            if metadata.get("last_message_at") is not None
            else None
        ),
        updated_at=(
            str(metadata.get("updated_at"))
            if metadata.get("updated_at") is not None
            else None
        ),
    )


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None

    def schedule_run_execution(run_id: str) -> None:
        background_tasks.add_task(execute_run, run_id)

    result = await generate_chat_response(
        prompt,
        context,
        req.session_id,
        schedule_run=schedule_run_execution,
    )
    return ChatResponse(
        ok=result.ok,
        intent=result.intent,
        output=result.output,
        error=result.error,
        session_id=result.session_id,
        run_id=result.run_id,
    )


@router.delete("/sessions/{session_id}", response_model=ClearConversationResponse)
async def clear_chat_session(session_id: str):
    cleared = conversation_store.clear_session(session_id)
    return ClearConversationResponse(
        ok=True,
        session_id=session_id,
        cleared=cleared,
        message="会话已清空。" if cleared else "会话不存在或已清空。",
    )


@router.get("/sessions", response_model=ConversationSessionListResponse)
async def list_chat_sessions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
):
    total, items = conversation_store.list_sessions(offset=offset, limit=limit)
    return ConversationSessionListResponse(
        ok=True,
        total=total,
        offset=offset,
        limit=limit,
        items=[
            _build_session_info(str(item.get("session_id") or ""), item)
            for item in items
        ],
    )


@router.get("/sessions/{session_id}", response_model=ConversationSessionMetadataResponse)
async def get_chat_session_metadata(session_id: str):
    metadata = conversation_store.get_session_metadata(session_id)
    if metadata is None:
        return ConversationSessionMetadataResponse(
            ok=True,
            session_id=session_id,
            exists=False,
        )

    session_info = _build_session_info(session_id, metadata)
    return ConversationSessionMetadataResponse(
        ok=True,
        exists=True,
        **session_info.model_dump(),
    )
