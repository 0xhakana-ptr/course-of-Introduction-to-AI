from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ...core.limits import FORBIDDEN_KEYS_FRONTEND_ONLY, FRONTEND_TEXT_MAX


JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

MAX_FRONTEND_TEXT_CHARS = FRONTEND_TEXT_MAX

FRONTEND_FORBIDDEN_KEYS = FORBIDDEN_KEYS_FRONTEND_ONLY


def _normalize_optional_text(value: object, *, max_chars: int = MAX_FRONTEND_TEXT_CHARS) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _coerce_progress(value: object) -> int | None:
    if value is None:
        return None
    try:
        progress = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return min(100, max(0, progress))


def _to_jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_jsonable(item) for item in value]
    return str(value)


def sanitize_frontend_payload(value: object) -> JsonValue:
    if isinstance(value, Mapping):
        payload: dict[str, JsonValue] = {}
        for key, item in value.items():
            key_text = str(key).strip()
            if not key_text or key_text.lower() in FRONTEND_FORBIDDEN_KEYS:
                continue
            payload[key_text] = sanitize_frontend_payload(item)
        return payload
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_frontend_payload(item) for item in value]
    return _to_jsonable(value)


def find_frontend_state_violations(value: object, *, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).strip()
            child_path = f"{path}.{key_text}" if key_text else path
            if key_text.lower() in FRONTEND_FORBIDDEN_KEYS:
                violations.append(child_path)
                continue
            violations.extend(find_frontend_state_violations(item, path=child_path))
        return violations
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            violations.extend(find_frontend_state_violations(item, path=f"{path}[{index}]"))
    return violations


def _compact_dict(payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != {} and value != []
    }


def _auth_request_from_state(state: Mapping[str, object]) -> dict[str, JsonValue] | None:
    explicit = state.get("auth_request")
    if isinstance(explicit, Mapping):
        sanitized = sanitize_frontend_payload(explicit)
        return sanitized if isinstance(sanitized, dict) and sanitized else None

    if str(state.get("action_name") or "").strip() != "ask_user_confirmation":
        return None

    action_input = state.get("action_input")
    action_input_map = action_input if isinstance(action_input, Mapping) else {}
    prompt = _normalize_optional_text(action_input_map.get("prompt"))
    blocked_action_name = _normalize_optional_text(action_input_map.get("blocked_action_name"))
    payload = _compact_dict(
        {
            "prompt": prompt,
            "blocked_action_name": blocked_action_name,
        }
    )
    return payload or None


@dataclass(frozen=True, slots=True)
class FrontendState:
    ui_status: str | None = None
    current_phase: str | None = None
    roleplay_line: str | None = None
    expression: str | None = None
    motion: str | None = None
    progress: int | None = None
    auth_request: dict[str, JsonValue] | None = None
    terminal_status: str | None = None

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "FrontendState":
        return cls(
            ui_status=_normalize_optional_text(state.get("ui_status")),
            current_phase=_normalize_optional_text(state.get("current_phase") or state.get("phase")),
            roleplay_line=_normalize_optional_text(state.get("roleplay_line") or state.get("quip")),
            expression=_normalize_optional_text(state.get("expression")),
            motion=_normalize_optional_text(state.get("motion")),
            progress=_coerce_progress(state.get("progress")),
            auth_request=_auth_request_from_state(state),
            terminal_status=_normalize_optional_text(
                state.get("terminal_status") or state.get("stop_reason")
            ),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        payload = _compact_dict(
            {
                "ui_status": self.ui_status,
                "current_phase": self.current_phase,
                "roleplay_line": self.roleplay_line,
                "expression": self.expression,
                "motion": self.motion,
                "progress": self.progress,
                "auth_request": self.auth_request,
                "terminal_status": self.terminal_status,
            }
        )
        sanitized = sanitize_frontend_payload(payload)
        return sanitized if isinstance(sanitized, dict) else {}
