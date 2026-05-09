from collections.abc import Mapping
from dataclasses import dataclass

from ..schemas import (
    WorkspaceToolDescriptorInfo,
    WorkspaceToolInfo,
    WorkspaceToolPlanInfo,
)
from ..tools.workspace_tool_models import WorkspaceToolDescriptor
from ..tools.workspace_tools import (
    get_workspace_tool_descriptor,
    normalize_workspace_tool_plan,
)


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class WorkspaceToolSnapshot:
    name: str | None = None
    title: str | None = None
    reason: str | None = None
    category: str | None = None
    output_kind: str | None = None
    error_code: str | None = None
    descriptor: dict[str, object] | None = None
    plan: dict[str, object] | None = None

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkspaceToolSnapshot":
        tool_name = _normalize_optional_text(state.get("workspace_tool_name"))
        descriptor_model = WorkspaceToolDescriptor.from_value(
            state.get("workspace_tool_descriptor")
        )
        if descriptor_model is None and tool_name is not None:
            descriptor_model = WorkspaceToolDescriptor.from_value(
                get_workspace_tool_descriptor(tool_name)
            )

        plan_model = normalize_workspace_tool_plan(state.get("workspace_tool_plan"))
        return cls(
            name=tool_name,
            title=descriptor_model.title if descriptor_model is not None else None,
            reason=_normalize_optional_text(state.get("workspace_tool_reason")),
            category=(
                _normalize_optional_text(state.get("workspace_tool_category"))
                or (descriptor_model.category if descriptor_model is not None else None)
            ),
            output_kind=(
                _normalize_optional_text(state.get("workspace_tool_output_kind"))
                or (descriptor_model.output_kind if descriptor_model is not None else None)
            ),
            error_code=_normalize_optional_text(state.get("workspace_tool_error_code")),
            descriptor=descriptor_model.as_dict() if descriptor_model is not None else None,
            plan=plan_model.as_dict() if plan_model is not None else None,
        )

    def merged_with(self, fallback: "WorkspaceToolSnapshot | None") -> "WorkspaceToolSnapshot":
        if fallback is None:
            return self
        return WorkspaceToolSnapshot(
            name=self.name or fallback.name,
            title=self.title or fallback.title,
            reason=self.reason or fallback.reason,
            category=self.category or fallback.category,
            output_kind=self.output_kind or fallback.output_kind,
            error_code=self.error_code or fallback.error_code,
            descriptor=self.descriptor or fallback.descriptor,
            plan=self.plan or fallback.plan,
        )


def build_workspace_tool_descriptor_info(
    snapshot: WorkspaceToolSnapshot,
) -> WorkspaceToolDescriptorInfo | None:
    if snapshot.descriptor is None:
        return None
    return WorkspaceToolDescriptorInfo.model_validate(snapshot.descriptor)


def build_workspace_tool_plan_info(
    snapshot: WorkspaceToolSnapshot,
) -> WorkspaceToolPlanInfo | None:
    if snapshot.plan is None:
        return None
    return WorkspaceToolPlanInfo.model_validate(snapshot.plan)


def build_workspace_tool_info(
    snapshot: WorkspaceToolSnapshot,
) -> WorkspaceToolInfo | None:
    if (
        snapshot.name is None
        and snapshot.reason is None
        and snapshot.category is None
        and snapshot.output_kind is None
        and snapshot.error_code is None
        and snapshot.descriptor is None
        and snapshot.plan is None
    ):
        return None
    return WorkspaceToolInfo(
        name=snapshot.name,
        title=snapshot.title,
        reason=snapshot.reason,
        category=snapshot.category,
        output_kind=snapshot.output_kind,
        error_code=snapshot.error_code,
        descriptor=build_workspace_tool_descriptor_info(snapshot),
        plan=build_workspace_tool_plan_info(snapshot),
    )


def build_workspace_tool_response_kwargs(
    snapshot: WorkspaceToolSnapshot,
) -> dict[str, object]:
    descriptor_info = build_workspace_tool_descriptor_info(snapshot)
    plan_info = build_workspace_tool_plan_info(snapshot)
    return {
        "workspace_tool_name": snapshot.name,
        "workspace_tool_reason": snapshot.reason,
        "workspace_tool_category": snapshot.category,
        "workspace_tool_output_kind": snapshot.output_kind,
        "workspace_tool_error_code": snapshot.error_code,
        "workspace_tool_descriptor": descriptor_info,
        "workspace_tool_plan": plan_info,
        "workspace_tool": build_workspace_tool_info(snapshot),
    }
