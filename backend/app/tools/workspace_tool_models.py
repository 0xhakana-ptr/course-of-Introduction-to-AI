from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    title: str
    description: str
    category: str
    output_kind: str
    input_keys: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="python")

    @classmethod
    def from_value(cls, value: object) -> "WorkspaceToolDescriptor | None":
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls.model_validate(dict(value))
        return cls.model_validate(
            {
                "name": getattr(value, "name", ""),
                "title": getattr(value, "title", ""),
                "description": getattr(value, "description", ""),
                "category": getattr(value, "category", ""),
                "output_kind": getattr(value, "output_kind", ""),
                "input_keys": list(getattr(value, "input_keys", []) or []),
            }
        )


class WorkspaceToolPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="python", exclude_none=True)


class WorkspaceToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    reason: str | None = None
    tool_category: str | None = None
    tool_output_kind: str | None = None
    tool_error_code: str | None = None
    tool_descriptor: WorkspaceToolDescriptor | None = None
    summary: str = ""
    error: str | None = None
    data: Any | None = None

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="python")
