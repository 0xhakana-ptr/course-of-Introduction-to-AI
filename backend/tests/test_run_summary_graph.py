from backend.app.agent_workflow.run_summary_graph import summarize_run_record
from backend.app.agent_workflow.summary_support import (
    build_summary_resolution_node,
    build_summary_roleplay_node,
)
from backend.app.agent_workflow.workflow_results import WorkflowSummaryResult
from backend.app.message_queue import message_queue
from backend.app.services.run_interface import create_run, execute_run
from backend.app.services.run_action.lifecycle import emit_final_run_chat_message
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


def test_summarize_run_record_returns_failed_result_when_graph_invoke_fails(monkeypatch):
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None

    record = load_run_record(run.run_id)
    assert record is not None

    fake_graph = type(
        "BrokenGraph",
        (),
        {
            "invoke": lambda self, state: (_ for _ in ()).throw(RuntimeError("summary graph boom")),
        },
    )()
    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.run_summary_graph",
        fake_graph,
    )

    result = summarize_run_record(record, emit_chat_message=False)

    assert result.ok is False
    assert "总结工作流执行失败" in result.output
    assert "summary graph boom" in result.output


def test_emit_final_run_chat_message_falls_back_when_summary_graph_returns_failed_result(monkeypatch):
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None

    record = load_run_record(run.run_id)
    assert record is not None
    message_queue.clear()

    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.summarize_run_record",
        lambda *args, **kwargs: WorkflowSummaryResult(ok=False, output="summary graph failed"),
    )

    emit_final_run_chat_message(record, node_name="task_done")
    messages = message_queue.get_messages()
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_done"
    assert f"run_id: {run.run_id}" in chat_messages[0]["content"]


def test_emit_final_run_chat_message_falls_back_when_summary_graph_raises(monkeypatch):
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None

    record = load_run_record(run.run_id)
    assert record is not None
    message_queue.clear()

    def broken_summary(*args, **kwargs):
        raise RuntimeError("summary workflow import path boom")

    monkeypatch.setattr(
        "backend.app.agent_workflow.run_summary_graph.summarize_run_record",
        broken_summary,
    )

    emit_final_run_chat_message(record, node_name="task_done")
    messages = message_queue.get_messages()
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_done"
    assert f"run_id: {run.run_id}" in chat_messages[0]["content"]


def test_summary_support_builds_resolution_node_from_custom_builders():
    summary_node = build_summary_resolution_node(
        fallback_text_builder=lambda state: str(state.get("fallback_text") or ""),
        prompt_builder=lambda state: f"prompt::{state.get('prompt_seed') or ''}",
        output_builder=lambda state, resolution: f"output::{resolution.text}",
        system_prompt="system",
        llm_is_configured_fn=lambda: False,
    )

    result_state = summary_node(
        {
            "fallback_text": "fallback summary",
            "prompt_seed": "demo",
        }
    )

    assert result_state["summary_text"] == "fallback summary"
    assert result_state["summary_source"] == "fallback"
    assert result_state["output"] == "output::fallback summary"


def test_summary_support_builds_roleplay_node_with_default_name():
    roleplay_node = build_summary_roleplay_node(default_node_name="summary_demo")
    message_queue.clear()

    roleplay_node(
        {
            "output": "summary roleplay content",
            "emit_chat_message": True,
        }
    )
    messages = message_queue.get_messages()

    assert len(messages) == 1
    assert messages[0]["type"] == "chat"
    assert messages[0]["node_name"] == "summary_demo"
    assert messages[0]["content"] == "summary roleplay content"
