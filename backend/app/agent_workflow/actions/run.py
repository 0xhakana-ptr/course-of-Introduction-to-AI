from __future__ import annotations

from collections.abc import Mapping

from .models import AgentActionDefinition, AgentActionDescriptor, AgentActionResult
from ..state.utils_shared import normalize_text
from .ports import get_run_port


def _model_dump(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")  # type: ignore[no-any-return]
    return dict(value) if isinstance(value, Mapping) else {}



def _status_summary(status: str) -> str:
    return {
        "queued": "任务已创建，等待后台执行。",
        "running": "任务正在后台执行。",
        "done": "任务已经完成。",
        "failed": "任务执行失败。",
        "cancelled": "任务已经取消。",
    }.get(status, "任务状态已更新。")


def _run_result(action_name: str, response: object | None, *, missing_summary: str) -> AgentActionResult:
    if response is None:
        return AgentActionResult(
            action_name=action_name,
            ok=False,
            summary=missing_summary,
            error=missing_summary,
        )

    data = _model_dump(response)
    run_id = normalize_text(data.get("run_id"))
    status = normalize_text(data.get("status"), default="unknown")
    output = normalize_text(data.get("output"))
    summary = output or _status_summary(status)
    return AgentActionResult(
        action_name=action_name,
        ok=True,
        summary=summary,
        data=data,
        metadata={
            "run_id": run_id,
            "status": status,
        },
    )


def _create_run(action_input: Mapping[str, object]) -> AgentActionResult:
    port = get_run_port()

    prompt = normalize_text(action_input.get("prompt"))
    context = action_input.get("context")
    response = port.create(prompt, str(context) if context is not None else None)
    return _run_result("run.create", response, missing_summary="Run was not created.")


def _inspect_run(action_input: Mapping[str, object]) -> AgentActionResult:
    port = get_run_port()

    run_id = normalize_text(action_input.get("run_id"))
    snapshot = port.inspect(run_id)
    if snapshot is None:
        return AgentActionResult(
            action_name="run.inspect",
            ok=False,
            summary=f"Run `{run_id}` was not found.",
            error="run not found",
            metadata={"run_id": run_id},
        )
    data = _model_dump(snapshot)
    return AgentActionResult(
        action_name="run.inspect",
        ok=True,
        summary=normalize_text(data.get("summary"), default=f"Run `{run_id}` snapshot was read."),
        data=data,
        metadata={
            "run_id": run_id,
            "status": data.get("status"),
            "terminal": bool(data.get("terminal")),
        },
    )


def _retry_run(action_input: Mapping[str, object]) -> AgentActionResult:
    port = get_run_port()

    run_id = normalize_text(action_input.get("run_id"))
    return _run_result(
        "run.retry",
        port.retry(run_id),
        missing_summary=f"Run `{run_id}` could not be retried.",
    )


def _rerun_run(action_input: Mapping[str, object]) -> AgentActionResult:
    port = get_run_port()

    run_id = normalize_text(action_input.get("run_id"))
    return _run_result(
        "run.rerun",
        port.rerun(run_id),
        missing_summary=f"Run `{run_id}` could not be rerun.",
    )


def _cancel_run(action_input: Mapping[str, object]) -> AgentActionResult:
    port = get_run_port()

    run_id = normalize_text(action_input.get("run_id"))
    return _run_result(
        "run.cancel",
        port.cancel(run_id),
        missing_summary=f"Run `{run_id}` could not be cancelled.",
    )


def list_run_action_definitions() -> list[AgentActionDefinition]:
    return [
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="run.create",
                description="Create a backend coding run.",
                category="run",
                input_keys=("prompt", "context"),
                output_keys=("run_id", "status", "summary"),
                safety_level="medium",
                user_visible_label="创建代码任务",
            ),
            executor=_create_run,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="run.inspect",
                description="Read a run snapshot by run_id.",
                category="run",
                input_keys=("run_id",),
                output_keys=("run_id", "status", "summary", "terminal"),
                safety_level="low",
                user_visible_label="读取任务状态",
            ),
            executor=_inspect_run,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="run.retry",
                description="Create a retry run from a failed run.",
                category="run",
                input_keys=("run_id",),
                output_keys=("run_id", "status", "summary"),
                safety_level="medium",
                user_visible_label="重试任务",
            ),
            executor=_retry_run,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="run.rerun",
                description="Create a rerun from a terminal run.",
                category="run",
                input_keys=("run_id",),
                output_keys=("run_id", "status", "summary"),
                safety_level="medium",
                user_visible_label="重新运行任务",
            ),
            executor=_rerun_run,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="run.cancel",
                description="Cancel a queued or running run.",
                category="run",
                input_keys=("run_id",),
                output_keys=("run_id", "status", "summary"),
                safety_level="high",
                requires_confirmation=True,
                user_visible_label="取消任务",
            ),
            executor=_cancel_run,
        ),
    ]
