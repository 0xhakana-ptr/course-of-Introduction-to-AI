import hashlib
import json
import threading
import time
from pathlib import Path
from uuid import uuid4

from ..core.config import settings
from .run_store import utc_now_iso


ConversationMessage = dict[str, str]


class ConversationStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[ConversationMessage]] = {}
        self._lock = threading.RLock()
        self._last_cleanup_monotonic = 0.0

    def _get_conversation_dir(self) -> Path:
        conversation_dir = settings.conversation_dir
        conversation_dir.mkdir(parents=True, exist_ok=True)
        return conversation_dir

    def _get_session_path(self, session_id: str) -> Path:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return self._get_conversation_dir() / f"{digest}.json"

    def _normalize_message(self, message: object) -> ConversationMessage | None:
        if not isinstance(message, dict):
            return None

        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        created_at = str(message.get("created_at") or "").strip()
        if not role or not content:
            return None

        normalized: ConversationMessage = {
            "role": role,
            "content": content,
        }
        if created_at:
            normalized["created_at"] = created_at
        return normalized

    def _trim_messages(self, messages: list[ConversationMessage]) -> list[ConversationMessage]:
        max_messages = settings.conversation_history_max_messages
        if max_messages > 0 and len(messages) > max_messages:
            return messages[-max_messages:]
        return messages

    def _list_session_paths(self) -> list[Path]:
        conversation_dir = settings.conversation_dir
        if not conversation_dir.exists():
            return []
        return [path for path in conversation_dir.glob("*.json") if path.is_file()]

    def _delete_session_path(self, session_path: Path) -> bool:
        try:
            session_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def _session_mtime(self, session_path: Path) -> float:
        try:
            return session_path.stat().st_mtime
        except OSError:
            return 0.0

    def _prune_storage_locked(self) -> int:
        removed_count = 0
        session_paths = self._list_session_paths()
        if not session_paths:
            return 0

        ttl_seconds = settings.conversation_session_ttl_seconds
        current_time = time.time()
        remaining_paths: list[Path] = []

        for session_path in session_paths:
            if ttl_seconds > 0 and (current_time - self._session_mtime(session_path)) > ttl_seconds:
                removed_count += int(self._delete_session_path(session_path))
                continue
            remaining_paths.append(session_path)

        max_persisted_sessions = settings.conversation_max_persisted_sessions
        if max_persisted_sessions > 0 and len(remaining_paths) > max_persisted_sessions:
            remaining_paths.sort(key=self._session_mtime, reverse=True)
            for session_path in remaining_paths[max_persisted_sessions:]:
                removed_count += int(self._delete_session_path(session_path))

        if removed_count > 0:
            self._sessions.clear()
        return removed_count

    def _maybe_prune_storage_locked(self, *, force: bool = False) -> int:
        current_monotonic = time.monotonic()
        interval_seconds = settings.conversation_cleanup_interval_seconds
        if (
            not force
            and interval_seconds > 0
            and (current_monotonic - self._last_cleanup_monotonic) < interval_seconds
        ):
            return 0

        removed_count = self._prune_storage_locked()
        self._last_cleanup_monotonic = current_monotonic
        return removed_count

    def _load_session_from_disk_locked(self, session_id: str) -> list[ConversationMessage]:
        cached = self._sessions.get(session_id)
        if cached is not None:
            return cached

        messages: list[ConversationMessage] = []
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                payload = json.loads(session_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None

            raw_messages: object = None
            if isinstance(payload, dict):
                raw_messages = payload.get("messages")
            elif isinstance(payload, list):
                raw_messages = payload

            if isinstance(raw_messages, list):
                messages = [
                    normalized
                    for item in raw_messages
                    if (normalized := self._normalize_message(item)) is not None
                ]
                messages = self._trim_messages(messages)

        self._sessions[session_id] = messages
        return messages

    def _write_session_locked(self, session_id: str, messages: list[ConversationMessage]) -> None:
        session_path = self._get_session_path(session_id)
        payload = {
            "session_id": session_id,
            "messages": messages,
            "updated_at": utc_now_iso(),
        }
        session_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_or_create_session_id(self, session_id: str | None = None) -> str:
        normalized = (session_id or "").strip()
        with self._lock:
            if not normalized:
                normalized = str(uuid4())
            self._maybe_prune_storage_locked()
            self._load_session_from_disk_locked(normalized)
            return normalized

    def append_message(self, session_id: str, role: str, content: str) -> None:
        text = content.strip()
        if not text:
            return

        with self._lock:
            self._maybe_prune_storage_locked()
            messages = self._load_session_from_disk_locked(session_id)
            messages.append(
                {
                    "role": role,
                    "content": text,
                    "created_at": utc_now_iso(),
                }
            )
            trimmed_messages = self._trim_messages(messages)
            if trimmed_messages is not messages:
                messages[:] = trimmed_messages
            self._write_session_locked(session_id, messages)

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
            self._maybe_prune_storage_locked()
            messages = self._load_session_from_disk_locked(session_id)
            return [dict(message) for message in messages]

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
            removed_from_cache = self._sessions.pop(session_id, None) is not None
            session_path = self._get_session_path(session_id)
            removed_from_disk = False
            if session_path.exists():
                session_path.unlink()
                removed_from_disk = True
            return removed_from_cache or removed_from_disk

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._last_cleanup_monotonic = 0.0
            conversation_dir = settings.conversation_dir
            if not conversation_dir.exists():
                return
            for session_path in conversation_dir.glob("*.json"):
                session_path.unlink()

    def prune_storage(self, *, force: bool = False) -> int:
        with self._lock:
            return self._maybe_prune_storage_locked(force=force)


conversation_store = ConversationStore()
