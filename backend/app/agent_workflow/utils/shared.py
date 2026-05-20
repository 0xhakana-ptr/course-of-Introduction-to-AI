# -*- coding: utf-8 -*-
"""Unified utility helpers for agent workflow modules.

Every agent-workflow module previously copy-pasted _normalize_text,
_coerce_bool, _coerce_int, _compact_text, and _safe_mapping.  This
module is the single source of truth; import from here everywhere.
"""

from __future__ import annotations

from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_WORKER_TEXT_CHARS: int = 1200
FORBIDDEN_WORKER_PAYLOAD_KEYS: frozenset[str] = frozenset({
    "action_result",
    "artifact_content",
    "code_diff",
    "current_code",
    "current_code_or_patch",
    "debug_trace",
    "full_code",
    "llm_prompt",
    "raw_error",
    "raw_error_ref",
    "stack_trace",
    "stderr",
    "stdout",
    "tool_internal_stack_trace",
    "workflow_trace",
})

# ---------------------------------------------------------------------------
# String / bool / int coercion
# ---------------------------------------------------------------------------

def normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default

def compact_text(value: object, *, limit: int = MAX_WORKER_TEXT_CHARS) -> str:
    text = normalize_text(value)
    return text if len(text) <= limit else f"{text[:limit].rstrip()}..."

def coerce_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default

def coerce_int(value: object, *, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default

def safe_mapping(value: object, *, text_limit: int = MAX_WORKER_TEXT_CHARS) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, object] = {}
    for key, item in value.items():
        normalized_key = normalize_text(key)
        if not normalized_key or normalized_key in FORBIDDEN_WORKER_PAYLOAD_KEYS:
            continue
        if isinstance(item, str):
            result[normalized_key] = compact_text(item, limit=text_limit)
        elif isinstance(item, int | float | bool) or item is None:
            result[normalized_key] = item
        elif isinstance(item, Mapping):
            nested = safe_mapping(item, text_limit=text_limit)
            if nested:
                result[normalized_key] = nested
    return result
