from fastapi import APIRouter, BackgroundTasks

from .error_responses import COMMON_ERROR_RESPONSES
from .query_params import SessionListLimitQuery, SessionListOffsetQuery
from .route_support import (
    build_chat_response,
    build_clear_conversation_response,
    build_session_context_response,
    build_session_list_response,
    build_session_metadata_response,
    normalize_prompt_and_context,
    schedule_run_execution,
)
from ..schemas import (
    ChatRequest,
    ChatResponse,
    ClearConversationResponse,
    ConversationSessionContextResponse,
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
    prompt, context = normalize_prompt_and_context(req.prompt, req.context)

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
    return build_clear_conversation_response(session_id, cleared=cleared)


@router.get("/sessions", response_model=ConversationSessionListResponse)
async def list_chat_sessions(
    offset: SessionListOffsetQuery = 0,
    limit: SessionListLimitQuery = 20,
):
    total, items = conversation_store.list_sessions(offset=offset, limit=limit)
    return build_session_list_response(
        total=total,
        offset=offset,
        limit=limit,
        items=items,
    )


@router.get("/sessions/{session_id}", response_model=ConversationSessionMetadataResponse)
async def get_chat_session_metadata(session_id: str):
    metadata = conversation_store.get_session_metadata(session_id)
    return build_session_metadata_response(session_id, metadata)


@router.get("/sessions/{session_id}/context", response_model=ConversationSessionContextResponse)
async def get_chat_session_context(session_id: str):
    snapshot = conversation_store.get_context_snapshot(session_id)
    return build_session_context_response(session_id, snapshot)
