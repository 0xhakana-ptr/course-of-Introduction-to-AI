import threading
from uuid import uuid4

from ..core.config import settings
from .run_store import utc_now_iso


ConversationMessage = dict[str, str]


class ConversationStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[ConversationMessage]] = {}
        self._lock = threading.RLock()

    def get_or_create_session_id(self, session_id: str | None = None) -> str:
        normalized = (session_id or "").strip()
        with self._lock:
            if not normalized:
                normalized = str(uuid4())
            self._sessions.setdefault(normalized, [])
            return normalized

    def append_message(self, session_id: str, role: str, content: str) -> None:
        text = content.strip()
        if not text:
            return

        with self._lock:
            messages = self._sessions.setdefault(session_id, [])
            messages.append(
                {
                    "role": role,
                    "content": text,
                    "created_at": utc_now_iso(),
                }
            )
            max_messages = settings.conversation_history_max_messages
            if max_messages > 0 and len(messages) > max_messages:
                del messages[: len(messages) - max_messages]

    def append_exchange(
        self,
        session_id: str,
        *,
        user_prompt: str,
        assistant_output: str | None = None,
    ) -> None:
        self.append_message(session_id, "user", user_prompt)
        if assistant_output:
            self.append_message(session_id, "assistant", assistant_output)

    def get_messages(self, session_id: str) -> list[ConversationMessage]:
        with self._lock:
            return [dict(message) for message in self._sessions.get(session_id, [])]

    def build_context(self, session_id: str, external_context: str | None = None) -> str | None:
        chunks: list[str] = []
        client_context = (external_context or "").strip()
        if client_context:
            chunks.append(f"Client provided context:\n{client_context}")

        messages = self.get_messages(session_id)
        if messages:
            history_lines = [
                f"{message['role'].title()}: {message['content']}"
                for message in messages
                if message.get("role") and message.get("content")
            ]
            if history_lines:
                chunks.append("Stored conversation history:\n" + "\n".join(history_lines))

        combined = "\n\n".join(chunks).strip()
        if not combined:
            return None

        max_chars = settings.chat_context_max_chars
        if max_chars > 0 and len(combined) > max_chars:
            return combined[-max_chars:]
        return combined

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()


conversation_store = ConversationStore()
