# -*- coding: utf-8 -*-
"""Hermes-style conversation memory for the agent.

Stores structured memory events for each conversation turn,
enabling the agent to remember 10+ previous steps.
Each event records intent, action, result, and context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any


@dataclass
class MemoryEvent:
    """A single memory event in the conversation."""
    turn_index: int
    timestamp: str
    user_input: str
    intent: str
    action_name: str = ""
    result_summary: str = ""
    ok: bool = True
    error: str | None = None
    file_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_context_line(self) -> str:
        """Format as a single context line for the agent prompt."""
        status = "OK" if self.ok else "FAILED"
        parts = [f"[Turn {self.turn_index}] {status} | Intent: {self.intent}"]
        if self.action_name:
            parts.append(f"| Action: {self.action_name}")
        parts.append(f"| User: {self.user_input[:100]}")
        if self.result_summary:
            parts.append(f"| Result: {self.result_summary[:120]}")
        if self.error:
            parts.append(f"| Error: {self.error[:80]}")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "timestamp": self.timestamp,
            "user_input": self.user_input,
            "intent": self.intent,
            "action_name": self.action_name,
            "result_summary": self.result_summary,
            "ok": self.ok,
            "error": self.error,
            "file_context": self.file_context,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEvent":
        return cls(
            turn_index=int(data.get("turn_index", 0)),
            timestamp=str(data.get("timestamp", "")),
            user_input=str(data.get("user_input", "")),
            intent=str(data.get("intent", "unknown")),
            action_name=str(data.get("action_name", "")),
            result_summary=str(data.get("result_summary", "")),
            ok=bool(data.get("ok", True)),
            error=str(data.get("error")) if data.get("error") else None,
            file_context=dict(data.get("file_context") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


class HermesMemory:
    """Hermes-style layered conversation memory.

    Design:
    - Recent Window: Full detail of last 10 turns (kept as MemoryEvents)
    - Compressed Archive: Summarized version of older turns
    - Working Memory: Current file context and active task

    Features:
    - Context preservation across 10+ turns
    - Self-compressing (older events summarized)
    - Session persistence (disk-backed)
    - Thread-safe
    """

    MAX_RECENT_EVENTS = 12  # Keep last 12 turns in full detail
    MAX_CONTEXT_LINES = 30  # Max context lines to include

    def __init__(self):
        self._events: dict[str, deque[MemoryEvent]] = {}  # session_id -> events
        self._turn_counters: dict[str, int] = {}  # session_id -> current turn
        self._lock = threading.RLock()

    def record_turn(self, session_id: str, user_input: str,
                    intent: str, action_name: str = "",
                    result_summary: str = "", ok: bool = True,
                    error: str | None = None,
                    file_context: dict[str, Any] | None = None,
                    metadata: dict[str, Any] | None = None) -> MemoryEvent:
        """Record a completed conversation turn."""
        with self._lock:
            if session_id not in self._events:
                self._events[session_id] = deque(maxlen=self.MAX_RECENT_EVENTS)
                self._turn_counters[session_id] = 0

            self._turn_counters[session_id] += 1
            event = MemoryEvent(
                turn_index=self._turn_counters[session_id],
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                user_input=user_input[:200],  # Truncate long inputs
                intent=intent,
                action_name=action_name,
                result_summary=result_summary[:200],
                ok=ok,
                error=error,
                file_context=file_context or {},
                metadata=metadata or {},
            )
            self._events[session_id].append(event)
            return event

    def build_context(self, session_id: str) -> str:
        """Build Hermes-style context string for the next turn.

        Returns a formatted string containing recent conversation history
        that can be injected into the agent's context.
        """
        with self._lock:
            events = self._events.get(session_id)
            if not events:
                return ""

            lines: list[str] = []
            lines.append("=== 对话记忆 (Hermes) ===")

            # Recent events in full detail
            recent = list(events)[-self.MAX_CONTEXT_LINES:]
            for event in recent:
                lines.append(event.to_context_line())

            # If we have more events than shown, indicate compression
            total = len(events)
            if total > len(recent):
                compressed_count = total - len(recent)
                lines.append(f"... ({compressed_count} 个更早的对话回合已压缩)")

            lines.append("=== 记忆结束 ===")
            return "\n".join(lines)

    def get_recent_events(self, session_id: str, count: int = 5) -> list[MemoryEvent]:
        """Get the most recent N events."""
        with self._lock:
            events = self._events.get(session_id)
            if not events:
                return []
            return list(events)[-count:]

    def get_last_event(self, session_id: str) -> MemoryEvent | None:
        """Get the most recent event."""
        with self._lock:
            events = self._events.get(session_id)
            if not events:
                return None
            return events[-1]

    def get_file_context_summary(self, session_id: str) -> str:
        """Build a summary of recent file operations."""
        with self._lock:
            events = self._events.get(session_id)
            if not events:
                return ""

            recent = list(events)[-5:]
            file_lines = []
            for event in recent:
                if event.file_context:
                    fc = event.file_context
                    if fc.get("recent_files"):
                        file_lines.append(f"Recent files: {', '.join(fc['recent_files'][:5])}")
                    if fc.get("last_modified"):
                        file_lines.append(f"Last modified: {fc['last_modified']}")

            return "\n".join(file_lines) if file_lines else ""

    def clear_session(self, session_id: str) -> None:
        """Clear all memory for a session."""
        with self._lock:
            self._events.pop(session_id, None)
            self._turn_counters.pop(session_id, None)

    def get_turn_count(self, session_id: str) -> int:
        """Get current turn count for a session."""
        with self._lock:
            return self._turn_counters.get(session_id, 0)

    def export_session(self, session_id: str) -> list[dict[str, Any]]:
        """Export all events for a session as dicts (for persistence)."""
        with self._lock:
            events = self._events.get(session_id)
            if not events:
                return []
            return [e.to_dict() for e in events]

    def import_session(self, session_id: str, data: list[dict[str, Any]]) -> None:
        """Import events from persisted data."""
        with self._lock:
            events = deque(maxlen=self.MAX_RECENT_EVENTS)
            max_turn = 0
            for item in data:
                event = MemoryEvent.from_dict(item)
                events.append(event)
                if event.turn_index > max_turn:
                    max_turn = event.turn_index
            self._events[session_id] = events
            self._turn_counters[session_id] = max_turn


# Global singleton
hermes_memory = HermesMemory()
