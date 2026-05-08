from fastapi import APIRouter

from .error_responses import COMMON_ERROR_RESPONSES
from .query_params import MessagesSinceIdQuery
from .route_support import build_clear_messages_response, build_messages_response
from ..message_queue import message_queue
from ..schemas import ClearMessagesResponse, MessagesResponse


router = APIRouter(
    prefix="/messages",
    tags=["messages"],
    responses=COMMON_ERROR_RESPONSES,
)


@router.get("", response_model=MessagesResponse)
async def get_messages(since_id: MessagesSinceIdQuery = None):
    messages = message_queue.get_messages(since_id)
    return build_messages_response(messages)


@router.delete("", response_model=ClearMessagesResponse)
async def clear_messages():
    message_queue.clear()
    return build_clear_messages_response()
