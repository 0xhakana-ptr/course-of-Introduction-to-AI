import hashlib
import json
import threading
import time
from pathlib import Path
from uuid import uuid4

from ..core.config import settings
from ..core.text_utils import build_preview
from .run_store import utc_now_iso


ConversationMessage = dict[str, str]
ConversationSessionMetadata = dict[str, str | int | bool | None]
ConversationSessionListItem = dict[str, str | int | bool | None]
ConversationContextSnapshot = dict[str, object]
CONTEXT_SUMMARY_PREVIEW_LIMIT = 120
SESSION_SUMMARY_PREVIEW_LIMIT = 240
SESSION_TITLE_PREVIEW_LIMIT = 40
CONTEXT_STRATEGY_VERSION = 1
CONTEXT_TRUNCATED_MARKER = "\n... (context truncated)"


class ConversationStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[ConversationMessage]] = {}
        self._session_metadata: dict[str, ConversationSessionMetadata] = {}
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

    def _normalize_messages(self, raw_messages: object) -> list[ConversationMessage]:
        if not isinstance(raw_messages, list):
            return []

        normalized_messages = [
            normalized
            for item in raw_messages
            if (normalized := self._normalize_message(item)) is not None
        ]
        return self._trim_messages(normalized_messages)

    def _trim_messages(self, messages: list[ConversationMessage]) -> list[ConversationMessage]:
        max_messages = settings.conversation_history_max_messages
        if max_messages > 0 and len(messages) > max_messages:
            return messages[-max_messages:]
        return messages

    def _split_messages_for_context(
        self,
        messages: list[ConversationMessage],
    ) -> tuple[list[ConversationMessage], list[ConversationMessage]]:
        recent_count = settings.conversation_context_recent_messages
        if recent_count <= 0:
            return [], messages
        return messages[:-recent_count], messages[-recent_count:]

    def _get_last_message_at(self, messages: list[ConversationMessage]) -> str | None:
        if not messages:
            return None
        return str(messages[-1].get("created_at") or "").strip() or None

    def _get_cached_compressed_summary(
        self,
        messages: list[ConversationMessage],
        metadata: ConversationSessionMetadata | None,
    ) -> str | None:
        if not self._is_metadata_compatible(messages, metadata):
            return None
        if metadata is None or metadata.get("compressed_summary") is None:
            return None
        summary = str(metadata.get("compressed_summary") or "").strip()
        return summary or None

    def _resolve_compressed_summary(
        self,
        messages: list[ConversationMessage],
        older_messages: list[ConversationMessage],
        metadata: ConversationSessionMetadata | None,
    ) -> str | None:
        if not older_messages:
            return None

        cached_summary = self._get_cached_compressed_summary(messages, metadata)
        if cached_summary is not None:
            return cached_summary
        return self._build_history_summary(older_messages)

    def _build_context_text(
        self,
        messages: list[ConversationMessage],
        *,
        metadata: ConversationSessionMetadata | None,
        external_context: str | None = None,
    ) -> str | None:
        chunks: list[str] = []
        client_context = self._clip_context_chunk(
            external_context,
            limit=settings.chat_external_context_max_chars,
        )
        if client_context:
            chunks.append(f"Client provided context:\n{client_context}")

        if messages:
            chunks.extend(self._build_history_context_sections(messages, metadata=metadata))

        combined = "\n\n".join(chunks).strip()
        if not combined:
            return None

        return self._clip_context_chunk(
            combined,
            limit=settings.chat_context_max_chars,
            keep_tail=True,
        )

    def _load_session_state_locked(
        self,
        session_id: str,
    ) -> tuple[list[ConversationMessage], ConversationSessionMetadata]:
        messages = list(self._load_session_from_disk_locked(session_id))
        metadata = self._session_metadata.get(session_id)
        if metadata is None:
            metadata = self._build_session_metadata(messages)
            self._session_metadata[session_id] = metadata
        return messages, metadata

    def _build_session_metadata(
        self,
        messages: list[ConversationMessage],
        *,
        updated_at: str | None = None,
    ) -> ConversationSessionMetadata:
        older_messages, recent_messages = self._split_messages_for_context(messages)
        compressed_summary = self._build_history_summary(older_messages)

        summary_preview: str | None = None
        if compressed_summary:
            summary_preview = build_preview(
                compressed_summary,
                limit=SESSION_SUMMARY_PREVIEW_LIMIT,
            )
        else:
            # For short sessions (no compressed history), use the first user prompt
            # as a stable session title in the chat history panel.
            first_user_message = next(
                (
                    str(m.get("content") or "").strip()
                    for m in messages
                    if str(m.get("role") or "").strip() == "user"
                ),
                "",
            )
            if first_user_message:
                summary_preview = build_preview(
                    first_user_message,
                    limit=SESSION_TITLE_PREVIEW_LIMIT,
                )

        return {
            "message_count": len(messages),
            "recent_message_count": len(recent_messages),
            "compressed_message_count": len(older_messages),
            "has_compressed_context": bool(older_messages),
            "compressed_summary": compressed_summary,
            "summary_preview": summary_preview,
            "last_message_at": self._get_last_message_at(messages),
            "updated_at": updated_at,
            "context_strategy_version": CONTEXT_STRATEGY_VERSION,
            "context_recent_messages_limit": settings.conversation_context_recent_messages,
            "context_summary_max_chars": settings.conversation_summary_max_chars,
        }

    def _normalize_session_metadata(
        self,
        metadata: object,
    ) -> ConversationSessionMetadata | None:
        if not isinstance(metadata, dict):
            return None

        normalized: ConversationSessionMetadata = {}
        int_fields = (
            "message_count",
            "recent_message_count",
            "compressed_message_count",
            "context_strategy_version",
            "context_recent_messages_limit",
            "context_summary_max_chars",
        )
        bool_fields = ("has_compressed_context",)
        text_fields = (
            "compressed_summary",
            "summary_preview",
            "last_message_at",
            "updated_at",
        )

        for field_name in int_fields:
            raw_value = metadata.get(field_name)
            if raw_value is None:
                continue
            try:
                normalized[field_name] = int(raw_value)
            except (TypeError, ValueError):
                continue

        for field_name in bool_fields:
            raw_value = metadata.get(field_name)
            if raw_value is None:
                continue
            normalized[field_name] = bool(raw_value)

        for field_name in text_fields:
            raw_value = metadata.get(field_name)
            if raw_value is None:
                normalized[field_name] = None
                continue
            text = str(raw_value).strip()
            normalized[field_name] = text or None

        return normalized

    def _is_metadata_compatible(
        self,
        messages: list[ConversationMessage],
        metadata: ConversationSessionMetadata | None,
    ) -> bool:
        if metadata is None:
            return False

        recent_limit = settings.conversation_context_recent_messages
        return (
            int(metadata.get("context_strategy_version") or 0) == CONTEXT_STRATEGY_VERSION
            and int(metadata.get("message_count") or -1) == len(messages)
            and int(metadata.get("context_recent_messages_limit") or -1) == recent_limit
            and int(metadata.get("context_summary_max_chars") or -1)
            == settings.conversation_summary_max_chars
        )

    def _set_session_cache_locked(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        *,
        updated_at: str | None = None,
        metadata: ConversationSessionMetadata | None = None,
    ) -> list[ConversationMessage]:
        self._sessions[session_id] = messages
        resolved_metadata = metadata
        if not self._is_metadata_compatible(messages, resolved_metadata):
            resolved_metadata = self._build_session_metadata(
                messages,
                updated_at=updated_at,
            )
        elif messages and not (resolved_metadata or {}).get("summary_preview"):
            # Backfill preview/title for older persisted sessions.
            resolved_metadata = self._build_session_metadata(
                messages,
                updated_at=updated_at,
            )
        elif updated_at and not resolved_metadata.get("updated_at"):
            resolved_metadata = {
                **resolved_metadata,
                "updated_at": updated_at,
            }
        self._session_metadata[session_id] = resolved_metadata
        return messages

    def _parse_session_payload(
        self,
        payload: object,
    ) -> tuple[str | None, list[ConversationMessage], str | None, ConversationSessionMetadata | None]:
        session_id: str | None = None
        updated_at: str | None = None
        metadata: ConversationSessionMetadata | None = None
        raw_messages: object = None

        if isinstance(payload, dict):
            session_id = str(payload.get("session_id") or "").strip() or None
            raw_messages = payload.get("messages")
            updated_at = str(payload.get("updated_at") or "").strip() or None
            metadata = self._normalize_session_metadata(payload.get("metadata"))
        elif isinstance(payload, list):
            raw_messages = payload

        return session_id, self._normalize_messages(raw_messages), updated_at, metadata

    def _build_history_line(
        self,
        message: ConversationMessage,
        *,
        preview_limit: int | None = None,
    ) -> str | None:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if not role or not content:
            return None
        if preview_limit is not None and preview_limit > 0:
            content = build_preview(content, limit=preview_limit)
        return f"{role.title()}: {content}"

    def _clip_context_chunk(
        self,
        text: str | None,
        *,
        limit: int,
        keep_tail: bool = False,
    ) -> str | None:
        raw = str(text or "").strip()
        if not raw:
            return None
        if limit <= 0 or len(raw) <= limit:
            return raw

        marker = CONTEXT_TRUNCATED_MARKER
        content_limit = max(limit - len(marker), 0)
        if content_limit <= 0:
            return raw[-limit:] if keep_tail else raw[:limit]

        clipped = raw[-content_limit:] if keep_tail else raw[:content_limit]
        return f"{clipped}{marker}"

    def _build_history_summary(self, messages: list[ConversationMessage]) -> str | None:
        if not messages:
            return None

        summary_limit = settings.conversation_summary_max_chars
        lines: list[str] = []
        current_length = 0

        for index, message in enumerate(messages):
            line = self._build_history_line(
                message,
                preview_limit=CONTEXT_SUMMARY_PREVIEW_LIMIT,
            )
            if line is None:
                continue

            extra_length = len(line) + (1 if lines else 0)
            if summary_limit > 0 and (current_length + extra_length) > summary_limit:
                omitted_count = len(messages) - index
                if omitted_count > 0:
                    lines.append(f"... ({omitted_count} earlier messages omitted)")
                break

            lines.append(line)
            current_length += extra_length

        return "\n".join(lines).strip() or None

    def _build_history_context_sections(
        self,
        messages: list[ConversationMessage],
        *,
        metadata: ConversationSessionMetadata | None = None,
    ) -> list[str]:
        if not messages:
            return []

        older_messages, recent_messages = self._split_messages_for_context(messages)
        if not older_messages:
            history_lines = [
                line
                for message in messages
                if (
                    line := self._build_history_line(
                        message,
                        preview_limit=settings.conversation_recent_message_max_chars,
                    )
                ) is not None
            ]
            if not history_lines:
                return []
            return ["Stored conversation history:\n" + "\n".join(history_lines)]

        sections: list[str] = []
        older_summary = self._resolve_compressed_summary(
            messages,
            older_messages,
            metadata,
        )
        if older_summary:
            sections.append(
                (
                    "Compressed earlier conversation summary:\n"
                    f"(covering {len(older_messages)} earlier messages)\n"
                    f"{older_summary}"
                )
            )

        recent_lines = [
            line
            for message in recent_messages
            if (
                line := self._build_history_line(
                    message,
                    preview_limit=settings.conversation_recent_message_max_chars,
                )
            ) is not None
        ]
        if recent_lines:
            sections.append("Recent stored conversation history:\n" + "\n".join(recent_lines))

        return sections

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
            self._session_metadata.clear()
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
        updated_at: str | None = None
        metadata: ConversationSessionMetadata | None = None
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                payload = json.loads(session_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            _, messages, updated_at, metadata = self._parse_session_payload(payload)

        return self._set_session_cache_locked(
            session_id,
            messages,
            updated_at=updated_at,
            metadata=metadata,
        )

    def _list_session_items_locked(self) -> list[ConversationSessionListItem]:
        items: list[ConversationSessionListItem] = []

        for session_path in self._list_session_paths():
            try:
                payload = json.loads(session_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            session_id, messages, updated_at, metadata = self._parse_session_payload(payload)
            if not session_id:
                continue

            self._set_session_cache_locked(
                session_id,
                messages,
                updated_at=updated_at,
                metadata=metadata,
            )
            resolved_metadata = self._session_metadata.get(session_id)
            if resolved_metadata is None:
                continue

            items.append(
                {
                    "session_id": session_id,
                    **resolved_metadata,
                    "has_summary_cache": bool(resolved_metadata.get("compressed_summary")),
                }
            )

        items.sort(
            key=lambda item: (
                str(item.get("updated_at") or item.get("last_message_at") or ""),
                int(item.get("message_count") or 0),
                str(item.get("session_id") or ""),
            ),
            reverse=True,
        )
        return items

    def _write_session_locked(self, session_id: str, messages: list[ConversationMessage]) -> None:
        session_path = self._get_session_path(session_id)
        updated_at = utc_now_iso()
        metadata = self._build_session_metadata(messages, updated_at=updated_at)
        payload = {
            "session_id": session_id,
            "messages": messages,
            "updated_at": updated_at,
            "metadata": metadata,
        }
        session_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._session_metadata[session_id] = metadata

    def _build_context_snapshot_locked(
        self,
        session_id: str,
        *,
        external_context: str | None = None,
    ) -> ConversationContextSnapshot | None:
        if not self._session_exists_locked(session_id):
            return None

        messages, metadata = self._load_session_state_locked(session_id)
        older_messages, recent_messages = self._split_messages_for_context(messages)
        compressed_summary = self._resolve_compressed_summary(
            messages,
            older_messages,
            metadata,
        )
        context_text = self._build_context_text(
            messages,
            metadata=metadata,
            external_context=external_context,
        )
        return {
            "session_id": session_id,
            "metadata": dict(metadata),
            "compressed_summary": compressed_summary,
            "recent_messages": [dict(message) for message in recent_messages],
            "context_text": context_text,
            "context_char_count": len(context_text or ""),
        }

    def get_or_create_session_id(self, session_id: str | None = None) -> str:
        normalized = (session_id or "").strip()
        with self._lock:
            if not normalized:
                normalized = str(uuid4())
            self._maybe_prune_storage_locked()
            self._load_session_from_disk_locked(normalized)
            return normalized

    def _session_exists_locked(self, session_id: str) -> bool:
        if self._get_session_path(session_id).exists():
            return True
        messages = self._sessions.get(session_id)
        return bool(messages)

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

    def get_session_metadata(self, session_id: str) -> ConversationSessionMetadata | None:
        with self._lock:
            self._maybe_prune_storage_locked()
            if not self._session_exists_locked(session_id):
                return None
            _, metadata = self._load_session_state_locked(session_id)
            return dict(metadata)

    def get_context_snapshot(
        self,
        session_id: str,
        *,
        external_context: str | None = None,
    ) -> ConversationContextSnapshot | None:
        with self._lock:
            self._maybe_prune_storage_locked()
            snapshot = self._build_context_snapshot_locked(
                session_id,
                external_context=external_context,
            )
            if snapshot is None:
                return None
            return {
                "session_id": str(snapshot.get("session_id") or session_id),
                "metadata": dict(snapshot.get("metadata") or {}),
                "compressed_summary": snapshot.get("compressed_summary"),
                "recent_messages": [
                    dict(message)
                    for message in snapshot.get("recent_messages", [])
                    if isinstance(message, dict)
                ],
                "context_text": snapshot.get("context_text"),
                "context_char_count": int(snapshot.get("context_char_count") or 0),
            }

    def list_sessions(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[ConversationSessionListItem]]:
        with self._lock:
            self._maybe_prune_storage_locked()
            items = self._list_session_items_locked()

        safe_offset = max(offset, 0)
        safe_limit = max(limit, 0)
        total = len(items)
        if safe_limit == 0:
            return total, []
        return total, [dict(item) for item in items[safe_offset : safe_offset + safe_limit]]

    def build_context(self, session_id: str, external_context: str | None = None) -> str | None:
        with self._lock:
            self._maybe_prune_storage_locked()
            messages, metadata = self._load_session_state_locked(session_id)
            return self._build_context_text(
                messages,
                metadata=metadata,
                external_context=external_context,
            )

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            removed_from_cache = self._sessions.pop(session_id, None) is not None
            self._session_metadata.pop(session_id, None)
            session_path = self._get_session_path(session_id)
            removed_from_disk = False
            if session_path.exists():
                session_path.unlink()
                removed_from_disk = True
            from .file_context_store import file_context_store

            removed_file_context = file_context_store.clear_session(session_id)
            return removed_from_cache or removed_from_disk or removed_file_context

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._session_metadata.clear()
            self._last_cleanup_monotonic = 0.0
            from .file_context_store import file_context_store

            file_context_store.clear_all()
            conversation_dir = settings.conversation_dir
            if not conversation_dir.exists():
                return
            for session_path in conversation_dir.glob("*.json"):
                session_path.unlink()

    def prune_storage(self, *, force: bool = False) -> int:
        with self._lock:
            return self._maybe_prune_storage_locked(force=force)


conversation_store = ConversationStore()
