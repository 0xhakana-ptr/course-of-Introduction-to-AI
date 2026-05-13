from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from ..agent_workflow.file.context import coerce_file_context, merge_file_context
from ..core.config import settings


class FileContextStore:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, object]] = {}
        self._lock = threading.RLock()

    def _context_dir(self) -> Path:
        context_dir = settings.conversation_dir / "file_context"
        context_dir.mkdir(parents=True, exist_ok=True)
        return context_dir

    def _context_path(self, session_id: str) -> Path:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return self._context_dir() / f"{digest}.json"

    def _load_locked(self, session_id: str) -> dict[str, object]:
        cached = self._cache.get(session_id)
        if cached is not None:
            return dict(cached)

        path = self._context_path(session_id)
        if not path.exists():
            self._cache[session_id] = {}
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}

        context = coerce_file_context(payload)
        self._cache[session_id] = context
        return dict(context)

    def _write_locked(self, session_id: str, context: dict[str, object]) -> None:
        normalized = coerce_file_context(context)
        self._cache[session_id] = normalized
        self._context_path(session_id).write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_context(self, session_id: str | None) -> dict[str, object]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return {}
        with self._lock:
            return self._load_locked(normalized_session_id)

    def update_context(
        self,
        session_id: str | None,
        updates: object,
    ) -> dict[str, object]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return coerce_file_context(updates)

        with self._lock:
            current = self._load_locked(normalized_session_id)
            merged = merge_file_context(current, updates)
            self._write_locked(normalized_session_id, merged)
            return merged

    def clear_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self._lock:
            removed_from_cache = self._cache.pop(normalized_session_id, None) is not None
            removed_from_disk = False
            path = self._context_path(normalized_session_id)
            if path.exists():
                path.unlink()
                removed_from_disk = True
            return removed_from_cache or removed_from_disk

    def clear_all(self) -> None:
        with self._lock:
            self._cache.clear()
            context_dir = settings.conversation_dir / "file_context"
            if not context_dir.exists():
                return
            for path in context_dir.glob("*.json"):
                if path.is_file():
                    path.unlink()


file_context_store = FileContextStore()
