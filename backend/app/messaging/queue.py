import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .runtime_events import normalize_frontend_message_payload


logger = logging.getLogger(__name__)


class MessageQueue:
    """消息队列，用于存储待发送的消息"""

    def __init__(self):
        self.messages: list[dict[str, Any]] = []
        self.max_size = 1000
        self._lock = threading.RLock()
        self._counter = 0
        self._message_index: dict[str, int] = {}

    def _next_message_id(self) -> str:
        self._counter += 1
        return f"msg_{int(time.time() * 1000)}_{self._counter}"

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _rebuild_index(self) -> None:
        self._message_index = {
            str(message["_id"]): index
            for index, message in enumerate(self.messages)
            if message.get("_id") is not None
        }

    def add_message(self, message: dict[str, Any]) -> str:
        with self._lock:
            message_id = self._next_message_id()
            stored_message = normalize_frontend_message_payload(message)
            stored_message["_id"] = message_id
            stored_message["_timestamp"] = self._timestamp()
            self.messages.append(stored_message)
            self._message_index[message_id] = len(self.messages) - 1
            if len(self.messages) > self.max_size:
                self.messages = self.messages[-self.max_size:]
                self._rebuild_index()
            total = len(self.messages)
        logger.debug(
            "Message queued: id=%s type=%s total=%s",
            message_id,
            message.get("type"),
            total,
        )
        return message_id

    def get_messages(self, since_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if since_id is None:
                return self.messages.copy()
            index = self._message_index.get(since_id)
            if index is None:
                # Client might be holding an evicted/unknown since_id (queue is bounded).
                # Returning the current queue lets the client resync instead of getting
                # stuck receiving empty arrays forever.
                return self.messages.copy()
            result = self.messages[index + 1:]
        if result:
            logger.debug("Messages fetched: count=%s since_id=%s", len(result), since_id)
        return result

    def clear(self) -> None:
        with self._lock:
            count = len(self.messages)
            self.messages.clear()
            self._message_index.clear()
        logger.info("Message queue cleared: count=%s", count)


message_queue = MessageQueue()
