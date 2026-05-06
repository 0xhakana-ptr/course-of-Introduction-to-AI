from .types import ChatServiceResult


def build_coding_reply(prompt: str, context: str | None) -> ChatServiceResult:
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
        result = run_agent(prompt, context)
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

    output = str(result.get("output") or "").strip()
    if output:
        return ChatServiceResult(
            intent="coding",
            ok=bool(result.get("ok", True)),
            output=output,
            error=str(result.get("error")) if result.get("error") is not None else None,
        )

    return ChatServiceResult(
        intent="coding",
        ok=bool(result.get("ok", True)),
        output=(
            "我已经把这条请求识别为代码任务，并触发了后端 Agent 工作流。\n\n"
            "当前 coding 分支还在继续完善中，暂时先返回占位结果。"
        ),
        error=str(result.get("error")) if result.get("error") is not None else None,
    )
