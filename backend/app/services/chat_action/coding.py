from collections.abc import Callable

from .types import ChatServiceResult


RunScheduler = Callable[[str], None]


def build_coding_reply(
    prompt: str,
    context: str | None,
    *,
    session_id: str | None = None,
    schedule_run: RunScheduler | None = None,
) -> ChatServiceResult:
    try:
        from ...agent_workflow.agent_graph import run_agent
    except ImportError as exc:
        return ChatServiceResult(
            intent="coding",
            ok=False,
            output=(
                "代码任务分支当前不可用，原因是 Agent 工作流依赖尚未正确加载。\n\n"
                f"prompt: {prompt}\n"
                f"context: {context or '(none)'}"
            ),
            error=str(exc),
        )

    try:
        result = run_agent(prompt, context, session_id=session_id, intent="coding")
    except Exception as exc:
        return ChatServiceResult(
            intent="coding",
            ok=False,
            output=(
                "代码任务执行失败。\n\n"
                f"prompt: {prompt}\n"
                f"context: {context or '(none)'}"
            ),
            error=str(exc),
        )

    run_id = str(result.get("run_id") or "").strip() or None
    if run_id and bool(result.get("ok", True)) and schedule_run is not None:
        try:
            schedule_run(run_id)
        except Exception as exc:
            return ChatServiceResult(
                intent="coding",
                ok=False,
                output=f"代码任务已创建，但后台执行调度失败。\n\nrun_id: {run_id}",
                error=str(exc),
                run_id=run_id,
            )

    output = str(result.get("output") or "").strip()
    if output:
        if run_id and schedule_run is not None:
            output = output.replace(
                "已通过 LangGraph 创建代码任务，并交给 `/runs` 链路处理。",
                "已通过 LangGraph 创建代码任务，并开始后台执行。",
            )
        return ChatServiceResult(
            intent="coding",
            ok=bool(result.get("ok", True)),
            output=output,
            error=str(result.get("error")) if result.get("error") is not None else None,
            run_id=run_id,
        )

    return ChatServiceResult(
        intent="coding",
        ok=bool(result.get("ok", True)),
        output=(
            "我已经把这条请求识别为代码任务，并触发了后端 Agent 工作流。\n\n"
            "当前 coding 分支还在继续完善中，暂时先返回占位结果。"
        ),
        error=str(result.get("error")) if result.get("error") is not None else None,
        run_id=run_id,
    )
