from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


def _copy_action_input(value: Mapping[str, object] | None) -> dict[str, object]:
    return dict(value or {})


def _copy_action_queue(value: Sequence[Mapping[str, object]] | None) -> list[dict[str, object]]:
    if value is None:
        return []
    return [
        {
            "action_name": str(item.get("action_name") or "").strip(),
            "action_input": _copy_action_input(
                item.get("action_input") if isinstance(item.get("action_input"), Mapping) else {}
            ),
        }
        for item in value
        if str(item.get("action_name") or "").strip()
    ]



def make_action_plan(
    action_name: str,
    action_input: Mapping[str, object] | None = None,
    *,
    reason: str = "",
    details: Mapping[str, object] | None = None,
) -> ActionPlan:
    """Factory for creating ActionPlan instances."""
    return ActionPlan(
        action_name=str(action_name or "").strip(),
        action_input=_copy_action_input(action_input),
        reason=reason,
        details=dict(details or {}),
    )


@dataclass(frozen=True, slots=True)
class ActionPlan:
    action_name: str
    action_input: dict[str, object] = field(default_factory=dict)
    reason: str = ""
    safety_level: str = "unknown"
    requires_confirmation: bool = False
    next_action_queue: list[dict[str, object]] | None = None
    planner_source: str = "rules"
    terminal: bool = True
    details: dict[str, object] = field(default_factory=dict)

    def with_updates(
        self,
        *,
        action_name: str | None = None,
        action_input: Mapping[str, object] | None = None,
        reason: str | None = None,
        safety_level: str | None = None,
        requires_confirmation: bool | None = None,
        next_action_queue: Sequence[Mapping[str, object]] | None = None,
        planner_source: str | None = None,
        terminal: bool | None = None,
        details: Mapping[str, object] | None = None,
    ) -> "ActionPlan":
        merged_details = dict(self.details)
        if details:
            merged_details.update(dict(details))
        return ActionPlan(
            action_name=action_name if action_name is not None else self.action_name,
            action_input=_copy_action_input(
                action_input if action_input is not None else self.action_input
            ),
            reason=reason if reason is not None else self.reason,
            safety_level=safety_level if safety_level is not None else self.safety_level,
            requires_confirmation=(
                requires_confirmation
                if requires_confirmation is not None
                else self.requires_confirmation
            ),
            next_action_queue=(
                _copy_action_queue(next_action_queue)
                if next_action_queue is not None
                else (
                    _copy_action_queue(self.next_action_queue)
                    if self.next_action_queue is not None
                    else None
                )
            ),
            planner_source=planner_source if planner_source is not None else self.planner_source,
            terminal=terminal if terminal is not None else self.terminal,
            details=merged_details,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "action_name": self.action_name,
            "action_input": dict(self.action_input),
            "reason": self.reason,
            "safety_level": self.safety_level,
            "requires_confirmation": self.requires_confirmation,
            "next_action_queue": _copy_action_queue(self.next_action_queue),
            "planner_source": self.planner_source,
            "terminal": self.terminal,
        }

    def plan_details(self) -> dict[str, object]:
        details = dict(self.details)
        if self.reason:
            details.setdefault("reason", self.reason)
        if self.next_action_queue is not None:
            details["next_action_queue"] = _copy_action_queue(self.next_action_queue)
        details.update(
            {
                "planner_source": self.planner_source,
                "safety_level": self.safety_level,
                "requires_confirmation": self.requires_confirmation,
                "terminal": self.terminal,
                "action_plan": self.as_dict(),
            }
        )
        return details

    def as_legacy_tuple(self) -> tuple[str, dict[str, object], dict[str, object]]:
        return self.action_name, dict(self.action_input), self.plan_details()
