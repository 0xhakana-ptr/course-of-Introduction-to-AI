import json

from backend.app.agent_workflow.graphs.coding_graph import (
    CODER_NODE,
    CODING_FAILURE_NODE,
    CODING_FINISH_NODE,
    CODING_START_NODE,
    EXECUTOR_NODE,
    DEBUGGER_NODE,
    PM_NODE,
    QA_NODE,
    run_coding_workflow,
    build_coding_workflow_node_failure_state,
)
from backend.app.agent_workflow.graphs.coding_result import CodingWorkflowResult
from backend.app.agent_workflow.graphs.coding_artifacts import (
    clear_coding_artifacts,
    read_coding_artifact,
)
from backend.app.services.run_action.queries import get_run
from backend.app.message_queue import message_queue
from backend.app.tools.safe_fs import resolve_workspace_path, safe_write_file
from backend.app.tools.workspace_tools import read_workspace_text


def _fake_llm_result(output: str, *, ok: bool = True, error: str | None = None):
    return type(
        "FakeLLMResult",
        (),
        {
            "ok": ok,
            "output": output,
            "error": error,
            "error_kind": None if ok else "request",
        },
    )()


def test_coding_workflow_skeleton_runs_without_executing_tools():
    result = run_coding_workflow(
        "请创建 notes/coding-subgraph.txt，内容是 hello",
        session_id="session_1",
        turn_id="turn_1",
    )

    payload = result.as_dict()
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is True
    assert result.error is None
    assert result.ui_status == "coding_skeleton_ready"
    assert result.stop_reason == "completed"
    assert result.current_task is not None
    assert result.tasks_list == [result.current_task]
    assert trace_nodes == [CODING_START_NODE, PM_NODE, CODER_NODE, CODING_FINISH_NODE]
    assert payload["coding_state"]["turn"]["turn_id"] == "turn_1"
    assert payload["coding_state"]["turn"]["session_id"] == "session_1"
    assert payload["coding_state"]["frontend"]["ui_status"] == "coding_skeleton_ready"
    assert payload["coding_state"]["engineering"]["tasks_list"] == result.tasks_list
    assert payload["coding_state"]["tool"] == {}
    assert "No tools were executed" in result.output


def test_coding_workflow_result_is_json_serializable_and_partitioned():
    result = run_coding_workflow("请读取 notes/demo.txt")

    dumped = json.dumps(result.as_dict(), ensure_ascii=False)

    assert '"raw_error":' not in dumped
    assert '"stderr":' not in dumped
    assert '"stdout":' not in dumped
    assert "coding_state" in result.as_dict()


def test_coding_workflow_executes_simple_workspace_write_action():
    result = run_coding_workflow(
        "请创建 notes/coding-action.txt，内容是 from coding subgraph",
        workspace_action_name="workspace.write",
        workspace_action_input={
            "rel_path": "notes/coding-action.txt",
            "content": "from coding subgraph",
        },
    )
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is True
    assert result.action_result is not None
    assert result.action_result["action_name"] == "workspace.write"
    assert result.action_result["metadata"]["workflow_name"] == "coding"
    assert trace_nodes == [
        CODING_START_NODE,
        PM_NODE,
        CODER_NODE,
        EXECUTOR_NODE,
        CODING_FINISH_NODE,
    ]
    assert read_workspace_text("notes/coding-action.txt")["content"] == "from coding subgraph"


def test_coding_workflow_emits_bridge_status_for_internal_nodes():
    result = run_coding_workflow(
        "请创建 notes/coding-node-events.txt，内容是 node events",
        workspace_action_name="workspace.write",
        workspace_action_input={
            "rel_path": "notes/coding-node-events.txt",
            "content": "node events",
        },
    )

    messages = message_queue.get_messages()
    status_by_node = {
        message["node_name"]: message
        for message in messages
        if message.get("type") == "status"
        and message.get("event_type") == "workflow.node_entered"
    }

    assert result.ok is True
    assert status_by_node[PM_NODE]["bridge_event_type"] == "Status_Update"
    assert status_by_node[PM_NODE]["bridge_payload"]["phase"] == "coding"
    assert status_by_node[CODER_NODE]["bridge_payload"]["phase"] == "coding"
    assert status_by_node[EXECUTOR_NODE]["bridge_payload"]["phase"] == "tools"
    assert status_by_node[CODING_FINISH_NODE]["bridge_payload"]["node_name"] == CODING_FINISH_NODE


def test_coding_workflow_uses_llm_planner_only_as_safe_plan_source(monkeypatch):
    planner_module = __import__(
        "backend.app.agent_workflow.graphs.coding_planner",
        fromlist=["call_llm_sync", "llm_is_configured"],
    )
    monkeypatch.setattr(planner_module, "llm_is_configured", lambda: True)
    monkeypatch.setattr(
        planner_module,
        "call_llm_sync",
        lambda *args, **kwargs: _fake_llm_result(
            """
            {
              "tasks_list": ["Create a file from the LLM plan"],
              "executor_action_name": "workspace.write",
              "executor_action_input": {
                "rel_path": "notes/llm-planner.txt",
                "content": "planned safely"
              },
              "target_files": ["notes/llm-planner.txt"],
              "reason": "The user asked to create a file."
            }
            """
        ),
    )

    result = run_coding_workflow("请创建 notes/llm-planner.txt，内容是 planned safely")

    assert result.ok is True
    assert result.action_result is not None
    assert result.action_result["action_name"] == "workspace.write"
    assert result.action_result["metadata"]["coder_plan"]["planner_source"] == "llm"
    assert result.action_result["metadata"]["coder_plan"]["token_budget"]["max_tokens"] == 700
    assert read_workspace_text("notes/llm-planner.txt")["content"] == "planned safely"


def test_coding_workflow_handles_invalid_llm_planner_json_without_crashing(monkeypatch):
    planner_module = __import__(
        "backend.app.agent_workflow.graphs.coding_planner",
        fromlist=["call_llm_sync", "llm_is_configured"],
    )
    monkeypatch.setattr(planner_module, "llm_is_configured", lambda: True)
    monkeypatch.setattr(
        planner_module,
        "call_llm_sync",
        lambda *args, **kwargs: _fake_llm_result("I will do it directly."),
    )

    result = run_coding_workflow("请创建 notes/invalid-llm-plan.txt")

    assert result.ok is True
    assert result.action_result is None
    assert result.state["coder_plan"]["planner_source"] == "llm"
    assert result.state["coder_plan"]["planner_result"]["error_kind"] == "invalid_json"
    assert not resolve_workspace_path("notes/invalid-llm-plan.txt").exists()


def test_coding_workflow_executes_run_create_through_pm_coder_executor():
    result = run_coding_workflow(
        "写一个 Python 程序打印 hello from coding workflow",
        run_action_name="run.create",
        run_action_input={
            "prompt": "写一个 Python 程序打印 hello from coding workflow",
            "context": None,
        },
    )
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is True
    assert result.action_result is not None
    assert result.action_result["action_name"] == "run.create"
    assert result.action_result["metadata"]["workflow_name"] == "coding"
    assert result.action_result["metadata"]["coder_plan"]["executor_action_name"] == "run.create"
    assert trace_nodes == [
        CODING_START_NODE,
        PM_NODE,
        CODER_NODE,
        EXECUTOR_NODE,
        CODING_FINISH_NODE,
    ]
    run_id = result.action_result["metadata"]["run_id"]
    run = get_run(str(run_id))
    assert run is not None
    assert run.status == "queued"


def test_coding_workflow_qa_summarizes_executor_failure_without_raw_payload():
    clear_coding_artifacts()
    safe_write_file("notes/existing-from-qa.txt", "old")

    result = run_coding_workflow(
        "请创建 notes/existing-from-qa.txt，内容是 new",
        workspace_action_name="workspace.write",
        workspace_action_input={
            "rel_path": "notes/existing-from-qa.txt",
            "content": "new",
        },
    )
    payload = result.as_dict()
    dumped = json.dumps(payload, ensure_ascii=False)
    trace_nodes = [item["node"] for item in result.workflow_trace]
    assert result.action_result is not None
    metadata = result.action_result["metadata"]
    raw_error_ref = str(metadata["raw_error_ref"])
    raw_artifact = read_coding_artifact(raw_error_ref)

    assert result.ok is False
    assert result.error is not None
    assert result.action_result["error"] == result.error
    assert metadata["error_summary"] == result.error
    assert raw_artifact is not None
    assert raw_artifact["error"] == "workspace file already exists: notes/existing-from-qa.txt"
    assert payload["coding_state"]["engineering"]["error_summary"] == result.error
    assert "raw_error_ref" not in payload["coding_state"]["engineering"]
    assert raw_error_ref in payload["coding_state"]["engineering"]["artifact_refs"]
    assert trace_nodes == [
        CODING_START_NODE,
        PM_NODE,
        CODER_NODE,
        EXECUTOR_NODE,
        QA_NODE,
        DEBUGGER_NODE,
        CODING_FAILURE_NODE,
    ]
    assert '"raw_error":' not in dumped
    assert '"stderr":' not in dumped
    assert '"stdout":' not in dumped


def test_coding_workflow_debugger_repairs_missing_read_with_allowed_directory_probe():
    safe_write_file("notes/debugger/info.txt", "debugger visible")

    result = run_coding_workflow(
        "请读取 notes/debugger/missing.txt，如果不存在就列出 notes/debugger 目录结构",
        workspace_action_name="workspace.read",
        workspace_action_input={
            "rel_path": "notes/debugger/missing.txt",
        },
    )
    payload = result.as_dict()
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is True
    assert result.error is None
    assert result.action_result is not None
    assert result.action_result["action_name"] == "workspace.list"
    assert result.action_result["metadata"]["debugger_plan"]["revised_action_name"] == "workspace.list"
    assert result.action_result["metadata"]["repair_count"] == 1
    assert trace_nodes == [
        CODING_START_NODE,
        PM_NODE,
        CODER_NODE,
        EXECUTOR_NODE,
        QA_NODE,
        DEBUGGER_NODE,
        EXECUTOR_NODE,
        CODING_FINISH_NODE,
    ]
    assert "notes/debugger/info.txt" in result.output
    assert "raw_error_ref" not in payload["coding_state"]["engineering"]
    assert "error_summary" not in payload["coding_state"]["engineering"]


def test_coding_workflow_debugger_stops_at_max_debug_steps():
    result = run_coding_workflow(
        "请读取 notes/debugger/no-repair.txt，如果不存在就列出 notes/debugger 目录结构",
        workspace_action_name="workspace.read",
        workspace_action_input={
            "rel_path": "notes/debugger/no-repair.txt",
        },
        max_debug_steps=0,
    )
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is False
    assert result.stop_reason == "max_debug_steps"
    assert DEBUGGER_NODE in trace_nodes
    assert EXECUTOR_NODE in trace_nodes


def test_coding_workflow_empty_prompt_routes_to_failure_result():
    result = run_coding_workflow("")
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is False
    assert result.error == "coding workflow requires non-empty user_input"
    assert result.ui_status == "coding_workflow_failed"
    assert result.stop_reason == "failed"
    assert trace_nodes == [CODING_START_NODE, CODING_FAILURE_NODE]


def test_coding_workflow_failure_state_records_exception_without_raw_payload():
    state = build_coding_workflow_node_failure_state(
        {
            "user_input": "请创建文件",
            "workflow_trace": [],
            "raw_error": "SECRET_RAW_ERROR",
            "stderr": "SECRET_STDERR",
        },
        node_name=PM_NODE,
        exc=RuntimeError("planner failed"),
    )
    result = CodingWorkflowResult.from_state(state)
    dumped = json.dumps(result.as_dict(), ensure_ascii=False)

    assert result.ok is False
    assert result.error == "planner failed"
    assert result.workflow_trace[-1]["node"] == PM_NODE
    assert "SECRET" not in dumped
