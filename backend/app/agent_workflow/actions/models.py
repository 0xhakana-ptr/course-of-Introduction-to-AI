from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Callable, Literal


AgentActionSafetyLevel = Literal["low", "medium", "high"]
AgentActionCategory = Literal[
    "chat",
    "workspace",
    "run",
    "character",
    "confirmation",
    "final",
]
AgentActionExecutor = Callable[[Mapping[str, object]], "AgentActionResult"]


@dataclass(frozen=True, slots=True)
class AgentActionDescriptor:
    name: str
    description: str
    category: AgentActionCategory
    input_keys: tuple[str, ...] = ()
    output_keys: tuple[str, ...] = ()
    safety_level: AgentActionSafetyLevel = "low"
    requires_confirmation: bool = False
    user_visible_label: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_keys": list(self.input_keys),
            "output_keys": list(self.output_keys),
            "safety_level": self.safety_level,
            "requires_confirmation": self.requires_confirmation,
            "user_visible_label": self.user_visible_label or self.name,
        }


@dataclass(frozen=True, slots=True)
class AgentActionResult:
    action_name: str
    ok: bool
    summary: str = ""
    data: object | None = None
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "action_name": self.action_name,
            "ok": self.ok,
            "summary": self.summary,
            "data": self.data,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AgentActionDefinition:
    descriptor: AgentActionDescriptor
    executor: AgentActionExecutor

    def execute(self, action_input: Mapping[str, object]) -> AgentActionResult:
        return self.executor(action_input)
