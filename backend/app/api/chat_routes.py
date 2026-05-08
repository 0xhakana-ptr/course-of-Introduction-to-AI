from fastapi import APIRouter, BackgroundTasks

from .error_responses import COMMON_ERROR_RESPONSES
from .query_params import SessionListLimitQuery, SessionListOffsetQuery
from .route_support import (
    build_chat_response,
    build_session_info,
    schedule_run_execution,
)
from ..schemas import (
    ChatRequest,
    ChatResponse,
    ClearConversationResponse,
    ConversationSessionListResponse,
    ConversationSessionMetadataResponse,
)
from ..services.chat_interface import generate_chat_response
from ..storage.conversation_store import conversation_store


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses=COMMON_ERROR_RESPONSES,
)
@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None

    result = await generate_chat_response(
        prompt,
        context,
        req.session_id,
        schedule_run=lambda run_id: schedule_run_execution(background_tasks, run_id),
    )
    return build_chat_response(result)


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
    offset: SessionListOffsetQuery = 0,
    limit: SessionListLimitQuery = 20,
):
    total, items = conversation_store.list_sessions(offset=offset, limit=limit)
    return ConversationSessionListResponse(
        ok=True,
        total=total,
        offset=offset,
        limit=limit,
        items=[
            build_session_info(str(item.get("session_id") or ""), item)
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

    session_info = build_session_info(session_id, metadata)
    return ConversationSessionMetadataResponse(
        ok=True,
        exists=True,
        **session_info.model_dump(),
    )
