import re
from collections.abc import Mapping

from ...core.config import settings
from ...tools.workspace_tools import (
    WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
    WORKSPACE_TOOL_ERROR_TARGET_DISABLED,
    WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED,
)
from ..actions import default_action_registry
from .loop_action_plan import ActionPlan


RUN_ACTIONS_REQUIRING_ID = {
    "run.inspect",
    "run.retry",
    "run.rerun",
    "run.cancel",
}

RECOVERY_REASON_DESKTOP_EXPORT_DISABLED = "desktop_export_disabled"
RECOVERY_REASON_FILE_EXISTS = "file_exists"
RECOVERY_REASON_MISSING_RUN_ID = "missing_run_id"
RECOVERY_REASON_UNSUPPORTED_WRITE_TARGET = "unsupported_write_target"

CONFIRMATION_KEYWORDS = (
    "确认",
    "同意",
    "允许",
    "继续执行",
)
ENGLISH_CONFIRMATION_PATTERN = re.compile(
    r"\b(?:confirm|confirmed|allow|proceed|yes)\b",
    re.IGNORECASE,
)
OVERWRITE_CONFIRMATION_KEYWORDS = (
    "覆盖",
    "替换",
    "overwrite",
    "replace",
)
NEGATED_OVERWRITE_KEYWORDS = (
    "不要覆盖",
    "不覆盖",
    "别覆盖",
    "不要替换",
    "不替换",
    "别替换",
    "do not overwrite",
    "don't overwrite",
    "dont overwrite",
    "without overwriting",
)


def normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def coerce_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def prompt_confirms_action(prompt: str) -> bool:
    text = str(prompt or "").strip()
    return (
        any(keyword in text for keyword in CONFIRMATION_KEYWORDS)
        or ENGLISH_CONFIRMATION_PATTERN.search(text) is not None
    )


def prompt_confirms_overwrite(prompt: str) -> bool:
    text = str(prompt or "").strip().lower()
    if any(keyword.lower() in text for keyword in NEGATED_OVERWRITE_KEYWORDS):
        return False
    return any(keyword.lower() in text for keyword in OVERWRITE_CONFIRMATION_KEYWORDS)


def apply_overwrite_confirmation_to_action(
    *,
    prompt: str,
    action_name: str,
    action_input: dict[str, object],
    workspace_plan: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object] | None]:
    if action_name not in {
        "workspace.write",
        "workspace.export_desktop",
        "workspace.move",
        "workspace.copy",
    }:
        return action_input, workspace_plan
    if not prompt_confirms_overwrite(prompt):
        return action_input, workspace_plan
    if not normalize_text(action_input.get("rel_path")):
        return action_input, workspace_plan

    confirmed_input = {**action_input, "overwrite": True}
    if workspace_plan is None:
        return confirmed_input, None

    tool_input = workspace_plan.get("tool_input")
    confirmed_plan = {
        **workspace_plan,
        "tool_input": {
            **(dict(tool_input) if isinstance(tool_input, dict) else {}),
            "overwrite": True,
        },
    }
    return confirmed_input, confirmed_plan


def desktop_export_confirmation_is_needed(action_input: dict[str, object]) -> bool:
    target_location = normalize_text(action_input.get("target_location")).lower()
    if target_location != "desktop":
        return False
    return settings.desktop_export_enabled and settings.desktop_export_dir is not None


def action_requires_runtime_confirmation(
    action_name: str,
    action_input: dict[str, object],
) -> bool:
    if action_name in RUN_ACTIONS_REQUIRING_ID and not normalize_text(action_input.get("run_id")):
        return False
    definition = default_action_registry.get(action_name)
    if definition is None:
        return False
    if action_name == "workspace.export_desktop":
        return desktop_export_confirmation_is_needed(action_input)
    return bool(definition.descriptor.requires_confirmation)


def action_safety_level(action_name: str) -> str:
    definition = default_action_registry.get(action_name)
    if definition is None:
        return "unknown"
    return definition.descriptor.safety_level


def make_action_plan(
    action_name: str,
    action_input: dict[str, object],
    *,
    reason: str,
    planner_source: str = "rules",
    terminal: bool = True,
    next_action_queue: list[dict[str, object]] | None = None,
    details: dict[str, object] | None = None,
) -> ActionPlan:
    return ActionPlan(
        action_name=action_name,
        action_input=dict(action_input),
        reason=reason,
        safety_level=action_safety_level(action_name),
        requires_confirmation=action_requires_runtime_confirmation(action_name, action_input),
        next_action_queue=next_action_queue,
        planner_source=planner_source,
        terminal=terminal,
        details=dict(details or {}),
    )


def confirmation_target_label(
    action_name: str,
    action_input: dict[str, object],
) -> str:
    if action_name.startswith("run."):
        return normalize_text(action_input.get("run_id"), default="目标任务")
    if action_name.startswith("workspace."):
        return normalize_text(action_input.get("rel_path"), default="目标路径")
    return "当前动作"


def build_action_confirmation_prompt(
    action_name: str,
    action_input: dict[str, object],
) -> str:
    definition = default_action_registry.get(action_name)
    descriptor = definition.descriptor if definition is not None else None
    action_label = descriptor.user_visible_label if descriptor is not None else action_name
    safety_level = descriptor.safety_level if descriptor is not None else "unknown"
    target_label = confirmation_target_label(action_name, action_input)
    return (
        "这一步会执行有风险的动作，需要你明确确认后我再继续。\n\n"
        f"动作: {action_label}\n"
        f"动作名: `{action_name}`\n"
        f"风险等级: `{safety_level}`\n"
        f"目标: `{target_label}`\n\n"
        "如果确认执行，请重新发送同一条请求，并明确写上“确认执行”或 `confirm`。"
    )


def with_confirmation_guard(
    *,
    prompt: str,
    plan: ActionPlan,
) -> ActionPlan:
    if (
        plan.action_name == "ask_user_confirmation"
        or not action_requires_runtime_confirmation(plan.action_name, plan.action_input)
        or prompt_confirms_action(prompt)
    ):
        return plan

    confirmation_prompt = build_action_confirmation_prompt(plan.action_name, plan.action_input)
    return make_action_plan(
        "ask_user_confirmation",
        {
            "prompt": confirmation_prompt,
            "blocked_action_name": plan.action_name,
            "blocked_action_input": plan.action_input,
        },
        reason="Runtime confirmation is required before executing a risky action.",
        planner_source=plan.planner_source,
        details={
            **plan.details,
            "confirmation_required": True,
            "blocked_action_name": plan.action_name,
            "blocked_action_plan": plan.as_dict(),
        },
    )


def is_file_exists_error(action_result: dict[str, object]) -> bool:
    error = normalize_text(action_result.get("error")).lower()
    summary = normalize_text(action_result.get("summary")).lower()
    return "file already exists" in error or "file already exists" in summary


def build_recovery_message(
    *,
    reason: str,
    state: Mapping[str, object],
    action_result: dict[str, object],
) -> str:
    raw_action_input = state.get("action_input")
    action_input = dict(raw_action_input) if isinstance(raw_action_input, Mapping) else {}
    action_name = normalize_text(state.get("action_name"))
    if reason == RECOVERY_REASON_DESKTOP_EXPORT_DISABLED:
        return (
            "我还不能直接导出到桌面，因为桌面导出没有启用或没有配置 "
            "`DESKTOP_EXPORT_DIR`。\n\n"
            "如果要继续，请先配置 `DESKTOP_EXPORT_ENABLED=true` 和 "
            "`DESKTOP_EXPORT_DIR`，或者让我改为创建到项目 workspace 里。"
        )
    if reason == RECOVERY_REASON_FILE_EXISTS:
        rel_path = normalize_text(action_input.get("rel_path"), default="目标文件")
        target_location = normalize_text(action_input.get("target_location"), default="workspace")
        target_label = "桌面导出目录" if target_location == "desktop" else "workspace"
        return (
            f"`{rel_path}` 在 {target_label} 中已经存在，我不会直接覆盖。\n\n"
            "如果你确认要覆盖，请明确告诉我“覆盖这个文件”；"
            "如果不想覆盖，请给我一个新的文件名。"
        )
    if reason == RECOVERY_REASON_MISSING_RUN_ID:
        action_label = action_name.split(".", 1)[1] if "." in action_name else action_name
        return (
            f"我需要一个明确的 `run_id` 才能继续执行 `{action_label}`。\n\n"
            "请把要处理的 `run_id` 发给我，我再继续查看、重试、重跑或取消。"
        )
    if reason == RECOVERY_REASON_UNSUPPORTED_WRITE_TARGET:
        return (
            "当前只支持写入项目 workspace，或显式配置过的桌面导出目录。\n\n"
            "请改为 workspace 路径，或先配置桌面导出目录。"
        )

    summary = normalize_text(action_result.get("summary"), default="工具执行失败。")
    return f"这一步没有完成：{summary}"


def recovery_reason_for_action_result(
    state: Mapping[str, object],
    action_result: dict[str, object],
) -> str | None:
    if bool(action_result.get("ok")):
        return None

    action_name = normalize_text(state.get("action_name"))
    raw_action_input = state.get("action_input")
    action_input = dict(raw_action_input) if isinstance(raw_action_input, Mapping) else {}
    metadata = action_result.get("metadata")
    metadata_dict = dict(metadata) if isinstance(metadata, Mapping) else {}
    tool_error_code = normalize_text(metadata_dict.get("tool_error_code"))

    if action_name == "workspace.export_desktop" and tool_error_code == WORKSPACE_TOOL_ERROR_TARGET_DISABLED:
        return RECOVERY_REASON_DESKTOP_EXPORT_DISABLED
    if action_name.startswith("workspace.") and tool_error_code == WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED:
        return RECOVERY_REASON_UNSUPPORTED_WRITE_TARGET
    if (
        action_name.startswith("workspace.")
        and tool_error_code == WORKSPACE_TOOL_ERROR_EXECUTION_FAILED
        and is_file_exists_error(action_result)
    ):
        return RECOVERY_REASON_FILE_EXISTS
    if action_name in RUN_ACTIONS_REQUIRING_ID and not normalize_text(action_input.get("run_id")):
        return RECOVERY_REASON_MISSING_RUN_ID
    return None


def should_replan_after_failure(
    state: Mapping[str, object],
    action_result: dict[str, object],
) -> tuple[bool, str | None, str | None]:
    if coerce_bool(state.get("recovery_attempted")):
        return False, None, None

    reason = recovery_reason_for_action_result(state, action_result)
    if reason is None:
        return False, None, None

    message = build_recovery_message(
        reason=reason,
        state=state,
        action_result=action_result,
    )
    return True, reason, message


def build_recovery_action_plan(state: Mapping[str, object]) -> ActionPlan:
    reason = normalize_text(state.get("recovery_reason"))
    message = normalize_text(
        state.get("recovery_message"),
        default="这一步需要你补充确认后才能继续。",
    )

    if reason == RECOVERY_REASON_FILE_EXISTS:
        return make_action_plan(
            "ask_user_confirmation",
            {"prompt": message},
            reason="Recoverable tool failure asks the user before overwrite.",
            planner_source="recovery",
            next_action_queue=[],
            details={"recovery_reason": reason},
        )

    return make_action_plan(
        "final.answer",
        {"content": message},
        reason="Recoverable tool failure is converted to a clear final answer.",
        planner_source="recovery",
        next_action_queue=[],
        details={"recovery_reason": reason},
    )
