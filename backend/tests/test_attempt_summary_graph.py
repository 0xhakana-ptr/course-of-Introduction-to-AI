from backend.app.agent_workflow.attempt_summary_graph import summarize_retry_outcome


def test_attempt_summary_graph_uses_fallback_summary_without_llm():
    result = summarize_retry_outcome(
        run_id="run_demo_1",
        attempt_summary="第 2 次尝试（第 1 轮自动修复后，LLM 修复）：执行成功；返回码 0。输出摘要：repair succeeded",
        next_action="这轮自动修复后的尝试已经成功，我会整理最终结果。",
        node_name="task_retry_done",
        emit_chat_message=False,
    )

    assert result["ok"] is True
    assert result["summary_source"] == "fallback"
    assert "run_id: run_demo_1" in str(result["output"])
    assert "下一步:" in str(result["output"])


def test_attempt_summary_graph_uses_llm_summary_when_available(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.attempt_summary_graph.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.attempt_summary_graph.call_llm_sync",
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

    assert result["ok"] is True
    assert result["summary_source"] == "llm"
    assert "摘要" not in str(result["summary_text"])
    assert "自动修复后的这轮尝试已经成功" in str(result["output"])
