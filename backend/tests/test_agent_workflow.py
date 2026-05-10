from backend.app.agent_workflow.graph.agent_graph import run_agent
from backend.app.agent_workflow.graph.graph_support import (
    AGENT_CODING_EDGE_MAP,
    AGENT_LINEAR_EDGES,
    AGENT_ROUTER_EDGE_MAP,
    AGENT_WORKSPACE_TOOL_EDGE_MAP,
    configure_agent_graph_edges,
    guard_node,
    register_agent_graph_nodes,
)
from backend.app.agent_workflow.state.run_support import (
    build_run_control_fallback_next_action,
    execute_run_control_action,
    resolve_target_run_id,
)
from backend.app.agent_workflow.state.run_state import (
    WorkflowRunStateSnapshot,
    build_run_state_updates,
)
from backend.app.agent_workflow.state.state_support import (
    append_workflow_trace,
    normalize_optional_text,
)
from backend.app.agent_workflow.agent_support import (
    build_agent_initial_state,
    build_chat_result_state,
    build_coding_requested_state,
    build_run_control_failure_state,
    build_run_control_success_state,
    build_run_creation_failure_state,
    build_run_creation_success_state,
    build_run_snapshot_failure_state,
    build_run_snapshot_progress_state,
    build_run_snapshot_success_state,
    build_run_terminal_summary_state,
    build_unknown_intent_output,
    build_unknown_intent_state,
    build_workspace_tool_state,
    emit_agent_roleplay_state,
    merge_context_sections,
    merge_agent_state,
    select_coding_next_node,
    select_workspace_tool_next_node,
    select_agent_next_node,
)
from backend.app.agent_workflow.output.text import describe_run_action
from backend.app.agent_workflow.trace.messages import (
    build_trace_event_label,
    build_trace_message,
    build_trace_status_level,
)
from backend.app.agent_workflow.trace.runtime import (
    build_runtime_event_summary,
    build_workflow_trace_entry,
    find_failure_trace,
    normalize_trace_items,
)
from backend.app.agent_workflow.output.roleplay import emit_roleplay_message, emit_roleplay_state
from backend.app.agent_workflow.output.node_events import emit_workflow_node_entered
from backend.app.agent_workflow.contracts.workflow_results import WorkflowAgentResult
from backend.app.core.config import settings
from backend.app.message_queue import message_queue
from backend.app.services.chat_action.intent import detect_intent, detect_run_action, extract_run_reference
from backend.app.services.chat_action.types import ChatServiceResult
from backend.app.services.run_action.types import WorkflowChatMessage
from backend.app.services.run_interface import create_run, get_run
from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import read_workspace_text


def test_agent_graph_routes_coding_intent_to_run_tool():
    result = run_agent("write python code", None, intent="coding")

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id
    assert result.run_status == "queued"
    assert result.as_dict()["intent"] == "coding"
    assert len(result.workflow_trace) >= 4
    assert result.workflow_trace[0]["node"] == "router"
    assert result.workflow_trace[-1]["node"] == "roleplay_node"

    run = get_run(str(result.run_id))
    assert run is not None
    assert run.status == "queued"


def test_agent_graph_can_inspect_existing_run_snapshot():
    run = create_run("build a calculator demo", None)

    result = run_agent(
        f"请查看 run_id {run.run_id} 的状态",
        None,
        intent="coding",
        emit_chat_message=False,
    )

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id == run.run_id
    assert result.run_status == "queued"
    assert result.run_action == "inspect"
    assert result.state["target_run_id"] == run.run_id
    assert "我读取了这个代码任务的中间状态，当前还在排队。" in result.output
    assert "当前快照:" in result.output
    assert "下一步:" in result.output


def test_agent_graph_can_inspect_terminal_run_and_return_summary(monkeypatch):
    run_id = "123e4567-e89b-12d3-a456-426614174000"

    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.get_run_snapshot",
        lambda target_run_id: type(
            "FakeRunSnapshot",
            (),
            {
                "status": "done",
                "summary": "任务执行成功。",
                "next_action": "任务已完成，可查看最终结果、产物或执行日志。",
                "terminal": True,
                "latest_attempt_summary": "第 1 次尝试（本地模板）：执行成功。",
                "cancel_requested": False,
            },
        )(),
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.get_run",
        lambda target_run_id: type(
            "FakeRunResponse",
            (),
            {
                "model_dump": lambda self=None: {
                    "run_id": run_id,
                    "status": "done",
                    "output": "任务已完成。",
                    "error": None,
                    "attempt_count": 1,
                    "repair_count": 0,
                    "generator": "template",
                    "prompt": "build demo",
                    "attempts": [],
                },
            },
        )(),
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.summarize_run_record",
        lambda record, emit_chat_message=False: type(
            "FakeSummaryResult",
            (),
            {
                "ok": True,
                "output": (
                    "代码任务已经完成。\n"
                    f"run_id: {run_id}\n"
                    "状态: done\n"
                    "摘要: 最终输出已经生成。"
                ),
                "summary_text": "最终输出已经生成。",
            },
        )(),
    )

    result = run_agent(
        f"请查看 run_id {run_id} 的状态",
        None,
        intent="coding",
        emit_chat_message=False,
    )

    assert result.ok is True
    assert result.run_id == run_id
    assert result.run_status == "done"
    assert result.run_action == "inspect"
    assert result.state["ui_status"] == "run_snapshot_terminal"
    assert "代码任务已经完成。" in result.output
    assert "摘要: 最终输出已经生成。" in result.output


def test_agent_graph_can_retry_existing_run(monkeypatch):
    source_run_id = "123e4567-e89b-12d3-a456-426614174000"
    captured: dict[str, object] = {}

    def fake_retry_run(run_id: str):
        captured["run_id"] = run_id
        return type(
            "FakeRun",
            (),
            {
                "run_id": "retry-run-1",
                "status": "queued",
                "output": "重试任务已创建，等待后台执行。",
            },
        )()

    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.retry_run",
        fake_retry_run,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.get_run_snapshot",
        lambda run_id: type(
            "FakeRunSnapshot",
            (),
            {
                "status": "queued",
                "summary": "任务已创建，等待后台执行。",
                "next_action": "等待后台开始执行，然后继续查询任务状态。",
            },
        )(),
    )

    result = run_agent(
        f"请 retry run_id {source_run_id}",
        None,
        intent="coding",
        emit_chat_message=False,
    )

    assert captured["run_id"] == source_run_id
    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id == "retry-run-1"
    assert result.run_status == "queued"
    assert result.run_action == "retry"
    assert "source_run_id: 123e4567-e89b-12d3-a456-426614174000" in result.output
    assert "当前快照:" in result.output
    assert "下一步:" in result.output


def test_agent_graph_routes_chat_intent_to_llm(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": f"reply to {prompt}",
                "error": None,
            },
        )(),
    )

    result = run_agent("hello", "ctx", intent="chat", emit_chat_message=False)

    assert result.ok is True
    assert result.intent == "chat"
    assert result.output == "reply to hello"
    assert result.run_id is None
    assert result.as_dict()["output"] == "reply to hello"
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "chat_node",
        "roleplay_node",
    ]


def test_agent_graph_captures_node_exception_with_trace(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.call_llm_sync",
        lambda prompt, context: (_ for _ in ()).throw(RuntimeError("llm raised boom")),
    )

    result = run_agent("hello", None, intent="chat", emit_chat_message=False)

    assert result.ok is False
    assert result.intent == "chat"
    assert result.ui_status == "workflow_node_failed"
    assert result.error == "llm raised boom"
    assert "chat_node" in result.output
    assert result.workflow_trace[-2]["node"] == "chat_node"
    assert result.workflow_trace[-2]["event"] == "node_exception"
    assert result.workflow_trace[-2]["event_type"] == "workflow.node_exception"
    assert result.workflow_trace[-2]["event_source"] == "chat"
    assert result.workflow_trace[-2]["event_stage"] == "chat"
    assert result.workflow_trace[-2]["frontend_visible"] is False
    assert result.workflow_trace[-1]["node"] == "roleplay_node"


def test_agent_graph_routes_coding_intent_with_workspace_tool_context(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "backend.app.tools.workspace_tools.build_workspace_overview",
        lambda **kwargs: "Workspace top-level entries:\n- [file] README.md",
    )

    def fake_create_run(prompt: str, context: str | None):
        captured["prompt"] = prompt
        captured["context"] = context
        return type("FakeRun", (), {"run_id": "run-tool-1", "status": "queued"})()

    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.create_run",
        fake_create_run,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.get_run_snapshot",
        lambda run_id: type(
            "FakeRunSnapshot",
            (),
            {
                "status": "queued",
                "summary": "任务已创建，等待后台执行。",
                "next_action": "等待后台开始执行，然后继续查询任务状态。",
            },
        )(),
    )

    result = run_agent("write python code", "client ctx", intent="coding")

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id == "run-tool-1"
    assert result.state["workspace_tool_name"] == "build_workspace_overview"
    assert result.state["run_summary"] is not None
    assert result.state["run_next_action"] is not None
    assert "当前快照:" in result.output
    assert "下一步:" in result.output
    assert captured["prompt"] == "write python code"
    assert captured["context"] == (
        "client ctx\n\n"
        "Workspace overview for the coding task:\n"
        "Workspace top-level entries:\n"
        "- [file] README.md"
    )


def test_agent_graph_finishes_simple_workspace_text_write_without_run():
    result = run_agent(
        "请创建 notes/todo.txt，内容是buy milk",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id is None
    assert result.state["workspace_tool_name"] == "write_workspace_text"
    assert result.state["workspace_tool_terminal"] is True
    assert result.state["workspace_tool_error"] is None
    assert "已在 workspace 中创建文本文件" in result.output
    assert read_workspace_text("notes/todo.txt")["content"] == "buy milk"
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "roleplay_node",
    ]


def test_agent_graph_finishes_pure_workspace_file_read_without_run():
    safe_write_file("backend/app/demo.txt", "demo content")

    result = run_agent(
        "请读取 backend/app/demo.txt",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.state["workspace_tool_name"] == "read_workspace_text"
    assert result.state["workspace_tool_terminal"] is True
    assert "我读到了 `backend/app/demo.txt` 的内容" in result.output
    assert "内容预览:" in result.output
    assert "demo content" in result.output
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "roleplay_node",
    ]


def test_agent_graph_finishes_pure_workspace_listing_without_run():
    safe_write_file("demo/nested/info.txt", "nested data")

    result = run_agent(
        "请列出 demo/nested 目录结构",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.state["workspace_tool_name"] == "list_workspace_entries"
    assert result.state["workspace_tool_terminal"] is True
    assert "我列出了 `demo/nested` 下的内容" in result.output
    assert "文件: demo/nested/info.txt" in result.output
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "roleplay_node",
    ]


def test_agent_graph_finishes_pure_workspace_test_without_run():
    safe_write_file(
        "backend/tests/test_demo_pass.py",
        "def test_demo_pass():\n"
        "    assert True\n",
    )

    result = run_agent(
        "请运行 backend/tests/test_demo_pass.py 的测试",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.state["workspace_tool_name"] == "run_workspace_tests"
    assert result.state["workspace_tool_terminal"] is True
    assert "我运行完测试了" in result.output
    assert "结果: 通过" in result.output
    assert "测试命令执行成功" in result.output
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "roleplay_node",
    ]


def test_agent_graph_keeps_codegen_for_file_repair_request(monkeypatch):
    captured: dict[str, object] = {}
    safe_write_file("backend/app/demo.txt", "broken content")

    def fake_create_run(prompt: str, context: str | None):
        captured["prompt"] = prompt
        captured["context"] = context
        return type("FakeRun", (), {"run_id": "repair-run-1", "status": "queued"})()

    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.create_run",
        fake_create_run,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.get_run_snapshot",
        lambda run_id: type(
            "FakeRunSnapshot",
            (),
            {
                "status": "queued",
                "summary": "任务已创建，等待后台执行。",
                "next_action": "等待后台开始执行，然后继续查询任务状态。",
            },
        )(),
    )

    result = run_agent(
        "请修复 backend/app/demo.txt 里的问题",
        "client ctx",
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id == "repair-run-1"
    assert result.state["workspace_tool_name"] == "read_workspace_text"
    assert result.state["workspace_tool_terminal"] is False
    assert captured["prompt"] == "请修复 backend/app/demo.txt 里的问题"
    assert captured["context"] == (
        "client ctx\n\n"
        "Workspace file preview (backend/app/demo.txt):\n"
        "broken content"
    )
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "run_tool_node",
        "roleplay_node",
    ]


def test_agent_graph_rejects_desktop_text_write_without_run():
    result = run_agent(
        "帮我在桌面创建一个txt文件",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    assert result.ok is True
    assert result.run_id is None
    assert result.ui_status == "workspace_tool_failed"
    assert result.state["workspace_tool_name"] == "write_workspace_text"
    assert result.state["workspace_tool_terminal"] is True
    assert result.state["workspace_tool_error_code"] == "WORKSPACE_TOOL_TARGET_DISABLED"
    assert "不能直接写桌面路径" in result.output
    assert [item["node"] for item in result.workflow_trace] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "roleplay_node",
    ]


def test_agent_graph_exports_desktop_text_when_enabled(monkeypatch, tmp_path):
    export_dir = tmp_path / "desktop-exports"
    monkeypatch.setattr(settings, "desktop_export_enabled", True)
    monkeypatch.setattr(settings, "desktop_export_dir", export_dir)

    result = run_agent(
        "帮我在桌面创建 notes/todo.txt，内容是buy milk",
        None,
        intent="coding",
        emit_chat_message=False,
        emit_node_events=False,
    )

    exported_file = export_dir / "todo.txt"
    assert result.ok is True
    assert result.run_id is None
    assert result.state["workspace_tool_name"] == "write_workspace_text"
    assert result.state["workspace_tool_terminal"] is True
    assert result.state["workspace_tool_error"] is None
    assert "已按配置导出文本文件到桌面导出目录" in result.output
    assert exported_file.read_text(encoding="utf-8") == "buy milk"


def test_agent_support_builds_initial_state_with_optional_intent():
    state = build_agent_initial_state(
        prompt="hello",
        context="ctx",
        session_id="session-1",
        emit_chat_message=False,
        intent="chat",
    )

    assert state["user_input"] == "hello"
    assert state["context"] == "ctx"
    assert state["session_id"] == "session-1"
    assert state["emit_chat_message"] is False
    assert state["emit_node_events"] is True
    assert state["intent"] == "chat"
    assert state["run_id"] is None
    assert state["ui_status"] is None


def test_agent_support_selects_route_and_builds_unknown_output():
    assert select_agent_next_node("chat") == "chat_node"
    assert select_agent_next_node("coding") == "coding_node"
    assert select_agent_next_node("something-else") == "unknown_node"

    output = build_unknown_intent_output("???")

    assert "你输入的内容是：???" in output
    assert "如果你只是想聊天" in output
    assert "如果你想让我处理代码任务" in output


def test_intent_detection_can_identify_run_inspection_prompt():
    run_id = "123e4567-e89b-12d3-a456-426614174000"

    assert extract_run_reference(f"请查看 run_id {run_id} 的状态") == run_id
    assert detect_run_action(f"请查看 run_id {run_id} 的状态") == "inspect"
    assert detect_intent(f"请查看 run_id {run_id} 的状态") == "coding"


def test_intent_detection_can_identify_run_control_prompts():
    run_id = "123e4567-e89b-12d3-a456-426614174000"

    assert detect_run_action(f"请 retry run_id {run_id}") == "retry"
    assert detect_run_action(f"请重新运行 run_id {run_id}") == "rerun"
    assert detect_run_action(f"请取消 run_id {run_id}") == "cancel"
    assert detect_intent(f"请取消 run_id {run_id}") == "coding"


def test_agent_support_merges_context_sections_and_builds_tool_plan(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.builder_support.plan_workspace_tool",
        lambda prompt: {
            "tool_name": "read_workspace_text",
            "tool_input": {"rel_path": "backend/app/demo.txt"},
            "reason": "Prompt references a workspace file path.",
        },
    )

    merged_context = merge_context_sections("client ctx", None, "tool ctx")
    state = build_coding_requested_state(
        build_agent_initial_state(
            prompt="write code",
            context="client ctx",
            session_id=None,
            emit_chat_message=False,
        )
    )

    assert merged_context == "client ctx\n\ntool ctx"
    assert state["context"] == "client ctx"
    assert state["workspace_tool_name"] == "read_workspace_text"
    assert state["workspace_tool_category"] == "context"
    assert state["workspace_tool_output_kind"] == "file_preview"
    assert state["workspace_tool_plan"] == {
        "tool_name": "read_workspace_text",
        "tool_input": {"rel_path": "backend/app/demo.txt"},
        "reason": "Prompt references a workspace file path.",
    }
    assert state["ui_status"] == "coding_requested"


def test_agent_support_builds_run_inspection_request_without_workspace_tool():
    run_id = "123e4567-e89b-12d3-a456-426614174000"
    state = build_coding_requested_state(
        build_agent_initial_state(
            prompt=f"请查看 run_id {run_id} 的状态",
            context="client ctx",
            session_id=None,
            emit_chat_message=False,
        )
    )

    assert state["run_action"] == "inspect"
    assert state["target_run_id"] == run_id
    assert state["workspace_tool_plan"] is None
    assert state["workspace_tool_name"] is None
    assert select_coding_next_node(state) == "run_snapshot_node"


def test_agent_support_builds_run_control_request_without_workspace_tool():
    run_id = "123e4567-e89b-12d3-a456-426614174000"
    state = build_coding_requested_state(
        build_agent_initial_state(
            prompt=f"请 retry run_id {run_id}",
            context="client ctx",
            session_id=None,
            emit_chat_message=False,
        )
    )

    assert state["run_action"] == "retry"
    assert state["target_run_id"] == run_id
    assert state["workspace_tool_plan"] is None
    assert state["workspace_tool_name"] is None
    assert select_coding_next_node(state) == "run_control_node"


def test_agent_support_routes_terminal_workspace_tool_to_roleplay():
    assert select_workspace_tool_next_node({"workspace_tool_terminal": True}) == "roleplay_node"
    assert select_workspace_tool_next_node({"workspace_tool_terminal": False}) == "run_tool_node"


def test_agent_run_support_resolves_target_run_id():
    state = {
        "target_run_id": "run-target-1",
        "run_id": "run-fallback-1",
    }

    assert resolve_target_run_id(state) == "run-target-1"
    assert resolve_target_run_id({"run_id": "run-fallback-1"}) == "run-fallback-1"
    assert resolve_target_run_id({}) == ""


def test_agent_run_state_helpers_normalize_and_build_updates():
    snapshot = WorkflowRunStateSnapshot.from_state(
        {
            "run_id": " run-1 ",
            "run_status": " queued ",
            "run_action": " inspect ",
            "target_run_id": " run-target-1 ",
            "run_summary": " summary ",
            "run_next_action": " next step ",
            "ui_status": " run_snapshot_ready ",
        }
    )
    updates = build_run_state_updates(
        run_id=" run-2 ",
        run_status=" running ",
        run_action=" retry ",
        run_summary="  ",
        run_next_action=" continue ",
        ui_status=" run_control_done ",
    )

    assert snapshot.run_id == "run-1"
    assert snapshot.run_status == "queued"
    assert snapshot.run_action == "inspect"
    assert snapshot.target_run_id == "run-target-1"
    assert snapshot.run_summary == "summary"
    assert snapshot.run_next_action == "next step"
    assert snapshot.ui_status == "run_snapshot_ready"
    assert snapshot.resolved_target_run_id() == "run-target-1"
    assert snapshot.run_payload() == ("run-1", "queued")
    assert updates == {
        "run_id": "run-2",
        "run_status": "running",
        "run_action": "retry",
        "run_summary": None,
        "run_next_action": "continue",
        "ui_status": "run_control_done",
    }


def test_agent_run_support_executes_control_action_and_fallback_text():
    captured: dict[str, str] = {}

    result = execute_run_control_action(
        action="retry",
        target_run_id="run-1",
        retry_action=lambda run_id: captured.setdefault("run_id", run_id) or {"ok": True},
        rerun_action=lambda run_id: {"mode": "rerun", "run_id": run_id},
        cancel_action=lambda run_id: {"mode": "cancel", "run_id": run_id},
    )

    assert captured["run_id"] == "run-1"
    assert result == "run-1"
    assert build_run_control_fallback_next_action("retry") == "等待后台开始执行，然后继续查询任务状态。"
    assert build_run_control_fallback_next_action("cancel") == "任务状态已更新，可继续查询任务快照确认最终结果。"


def test_agent_text_and_state_support_helpers_expose_stable_utilities():
    assert describe_run_action("cancel") == "取消"
    assert describe_run_action("other") == "处理"
    assert normalize_optional_text("  demo  ") == "demo"
    assert normalize_optional_text("   ") is None


def test_trace_runtime_builds_stable_workflow_trace_entries():
    entry = build_workflow_trace_entry(
        step=3,
        node="chat_node",
        event="llm_response_failed",
        ui_status="chat_failed",
        details={"has_error": True},
    )

    assert entry["step"] == 3
    assert entry["event_type"] == "chat.response_failed"
    assert entry["event_source"] == "chat"
    assert entry["event_stage"] == "chat"
    assert entry["frontend_visible"] is False
    assert entry["details"] == {"has_error": True}
    assert build_trace_event_label("llm_response_failed") == "聊天回复失败"
    assert build_trace_event_label("custom_event") == "custom_event"
    assert build_trace_status_level("workspace_tool_failed") == "error"
    assert build_trace_status_level("workspace_tool_skipped") == "warning"
    assert build_trace_status_level("workspace_tool_applied") == "info"
    assert build_trace_message(
        {
            "node_label": "代码任务预处理",
            "event": "coding_request_prepared",
            "details": {
                "run_action": "create",
                "workspace_tool_name": "read_workspace_text",
                "workspace_tool_title": "读取工作区文本",
                "workspace_tool_category": "context",
                "workspace_tool_output_kind": "file_preview",
            },
        }
    ) == (
        "代码任务预处理已解析 coding 请求，动作为 `create`，"
        "并规划工作区工具 `read_workspace_text`（读取工作区文本），"
        "类别 `context`，输出 `file_preview`。"
    )


def test_append_workflow_trace_uses_runtime_trace_entry_helper():
    state = append_workflow_trace(
        {
            "workflow_trace": [
                {"step": 1, "node": "router", "event": "intent_routed"},
                "invalid trace item",
            ],
        },
        node="workspace_tool_node",
        event="workspace_tool_applied",
        ui_status="workspace_tool_ready",
        details={"tool_name": "build_workspace_overview"},
    )

    trace = state["workflow_trace"]

    assert len(trace) == 2
    assert trace[-1]["step"] == 2
    assert trace[-1]["event_type"] == "tool.applied"
    assert trace[-1]["event_source"] == "tool"
    assert trace[-1]["event_stage"] == "tools"
    assert trace[-1]["ui_status"] == "workspace_tool_ready"
    assert trace[-1]["details"] == {"tool_name": "build_workspace_overview"}


def test_trace_runtime_normalizes_failure_and_event_summary():
    trace = normalize_trace_items(
        [
            {"step": 1, "node": "router", "event": "intent_routed"},
            {
                "step": 2,
                "node": "chat_node",
                "event": "llm_response_failed",
                "details": {"has_error": True},
            },
            "invalid trace item",
        ]
    )
    failure = find_failure_trace(trace)
    summary = build_runtime_event_summary(trace)

    assert len(trace) == 2
    assert trace[0]["node_label"] == "意图路由"
    assert trace[0]["event_type"] == "workflow.intent_routed"
    assert trace[1]["status_level"] == "error"
    assert failure is not None
    assert failure["event"] == "llm_response_failed"
    assert summary.event_count == 2
    assert summary.error_event_count == 1
    assert summary.event_type_counts["chat.response_failed"] == 1
    assert summary.event_source_counts["workflow"] == 1
    assert summary.event_source_counts["chat"] == 1
    assert summary.last_event_stage == "chat"


def test_agent_graph_support_guard_node_wraps_exceptions():
    wrapped = guard_node(
        "chat_node",
        lambda state: (_ for _ in ()).throw(RuntimeError("boom")),
        failure_builder=lambda state, node_name, exc: {
            "state": state,
            "node_name": node_name,
            "error": str(exc),
        },
    )

    result = wrapped({"prompt": "hello"})

    assert result["node_name"] == "chat_node"
    assert result["error"] == "boom"
    assert result["state"] == {"prompt": "hello"}


def test_agent_graph_support_registers_nodes_and_edges():
    class FakeWorkflow:
        def __init__(self):
            self.nodes: list[str] = []
            self.entry_point: str | None = None
            self.conditional_edges: list[tuple[str, dict[str, str]]] = []
            self.edges: list[tuple[str, str]] = []

        def add_node(self, node_name, handler):
            self.nodes.append(node_name)

        def set_entry_point(self, node_name):
            self.entry_point = node_name

        def add_conditional_edges(self, node_name, route_fn, edge_map):
            self.conditional_edges.append((node_name, dict(edge_map)))

        def add_edge(self, start_node, end_node):
            self.edges.append((start_node, end_node))

    workflow = FakeWorkflow()

    register_agent_graph_nodes(
        workflow,
        node_handlers={
            "router": lambda state: state,
            "chat_node": lambda state: state,
        },
        failure_builder=lambda state, node_name, exc: state,
    )
    configure_agent_graph_edges(
        workflow,
        route_by_intent=lambda state: "chat_node",
        select_coding_next_node=lambda state: "workspace_tool_node",
        select_workspace_tool_next_node=lambda state: "run_tool_node",
        end_node="END",
    )

    assert workflow.nodes == ["router", "chat_node"]
    assert workflow.entry_point == "router"
    assert workflow.conditional_edges == [
        ("router", AGENT_ROUTER_EDGE_MAP),
        ("coding_node", AGENT_CODING_EDGE_MAP),
        ("workspace_tool_node", AGENT_WORKSPACE_TOOL_EDGE_MAP),
    ]
    assert workflow.edges[:-1] == list(AGENT_LINEAR_EDGES)
    assert workflow.edges[-1] == ("roleplay_node", "END")


def test_agent_support_builds_workspace_tool_state_and_merges_context(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.builder_support.execute_workspace_tool_plan",
        lambda plan: {
            "tool_name": "build_workspace_overview",
            "reason": "Provide a compact workspace overview before creating the run.",
            "summary": "Workspace overview for the coding task:\n- [file] README.md",
        },
    )
    base_state = build_agent_initial_state(
        prompt="write code",
        context="client ctx",
        session_id=None,
        emit_chat_message=False,
    )
    base_state["workspace_tool_plan"] = {
        "tool_name": "build_workspace_overview",
        "tool_input": {"rel_path": "."},
        "reason": "Provide a compact workspace overview before creating the run.",
    }

    state = build_workspace_tool_state(base_state)

    assert state["workspace_tool_name"] == "build_workspace_overview"
    assert state["workspace_tool_category"] == "context"
    assert state["workspace_tool_output_kind"] == "overview_text"
    assert state["workspace_tool_error_code"] is None
    assert state["workspace_tool_error"] is None
    assert state["workspace_tool_context"] is not None
    assert "client ctx" in str(state["context"])
    assert "Workspace overview for the coding task:" in str(state["context"])
    assert state["ui_status"] == "workspace_tool_ready"
    assert state["workflow_trace"][-1]["event"] == "workspace_tool_applied"
    assert state["workflow_trace"][-1]["event_type"] == "tool.applied"
    assert state["workflow_trace"][-1]["event_source"] == "tool"
    assert state["workflow_trace"][-1]["event_stage"] == "tools"
    assert state["workflow_trace"][-1]["details"]["tool_title"] == "工作区概览"
    assert state["workflow_trace"][-1]["details"]["tool_category"] == "context"
    assert state["workflow_trace"][-1]["details"]["tool_output_kind"] == "overview_text"


def test_agent_support_keeps_original_context_when_workspace_tool_fails(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.builder_support.execute_workspace_tool_plan",
        lambda plan: {
            "tool_name": "read_workspace_text",
            "reason": "Prompt references a workspace file path.",
            "summary": "Workspace tool `read_workspace_text` failed: boom",
            "error": "boom",
        },
    )
    base_state = build_agent_initial_state(
        prompt="write code",
        context="client ctx",
        session_id=None,
        emit_chat_message=False,
    )
    base_state["workspace_tool_plan"] = {
        "tool_name": "read_workspace_text",
        "tool_input": {"rel_path": "backend/app/demo.txt"},
        "reason": "Prompt references a workspace file path.",
    }

    state = build_workspace_tool_state(base_state)

    assert state["context"] == "client ctx"
    assert state["workspace_tool_category"] == "context"
    assert state["workspace_tool_output_kind"] == "file_preview"
    assert state["workspace_tool_error"] == "boom"
    assert state["ui_status"] == "workspace_tool_failed"
    assert state["workflow_trace"][-1]["event"] == "workspace_tool_failed"
    assert state["workflow_trace"][-1]["event_type"] == "tool.failed"
    assert state["workflow_trace"][-1]["event_source"] == "tool"
    assert state["workflow_trace"][-1]["event_stage"] == "tools"
    assert state["workflow_trace"][-1]["details"]["tool_title"] == "读取工作区文本"


def test_agent_support_builds_run_snapshot_states():
    base_state = build_agent_initial_state(
        prompt="inspect run",
        context=None,
        session_id=None,
        emit_chat_message=False,
    )
    success_state = build_run_snapshot_success_state(
        base_state,
        run_id="run-1",
        status="running",
        snapshot_summary="任务正在执行中。",
        next_action="继续轮询任务状态。",
    )
    failure_state = build_run_snapshot_failure_state(
        base_state,
        run_id="run-2",
        error="未找到对应的代码任务。",
    )

    assert success_state["run_id"] == "run-1"
    assert success_state["run_action"] == "inspect"
    assert success_state["ui_status"] == "run_snapshot_ready"
    assert "我读取了这个代码任务的当前状态。" in success_state["output"]
    assert failure_state["run_id"] == "run-2"
    assert failure_state["run_action"] == "inspect"
    assert failure_state["ui_status"] == "run_snapshot_failed"
    assert "未找到对应的代码任务。" in failure_state["output"]


def test_agent_support_builds_run_snapshot_progress_and_terminal_states():
    base_state = build_agent_initial_state(
        prompt="inspect run",
        context=None,
        session_id=None,
        emit_chat_message=False,
    )
    progress_state = build_run_snapshot_progress_state(
        base_state,
        run_id="run-1",
        status="running",
        snapshot_summary="任务正在执行中。",
        next_action="继续轮询任务状态。",
        latest_attempt_summary="第 1 次尝试（本地模板）：正在执行。",
        cancel_requested=False,
    )
    terminal_state = build_run_terminal_summary_state(
        base_state,
        run_id="run-2",
        status="done",
        summary_text="最终输出已经生成。",
        next_action="任务已完成，可查看最终结果、产物或执行日志。",
    )

    assert progress_state["run_id"] == "run-1"
    assert progress_state["ui_status"] == "run_snapshot_in_progress"
    assert "最近一次尝试:" in progress_state["output"]
    assert terminal_state["run_id"] == "run-2"
    assert terminal_state["ui_status"] == "run_snapshot_terminal"
    assert "最终总结: 最终输出已经生成。" in terminal_state["output"]


def test_agent_support_builds_run_control_states():
    base_state = build_agent_initial_state(
        prompt="retry run",
        context=None,
        session_id=None,
        emit_chat_message=False,
    )
    success_state = build_run_control_success_state(
        base_state,
        action="retry",
        source_run_id="run-source-1",
        run_id="run-1",
        status="queued",
        snapshot_summary="任务已创建，等待后台执行。",
        next_action="等待后台开始执行，然后继续查询任务状态。",
    )
    failure_state = build_run_control_failure_state(
        base_state,
        action="cancel",
        run_id="run-2",
        error="run with status 'done' does not support cancel",
    )

    assert success_state["run_id"] == "run-1"
    assert success_state["run_action"] == "retry"
    assert success_state["ui_status"] == "run_control_done"
    assert "source_run_id: run-source-1" in success_state["output"]
    assert failure_state["run_id"] == "run-2"
    assert failure_state["run_action"] == "cancel"
    assert failure_state["ui_status"] == "run_control_failed"
    assert "取消操作" in failure_state["output"]


def test_agent_support_merges_state_and_builds_node_results():
    base_state = build_agent_initial_state(
        prompt="hello",
        context=None,
        session_id=None,
        emit_chat_message=False,
    )

    merged_state = merge_agent_state(base_state, ui_status="demo", output="x")
    chat_state = build_chat_result_state(base_state, output="reply", error=None)
    failed_run_state = build_run_creation_failure_state(base_state, error="boom")
    queued_run_state = build_run_creation_success_state(
        base_state,
        run_id="run-1",
        status="queued",
        snapshot_summary="任务已创建，等待后台执行。",
        next_action="等待后台开始执行，然后继续查询任务状态。",
    )
    unknown_state = build_unknown_intent_state(base_state, prompt="???")

    assert merged_state["ui_status"] == "demo"
    assert merged_state["output"] == "x"
    assert chat_state["ui_status"] == "chat_done"
    assert chat_state["output"] == "reply"
    assert failed_run_state["ui_status"] == "run_create_failed"
    assert "代码任务创建失败" in failed_run_state["output"]
    assert queued_run_state["ui_status"] == "run_queued"
    assert queued_run_state["run_id"] == "run-1"
    assert queued_run_state["run_summary"] == "任务已创建，等待后台执行。"
    assert queued_run_state["run_next_action"] == "等待后台开始执行，然后继续查询任务状态。"
    assert "当前快照: 任务已创建，等待后台执行。" in queued_run_state["output"]
    assert unknown_state["ui_status"] == "unknown_done"


def test_workflow_node_entered_event_emits_quip_and_status_messages():
    state = build_agent_initial_state(
        prompt="write python code",
        context=None,
        session_id=None,
        emit_chat_message=False,
        emit_node_events=True,
        intent="coding",
    )

    assert emit_workflow_node_entered(state, "workspace_tool_node") is True

    messages = message_queue.get_messages()
    assert len(messages) == 2
    assert [message["type"] for message in messages] == ["quip", "status"]
    assert {message["event_type"] for message in messages} == {"workflow.node_entered"}
    assert {message["event_source"] for message in messages} == {"workflow"}
    assert {message["event_stage"] for message in messages} == {"tools"}
    assert {message["node_name"] for message in messages} == {"workspace_tool_node"}
    assert messages[0]["content"] == "我先查看一下项目上下文。"
    assert messages[0]["metadata"]["node_label"] == "工作区工具"
    assert messages[0]["metadata"]["phase"] == "tools"
    assert messages[1]["status"] == "running"
    assert messages[1]["progress"] == 30
    assert messages[1]["metadata"]["runtime_event"] == "node_entered"


def test_workflow_node_entered_event_can_be_suppressed():
    state = build_agent_initial_state(
        prompt="write python code",
        context=None,
        session_id=None,
        emit_chat_message=False,
        emit_node_events=False,
        intent="coding",
    )

    assert emit_workflow_node_entered(state, "workspace_tool_node") is False
    assert message_queue.get_messages() == []


def test_agent_support_roleplay_helper_emits_message():
    state = build_agent_initial_state(
        prompt="hello",
        context=None,
        session_id=None,
        emit_chat_message=True,
    )
    state["output"] = "roleplay content"

    result_state = emit_agent_roleplay_state(state, node_name="agent_roleplay")
    messages = message_queue.get_messages()

    assert result_state["output"] == "roleplay content"
    assert len(messages) == 1
    assert messages[0]["type"] == "chat"
    assert messages[0]["node_name"] == "agent_roleplay"
    assert messages[0]["content"] == "roleplay content"


def test_roleplay_helpers_emit_message_from_message_and_state():
    message_queue.clear()

    emit_roleplay_message(
        WorkflowChatMessage(
            node_name="task_repairing",
            content="repair feedback",
        ),
        default_node_name="agent_roleplay",
    )
    state = emit_roleplay_state(
        {
            "output": "state content",
            "node_name": "summary_demo",
            "emit_chat_message": True,
        },
        default_node_name="agent_roleplay",
    )
    messages = message_queue.get_messages()

    assert state["output"] == "state content"
    assert len(messages) == 2
    assert messages[0]["node_name"] == "task_repairing"
    assert messages[0]["content"] == "repair feedback"
    assert messages[1]["node_name"] == "summary_demo"
    assert messages[1]["content"] == "state content"


def test_chat_service_result_can_normalize_agent_result_and_apply_updates():
    fake_agent_result = type(
        "FakeAgentResult",
        (),
        {
            "intent": "other",
            "ok": True,
            "output": "   ",
            "error": None,
            "run_id": " run-1 ",
            "run_action": " inspect ",
        },
    )()

    result = ChatServiceResult.from_agent_result(
        fake_agent_result,
        intent_hint="coding",
        fallback_output_builder=lambda intent: f"fallback::{intent}",
    )
    updated = result.with_updates(session_id="session-1", error="boom")

    assert result.intent == "unknown"
    assert result.is_intent("unknown") is True
    assert result.output == "fallback::unknown"
    assert result.run_id == "run-1"
    assert result.run_action == "inspect"
    assert updated.session_id == "session-1"
    assert updated.error == "boom"
    assert result.session_id is None


def test_workflow_agent_result_can_normalize_generic_object_fields():
    fake_agent_result = type(
        "FakeAgentWorkflowResult",
        (),
        {
            "ok": True,
            "output": "agent output",
            "intent": "coding",
            "error": None,
            "run_id": " run-2 ",
            "run_status": " queued ",
            "run_action": " create ",
            "ui_status": " run_queued ",
            "workflow_trace": [{"step": 1, "node": "router", "event": "intent_routed"}],
        },
    )()

    result = WorkflowAgentResult.from_value(
        fake_agent_result,
        default_intent="unknown",
    )

    assert result.ok is True
    assert result.output == "agent output"
    assert result.intent == "coding"
    assert result.run_id == "run-2"
    assert result.run_status == "queued"
    assert result.run_action == "create"
    assert result.ui_status == "run_queued"
    assert result.workflow_trace[0]["node"] == "router"


def test_workflow_agent_result_exposes_consumption_helpers():
    result = WorkflowAgentResult.from_value(
        {
            "ok": True,
            "output": "   ",
            "intent": "other",
            "run_id": "run-3",
            "run_status": "queued",
        }
    )

    assert result.resolved_intent(valid_intents={"chat", "coding", "unknown"}) == "unknown"
    assert result.resolved_output(
        intent="unknown",
        fallback_output_builder=lambda intent: f"fallback::{intent}",
    ) == "fallback::unknown"
    assert result.run_payload() == ("run-3", "queued")
