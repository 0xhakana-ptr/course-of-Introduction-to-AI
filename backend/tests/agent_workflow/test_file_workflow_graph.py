import json

from backend.app.agent_workflow.graphs.file_graph import (
    FILE_EXECUTOR_NODE,
    FILE_FAILURE_NODE,
    FILE_FINISH_NODE,
    FILE_OBSERVER_NODE,
    FILE_START_NODE,
    run_file_workflow,
)
from backend.app.agent_workflow.graphs.file_result import FileWorkflowResult
from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import read_workspace_text


def test_file_workflow_executes_workspace_write_action():
    result = run_file_workflow(
        "请创建 notes/file-workflow.txt，内容是 hello file workflow",
        file_action_name="workspace.write",
        file_action_input={
            "rel_path": "notes/file-workflow.txt",
            "content": "hello file workflow",
        },
        session_id="session_1",
        turn_id="turn_1",
    )
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is True
    assert result.error is None
    assert result.ui_status == "file_workflow_completed"
    assert result.stop_reason == "completed"
    assert result.action_result is not None
    assert result.action_result["action_name"] == "workspace.write"
    assert result.file_state["last_created_file"] == "notes/file-workflow.txt"
    assert result.file_state["last_written_file"] == "notes/file-workflow.txt"
    assert trace_nodes == [
        FILE_START_NODE,
        FILE_EXECUTOR_NODE,
        FILE_OBSERVER_NODE,
        FILE_FINISH_NODE,
    ]
    assert read_workspace_text("notes/file-workflow.txt")["content"] == "hello file workflow"


def test_file_workflow_tracks_search_results():
    safe_write_file("notes/file-search/a.txt", "hello search")
    safe_write_file("notes/file-search/b.txt", "other")

    result = run_file_workflow(
        "请搜索 notes/file-search 下包含 hello 的文件",
        file_action_name="workspace.search",
        file_action_input={
            "rel_path": "notes/file-search",
            "query": "hello",
        },
    )

    assert result.ok is True
    assert result.action_result is not None
    assert result.action_result["action_name"] == "workspace.search"
    assert result.file_state["last_file_action"] == "workspace.search"
    assert result.file_state["last_search_results"] == [
        {
            "path": "notes/file-search/a.txt",
            "line_number": 1,
            "preview": "hello search",
            "truncated": False,
        }
    ]


def test_file_workflow_rejects_unsupported_action():
    result = run_file_workflow(
        "run command",
        file_action_name="run.create",
        file_action_input={"prompt": "demo"},
    )
    trace_nodes = [item["node"] for item in result.workflow_trace]

    assert result.ok is False
    assert result.ui_status == "file_workflow_failed"
    assert "unsupported file action" in str(result.error)
    assert trace_nodes == [FILE_START_NODE, FILE_FAILURE_NODE]


def test_file_workflow_result_is_json_serializable_and_sanitized():
    result = FileWorkflowResult.from_state(
        {
            "output": "done",
            "action_result": {
                "ok": True,
                "stdout": "raw stdout",
                "data": {"path": "notes/a.txt"},
            },
            "workflow_trace": [],
            "raw_error": "raw error",
            "file_state": {"last_read_file": "notes/a.txt"},
        }
    )

    dumped = json.dumps(result.as_dict(), ensure_ascii=False)

    assert result.ok is True
    assert "stdout" not in dumped
    assert "raw_error" not in dumped
    assert "last_read_file" in dumped
