from __future__ import annotations

from collections.abc import Mapping

from ...tools.workspace_tools import (
    WORKSPACE_TOOL_NAME_LIST,
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_TEST,
    WORKSPACE_TOOL_NAME_WRITE,
    build_workspace_tool_user_output,
    execute_workspace_tool_plan,
    get_workspace_tool_descriptor,
)
from ...tools.workspace_tool_models import WorkspaceToolDescriptor
from .models import AgentActionDefinition, AgentActionDescriptor, AgentActionResult


WORKSPACE_ACTION_TOOL_MAP: dict[str, str] = {
    "workspace.overview": WORKSPACE_TOOL_NAME_OVERVIEW,
    "workspace.read": WORKSPACE_TOOL_NAME_READ,
    "workspace.write": WORKSPACE_TOOL_NAME_WRITE,
    "workspace.list": WORKSPACE_TOOL_NAME_LIST,
    "workspace.test": WORKSPACE_TOOL_NAME_TEST,
    "workspace.export_desktop": WORKSPACE_TOOL_NAME_WRITE,
}


def _descriptor_for_workspace_action(
    *,
    action_name: str,
    tool_name: str,
    user_visible_label: str,
    requires_confirmation: bool = False,
) -> AgentActionDescriptor:
    tool_descriptor = WorkspaceToolDescriptor.from_value(
        get_workspace_tool_descriptor(tool_name)
    )
    input_keys = tuple(tool_descriptor.input_keys) if tool_descriptor else ()
    output_keys = ("summary", "data", "error")
    safety_level = "medium" if tool_name in {WORKSPACE_TOOL_NAME_WRITE, WORKSPACE_TOOL_NAME_TEST} else "low"
    if action_name == "workspace.export_desktop" or tool_name == WORKSPACE_TOOL_NAME_TEST:
        safety_level = "high"
    return AgentActionDescriptor(
        name=action_name,
        description=tool_descriptor.description if tool_descriptor else f"Workspace action {action_name}.",
        category="workspace",
        input_keys=input_keys,
        output_keys=output_keys,
        safety_level=safety_level,
        requires_confirmation=requires_confirmation,
        user_visible_label=user_visible_label,
    )


def _execute_workspace_action(
    action_name: str,
    tool_name: str,
    action_input: Mapping[str, object],
) -> AgentActionResult:
    tool_input = dict(action_input)
    if action_name == "workspace.export_desktop":
        tool_input["target_location"] = "desktop"

    raw_result = execute_workspace_tool_plan(
        {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "reason": f"Agent action `{action_name}` requested workspace tool `{tool_name}`.",
            "terminal": True,
        }
    )
    summary = build_workspace_tool_user_output(raw_result) or str(raw_result.get("summary") or "")
    return AgentActionResult(
        action_name=action_name,
        ok=bool(raw_result.get("ok")),
        summary=summary,
        data=raw_result.get("data"),
        error=str(raw_result.get("error")) if raw_result.get("error") is not None else None,
        metadata={
            "tool_name": tool_name,
            "tool_category": raw_result.get("tool_category"),
            "tool_output_kind": raw_result.get("tool_output_kind"),
            "tool_error_code": raw_result.get("tool_error_code"),
        },
    )


def list_workspace_action_definitions() -> list[AgentActionDefinition]:
    labels = {
        "workspace.overview": "读取工作区概览",
        "workspace.read": "读取工作区文件",
        "workspace.write": "写入工作区文本",
        "workspace.list": "列出工作区目录",
        "workspace.test": "运行工作区测试",
        "workspace.export_desktop": "导出文本到桌面目录",
    }
    definitions: list[AgentActionDefinition] = []
    for action_name, tool_name in WORKSPACE_ACTION_TOOL_MAP.items():
        definitions.append(
            AgentActionDefinition(
                descriptor=_descriptor_for_workspace_action(
                    action_name=action_name,
                    tool_name=tool_name,
                    user_visible_label=labels[action_name],
                    requires_confirmation=action_name in {
                        "workspace.export_desktop",
                        "workspace.test",
                    },
                ),
                executor=lambda action_input, action_name=action_name, tool_name=tool_name: _execute_workspace_action(
                    action_name,
                    tool_name,
                    action_input,
                ),
            )
        )
    return definitions
