from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


_UNSET: Final = object()


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class WorkflowRunStateSnapshot:
    run_id: str | None = None
    run_status: str | None = None
    run_action: str | None = None
    target_run_id: str | None = None
    run_summary: str | None = None
    run_next_action: str | None = None
    ui_status: str | None = None

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkflowRunStateSnapshot":
        return cls(
            run_id=_normalize_optional_text(state.get("run_id")),
            run_status=_normalize_optional_text(state.get("run_status")),
            run_action=_normalize_optional_text(state.get("run_action")),
            target_run_id=_normalize_optional_text(state.get("target_run_id")),
            run_summary=_normalize_optional_text(state.get("run_summary")),
            run_next_action=_normalize_optional_text(state.get("run_next_action")),
            ui_status=_normalize_optional_text(state.get("ui_status")),
        )

    def resolved_target_run_id(self) -> str:
        return self.target_run_id or self.run_id or ""

    def run_payload(self) -> tuple[str | None, str | None]:
        return self.run_id, self.run_status

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "run_status": self.run_status,
            "run_action": self.run_action,
            "target_run_id": self.target_run_id,
            "run_summary": self.run_summary,
            "run_next_action": self.run_next_action,
            "ui_status": self.ui_status,
        }


def build_run_state_updates(
    *,
    run_id: object = _UNSET,
    run_status: object = _UNSET,
    run_action: object = _UNSET,
    target_run_id: object = _UNSET,
    run_summary: object = _UNSET,
    run_next_action: object = _UNSET,
    ui_status: object = _UNSET,
) -> dict[str, object]:
    updates: dict[str, object] = {}
    raw_values = {
        "run_id": run_id,
        "run_status": run_status,
        "run_action": run_action,
        "target_run_id": target_run_id,
        "run_summary": run_summary,
        "run_next_action": run_next_action,
        "ui_status": ui_status,
    }
    for key, value in raw_values.items():
        if value is _UNSET:
            continue
        updates[key] = _normalize_optional_text(value)
    return updates
