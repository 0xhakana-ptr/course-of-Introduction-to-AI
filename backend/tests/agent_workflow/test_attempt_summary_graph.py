from backend.app.agent_workflow.graphs.summary_attempt_summary_graph import summarize_retry_outcome
from backend.app.agent_workflow.contracts.workflow_results import WorkflowSummaryResult
from backend.app.message_queue import message_queue
from backend.app.services.run_action.lifecycle import emit_retry_outcome_message


def test_attempt_summary_graph_uses_fallback_summary_without_llm():
    result = summarize_retry_outcome(
        run_id="run_demo_1",
        attempt_summary="第 2 次尝试（第 1 轮自动修复后，LLM 修复）：执行成功；返回码 0。输出摘要：repair succeeded",
        next_action="这轮自动修复后的尝试已经成功，我会整理最终结果。",
        node_name="task_retry_done",
        emit_chat_message=False,
    )

    assert result.ok is True
    assert result.summary_source == "fallback"
    assert "run_id:" not in result.output
    assert "下一步:" in result.output
    assert result.as_dict()["summary_text"] == result.summary_text


def test_attempt_summary_graph_uses_llm_summary_when_available(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graphs.summary_attempt_summary_graph.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.graphs.summary_attempt_summary_graph.call_llm_sync",
        lambda *args, **kwargs: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": "自动修复后的这轮尝试已经成功，接下来我会整理最终结果给你。",
                "error": None,
            },
        )(),
    )

    result = summarize_retry_outcome(
        run_id="run_demo_2",
        attempt_summary="第 2 次尝试（第 1 轮自动修复后，LLM 修复）：执行成功；返回码 0。",
        next_action="这轮自动修复后的尝试已经成功，我会整理最终结果。",
        node_name="task_retry_done",
        emit_chat_message=False,
    )

    assert result.ok is True
    assert result.summary_source == "llm"
    assert "摘要" not in result.summary_text
    assert "自动修复后的这轮尝试已经成功" in result.output


def test_attempt_summary_graph_returns_failed_result_when_graph_invoke_fails(monkeypatch):
    fake_graph = type(
        "BrokenGraph",
        (),
        {
            "invoke": lambda self, state: (_ for _ in ()).throw(RuntimeError("attempt graph boom")),
        },
    )()
    monkeypatch.setattr(
        "backend.app.agent_workflow.graphs.summary_attempt_summary_graph.attempt_summary_graph",
        fake_graph,
    )

    result = summarize_retry_outcome(
        run_id="run_demo_3",
        attempt_summary="attempt failed",
        next_action="我会整理结果。",
        node_name="task_retry_failed",
        emit_chat_message=False,
    )

    assert result.ok is False
    assert "总结工作流执行失败" in result.output
    assert "attempt graph boom" in result.output


def test_emit_retry_outcome_message_falls_back_when_summary_graph_returns_failed_result(monkeypatch):
    message_queue.clear()
    monkeypatch.setattr(
        "backend.app.agent_workflow.graphs.summary_attempt_summary_graph.summarize_retry_outcome",
        lambda *args, **kwargs: WorkflowSummaryResult(ok=False, output="attempt summary graph failed"),
    )

    emit_retry_outcome_message(
        run_id="run_demo_4",
        attempt_summary="第 2 次尝试失败。",
        next_action="我会结束当前任务并整理失败原因。",
        node_name="task_retry_failed",
    )
    messages = message_queue.get_messages()
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_retry_failed"
    assert "run_id:" not in chat_messages[0]["content"]
    assert "需要看细节时" in chat_messages[0]["content"]


def test_emit_retry_outcome_message_falls_back_when_summary_graph_raises(monkeypatch):
    message_queue.clear()

    def broken_summary(*args, **kwargs):
        raise RuntimeError("attempt workflow import path boom")

    monkeypatch.setattr(
        "backend.app.agent_workflow.graphs.summary_attempt_summary_graph.summarize_retry_outcome",
        broken_summary,
    )

    emit_retry_outcome_message(
        run_id="run_demo_5",
        attempt_summary="第 3 次尝试失败。",
        next_action="我会继续分析失败原因。",
        node_name="task_retry_failed",
    )
    messages = message_queue.get_messages()
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_retry_failed"
    assert "run_id:" not in chat_messages[0]["content"]
    assert "需要看细节时" in chat_messages[0]["content"]
