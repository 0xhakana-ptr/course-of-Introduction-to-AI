import importlib

import anyio

from backend.app.agent_workflow.loop.agent_loop_graph import run_agent_loop
from backend.app.services.chat_action.agent import build_agent_reply
from backend.app.services.run_interface import create_run, execute_run, get_run
from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import read_workspace_text


def test_agent_loop_graph_handles_chat_action(monkeypatch):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": f"loop reply to {prompt}",
                "error": None,
            },
        )(),
    )

    result = run_agent_loop(
        "hello",
        "ctx",
        intent="chat",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.intent == "chat"
    assert result.output == "loop reply to hello"
    assert result.state["runtime_mode"] == "loop"
    assert result.runtime_turn["stop_reason"] == "completed"
    assert [item["node"] for item in result.workflow_trace] == [
        "perceive_node",
        "plan_node",
        "act_node",
        "observe_node",
        "decide_continue_node",
        "finalize_node",
        "roleplay_node",
    ]
    assert result.runtime_steps[2]["action"]["name"] == "chat.reply"
    assert result.state["action_name"] == "chat.reply"


def test_agent_loop_graph_executes_workspace_write_action():
    result = run_agent_loop(
        "请创建 notes/loop.txt，内容是loop ok",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id is None
    assert result.state["action_name"] == "workspace.write"
    assert result.state["workspace_tool_name"] == "write_workspace_text"
    assert "已在 workspace 中创建文本文件" in result.output
    assert read_workspace_text("notes/loop.txt")["content"] == "loop ok"


def test_agent_loop_graph_executes_workspace_read_action():
    safe_write_file("backend/app/demo.txt", "demo content")

    result = run_agent_loop(
        "请读取 backend/app/demo.txt",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.state["action_name"] == "workspace.read"
    assert result.state["workspace_tool_name"] == "read_workspace_text"
    assert "我读到了 `backend/app/demo.txt` 的内容" in result.output
    assert "demo content" in result.output


def test_agent_loop_graph_executes_workspace_list_action():
    safe_write_file("demo/nested/info.txt", "nested data")

    result = run_agent_loop(
        "请列出 demo/nested 目录结构",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.state["action_name"] == "workspace.list"
    assert result.state["workspace_tool_name"] == "list_workspace_entries"
    assert "我列出了 `demo/nested` 下的内容" in result.output
    assert "文件: demo/nested/info.txt" in result.output


def test_agent_loop_graph_executes_workspace_test_action():
    safe_write_file(
        "backend/tests/test_demo_pass.py",
        "def test_demo_pass():\n"
        "    assert True\n",
    )

    result = run_agent_loop(
        "请运行 backend/tests/test_demo_pass.py 的测试",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.state["action_name"] == "workspace.test"
    assert result.state["workspace_tool_name"] == "run_workspace_tests"
    assert "我运行完测试了" in result.output
    assert "结果: 通过" in result.output


def test_agent_loop_graph_keeps_complex_file_request_on_run_create_path():
    safe_write_file("backend/app/demo.py", "print('broken')")

    result = run_agent_loop(
        "请修复 backend/app/demo.py 里的问题",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id
    assert result.run_status == "queued"
    assert result.run_action == "create"
    assert result.state["action_name"] == "run.create"


def test_agent_loop_graph_executes_run_inspect_action():
    run = create_run("build a demo", None)

    result = run_agent_loop(
        f"请查看 run_id {run.run_id} 的状态",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id == run.run_id
    assert result.run_status == "queued"
    assert result.run_action == "inspect"
    assert result.state["action_name"] == "run.inspect"
    assert "任务已创建，等待后台执行" in result.output


def test_agent_loop_graph_executes_run_retry_action():
    failed_run = create_run("please run a broken fail demo", None)
    failed_result = execute_run(failed_run.run_id)
    assert failed_result is not None
    assert failed_result.status == "failed"

    result = run_agent_loop(
        f"请 retry run_id {failed_run.run_id}",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id
    assert result.run_id != failed_run.run_id
    assert result.run_status == "queued"
    assert result.run_action == "retry"
    assert result.state["action_name"] == "run.retry"
    assert "原任务已经记录在任务详情里。" in result.output
    assert "目前我看到：" in result.output
    follow_up = get_run(result.run_id)
    assert follow_up is not None
    assert follow_up.source_run_id == failed_run.run_id
    assert follow_up.trigger_mode == "retry"


def test_agent_loop_graph_executes_run_rerun_action():
    successful_run = create_run("build a calculator demo", None)
    successful_result = execute_run(successful_run.run_id)
    assert successful_result is not None
    assert successful_result.status == "done"

    result = run_agent_loop(
        f"请重新运行 run_id {successful_run.run_id}",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id
    assert result.run_id != successful_run.run_id
    assert result.run_status == "queued"
    assert result.run_action == "rerun"
    assert result.state["action_name"] == "run.rerun"
    assert "重新运行任务" in result.output
    follow_up = get_run(result.run_id)
    assert follow_up is not None
    assert follow_up.source_run_id == successful_run.run_id
    assert follow_up.trigger_mode == "rerun"


def test_agent_loop_graph_executes_run_cancel_action():
    run = create_run("build a calculator demo", None)

    result = run_agent_loop(
        f"请取消 run_id {run.run_id}",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id == run.run_id
    assert result.run_status == "cancelled"
    assert result.run_action == "cancel"
    assert result.state["action_name"] == "run.cancel"
    assert "取消请求" in result.output
    cancelled = get_run(run.run_id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled.cancel_requested is True


def test_agent_loop_graph_reports_chat_llm_failure(monkeypatch):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": False,
                "output": "调用大模型接口失败。",
                "error": "llm failed",
            },
        )(),
    )

    result = run_agent_loop(
        "hello",
        None,
        intent="chat",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is False
    assert result.error == "llm failed"
    assert result.ui_status == "chat_failed"
    assert result.runtime_turn["stop_reason"] == "failed"
    assert result.workflow_trace[-1]["node"] == "failure_node"
    assert [item["node"] for item in result.workflow_trace].count("plan_node") == 1


def test_agent_loop_graph_recovers_desktop_export_disabled():
    result = run_agent_loop(
        "帮我在桌面创建 notes/desk.txt，内容是hello desk",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    action_names = [step["action"]["name"] for step in result.runtime_steps]

    assert result.ok is True
    assert result.error is None
    assert result.runtime_turn["stop_reason"] == "completed"
    assert result.state["recovery_reason"] == "desktop_export_disabled"
    assert [item["node"] for item in result.workflow_trace].count("plan_node") == 2
    assert "workspace.export_desktop" in action_names
    assert "final.answer" in action_names
    assert "DESKTOP_EXPORT_ENABLED=true" in result.output


def test_agent_loop_graph_asks_before_overwriting_existing_file():
    safe_write_file("notes/existing.txt", "old")

    result = run_agent_loop(
        "请创建 notes/existing.txt，内容是new",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    action_names = [step["action"]["name"] for step in result.runtime_steps]

    assert result.ok is True
    assert result.error is None
    assert result.runtime_turn["stop_reason"] == "completed"
    assert result.state["recovery_reason"] == "file_exists"
    assert result.state["action_name"] == "ask_user_confirmation"
    assert [item["node"] for item in result.workflow_trace].count("plan_node") == 2
    assert "workspace.write" in action_names
    assert "ask_user_confirmation" in action_names
    assert "不会直接覆盖" in result.output
    assert read_workspace_text("notes/existing.txt")["content"] == "old"


def test_agent_loop_graph_asks_for_run_id_when_run_action_lacks_reference(monkeypatch):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(loop_module, "detect_run_action", lambda prompt: "inspect")
    monkeypatch.setattr(loop_module, "extract_run_reference", lambda prompt: None)

    result = run_agent_loop(
        "请查看这个任务的状态",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    action_names = [step["action"]["name"] for step in result.runtime_steps]

    assert result.ok is True
    assert result.error is None
    assert result.runtime_turn["stop_reason"] == "completed"
    assert result.state["recovery_reason"] == "missing_run_id"
    assert [item["node"] for item in result.workflow_trace].count("plan_node") == 2
    assert "run.inspect" in action_names
    assert "final.answer" in action_names
    assert "run_id" in result.output


def test_chat_agent_uses_loop_graph(monkeypatch):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": "loop mode reply",
                "error": None,
            },
        )(),
    )

    async def call_build_agent_reply():
        return await build_agent_reply(
            "hello",
            None,
            intent="chat",
            emit_chat_message=False,
            emit_node_events=False,
        )

    result = anyio.run(call_build_agent_reply)

    assert result.ok is True
    assert result.intent == "chat"
    assert result.output == "loop mode reply"
