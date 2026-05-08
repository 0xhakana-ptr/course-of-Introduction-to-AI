from backend.app.agent_workflow.run_summary_graph import summarize_run_record
from backend.app.services.run_interface import create_run, execute_run
from backend.app.storage.run_store import load_run_record


def test_summarize_run_record_uses_fallback_summary_without_llm():
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None

    record = load_run_record(run.run_id)
    assert record is not None

    result = summarize_run_record(record, emit_chat_message=False)

    assert result.ok is True
    assert result.summary_source == "fallback"
    assert "run_id:" in result.output
    assert "状态: done" in result.output
    assert result.as_dict()["summary_source"] == "fallback"


def test_summarize_run_record_uses_llm_summary_when_available(monkeypatch):
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None

    record = load_run_record(run.run_id)
    assert record is not None

    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.call_llm_sync",
        lambda *args, **kwargs: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": "任务已经顺利完成，结果看起来正常。",
                "error": None,
            },
        )(),
    )

    result = summarize_run_record(record, emit_chat_message=False)

    assert result.ok is True
    assert result.summary_source == "llm"
    assert result.summary_text == "任务已经顺利完成，结果看起来正常。"
    assert "摘要: 任务已经顺利完成，结果看起来正常。" in result.output


def test_run_completion_message_uses_run_summary_graph_when_llm_summary_available(
    monkeypatch,
    client,
):
    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.call_llm_sync",
        lambda *args, **kwargs: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": "这次代码任务已经处理完成，你可以查看详细结果。",
                "error": None,
            },
        )(),
    )

    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "done"

    response = client.get("/messages")
    assert response.status_code == 200
    messages = response.json()["messages"]
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_done"
    assert "摘要: 这次代码任务已经处理完成，你可以查看详细结果。" in chat_messages[0]["content"]
