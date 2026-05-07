from fastapi import APIRouter, Query

from ..message_queue import message_queue
from ..schemas import ClearMessagesResponse, MessagesResponse


router = APIRouter()


@router.get("/messages", response_model=MessagesResponse)
async def get_messages(since_id: str | None = Query(default=None)):
    messages = message_queue.get_messages(since_id)
    return MessagesResponse(
        ok=True,
        messages=messages,
        count=len(messages),
    )


@router.delete("/messages", response_model=ClearMessagesResponse)
async def clear_messages():
    message_queue.clear()
    return ClearMessagesResponse(
        ok=True,
        message="消息队列已清空",
    )
