import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
MESSAGE_STREAM_POLL_INTERVAL_SECONDS = 0.25


async def _send_message_batch(
    websocket: WebSocket,
    *,
    since_id: str | None,
) -> str | None:
    messages = message_queue.get_messages(since_id)
    response = build_messages_response(messages)
    await websocket.send_json(response.model_dump(by_alias=True, mode="json"))
    if not messages:
        return since_id
    return str(messages[-1].get("_id") or since_id or "")


@router.get("", response_model=MessagesResponse)
async def get_messages(since_id: MessagesSinceIdQuery = None):
    messages = message_queue.get_messages(since_id)
    return build_messages_response(messages)


@router.delete("", response_model=ClearMessagesResponse)
async def clear_messages():
    message_queue.clear()
    return build_clear_messages_response()


@router.websocket("/ws")
async def stream_messages(websocket: WebSocket):
    since_id = (websocket.query_params.get("since_id") or "").strip() or None
    await websocket.accept()
    since_id = await _send_message_batch(websocket, since_id=since_id)

    try:
        while True:
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=MESSAGE_STREAM_POLL_INTERVAL_SECONDS,
                )
            except TimeoutError:
                since_id = await _send_message_batch(websocket, since_id=since_id)
                continue
    except WebSocketDisconnect:
        return
