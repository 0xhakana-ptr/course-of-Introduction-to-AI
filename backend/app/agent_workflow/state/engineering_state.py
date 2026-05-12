from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .display_state import JsonValue, _to_jsonable


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if not isinstance(value, Sequence):
        text = str(value).strip()
        return (text,) if text else ()
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return tuple(items)


def _coerce_non_negative_int(value: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _compact_dict(payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != [] and value != {}
    }


@dataclass(frozen=True, slots=True)
class EngineeringState:
    tasks_list: tuple[str, ...] = ()
    current_task: str | None = None
    target_files: tuple[str, ...] = ()
    current_code_or_patch_ref: str | None = None
    raw_error_ref: str | None = None
    error_summary: str | None = None
    repair_count: int = 0
    artifact_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "EngineeringState":
        return cls(
            tasks_list=_coerce_text_tuple(state.get("tasks_list")),
            current_task=_normalize_optional_text(state.get("current_task")),
            target_files=_coerce_text_tuple(state.get("target_files")),
            current_code_or_patch_ref=_normalize_optional_text(
                state.get("current_code_or_patch_ref") or state.get("code_patch_ref")
            ),
            raw_error_ref=_normalize_optional_text(
                state.get("raw_error_ref") or state.get("raw_error_artifact_ref")
            ),
            error_summary=_normalize_optional_text(state.get("error_summary")),
            repair_count=_coerce_non_negative_int(state.get("repair_count")),
            artifact_refs=_coerce_text_tuple(state.get("artifact_refs")),
        )

    def with_raw_error_ref(self, raw_error_ref: str) -> "EngineeringState":
        return replace(self, raw_error_ref=_normalize_optional_text(raw_error_ref))

    def with_error_summary(self, error_summary: str, *, clear_raw_error_ref: bool = True) -> "EngineeringState":
        return replace(
            self,
            error_summary=_normalize_optional_text(error_summary),
            raw_error_ref=None if clear_raw_error_ref else self.raw_error_ref,
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return _compact_dict(
            {
                "tasks_list": list(self.tasks_list),
                "current_task": self.current_task,
                "target_files": list(self.target_files),
                "current_code_or_patch_ref": self.current_code_or_patch_ref,
                "raw_error_ref": self.raw_error_ref,
                "error_summary": self.error_summary,
                "repair_count": self.repair_count,
                "artifact_refs": list(self.artifact_refs),
            }
        )


def engineering_payload_to_jsonable(value: object) -> JsonValue:
    return _to_jsonable(value)
