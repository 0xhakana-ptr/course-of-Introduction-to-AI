from fastapi import APIRouter, BackgroundTasks

from ..schemas import ChatRequest, ChatResponse, ClearConversationResponse
from ..services.chat_interface import generate_chat_response
from ..services.run_interface import execute_run
from ..storage.conversation_store import conversation_store


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
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


@router.delete("/chat/sessions/{session_id}", response_model=ClearConversationResponse)
async def clear_chat_session(session_id: str):
    cleared = conversation_store.clear_session(session_id)
    return ClearConversationResponse(
        ok=True,
        session_id=session_id,
        cleared=cleared,
        message="会话已清空。" if cleared else "会话不存在或已清空。",
    )
