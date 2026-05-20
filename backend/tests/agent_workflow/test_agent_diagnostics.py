import importlib

from backend.app.agent_workflow.diagnostics.failure import build_failure_descriptor
from backend.app.agent_workflow.diagnostics.support import (
    WorkspaceToolSnapshot,
    build_workspace_tool_response_kwargs,
)


def test_agent_diagnostics_preview_defaults_to_loop_plan(client):
    response = client.post(
        "/agent/diagnostics/preview",
        json={"prompt": "请创建 notes/diag-loop.txt，内容是loop diagnostics", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["diagnostics_mode"] == "loop"
    assert payload["route_scope"] == "primary_loop"
    assert payload["selected_route"] == "agent_loop"
    assert payload["intent"] == "coding"
    assert payload["action_name"] == "workspace.write"
    assert payload["action_category"] == "workspace"
    assert payload["action_safety_level"] == "medium"
    assert payload["requires_confirmation"] is False
    assert payload["workspace_tool_name"] == "write_workspace_text"
    assert payload["workspace_tool_plan"]["tool_input"]["rel_path"] == "notes/diag-loop.txt"
    assert payload["planned_nodes"][:2] == ["plan_node", "plan_node"]
    assert payload["debug_summary"]["first_node"] == "plan_node"
    assert payload["debug_summary"]["last_node"] == "plan_node"
    assert payload["runtime_event_summary"]["event_count"] == 2
    assert any("Agent Loop 主路径" in note for note in payload["notes"])


def test_agent_diagnostics_run_defaults_to_loop_and_executes_chat(monkeypatch, client):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": f"loop diagnostics reply to {prompt}",
                "error": None,
            },
        )(),
    )

    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "hello loop diagnostics", "context": "ctx"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["diagnostics_mode"] == "loop"
    assert payload["route_scope"] == "primary_loop"
    assert payload["selected_route"] == "agent_loop"
    assert payload["action_name"] == "chat.reply"
    assert payload["executable"] is True
    assert payload["executed"] is True
    assert payload["output"] == "loop diagnostics reply to hello loop diagnostics"
    assert [item["node"] for item in payload["workflow_trace"]] == [
        "plan_node",
        "plan_node",
        "act_node",
        "observe_node",
        "decide_continue_node",
        "finalize_node",
        "roleplay_node",
    ]


def test_agent_diagnostics_run_blocks_loop_side_effecting_action(client):
    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "请创建 notes/blocked-loop.txt，内容是blocked", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["diagnostics_mode"] == "loop"
    assert payload["selected_route"] == "agent_loop"
    assert payload["action_name"] == "workspace.write"
    assert payload["executable"] is False
    assert payload["executed"] is False
    assert payload["blocked_reason"]
    assert "workspace.write" in payload["blocked_reason"]
    assert payload["debug_summary"]["blocked"] is True
    assert payload["error_context"]["error_type"] == "blocked"


def test_legacy_route_diagnostics_endpoints_are_removed(client):
    preview_response = client.post(
        "/agent/diagnostics/legacy-route/preview",
        json={"prompt": "hello", "context": None},
    )
    run_response = client.post(
        "/agent/diagnostics/legacy-route/run",
        json={"prompt": "hello", "context": None},
    )

    assert preview_response.status_code == 404
    assert run_response.status_code == 404


def test_workspace_tool_snapshot_can_merge_runtime_state_with_preview_state():
    preview_snapshot = WorkspaceToolSnapshot.from_state(
        {
            "workspace_tool_name": "read_workspace_text",
            "workspace_tool_reason": "Prompt references a workspace file path.",
            "workspace_tool_descriptor": {
                "name": "read_workspace_text",
                "title": "读取工作区文本",
                "description": "读取单个工作区文本文件并返回裁剪后的内容预览。",
                "category": "context",
                "output_kind": "file_preview",
                "input_keys": ["rel_path", "max_chars"],
            },
            "workspace_tool_plan": {
                "tool_name": "read_workspace_text",
                "tool_input": {"rel_path": "backend/app/main.py"},
                "reason": "Prompt references a workspace file path.",
            },
        }
    )
    runtime_snapshot = WorkspaceToolSnapshot.from_state(
        {
            "workspace_tool_name": "read_workspace_text",
            "workspace_tool_error_code": "WORKSPACE_TOOL_EXECUTION_FAILED",
        }
    ).merged_with(preview_snapshot)

    assert runtime_snapshot.name == "read_workspace_text"
    assert runtime_snapshot.title == "读取工作区文本"
    assert runtime_snapshot.category == "context"
    assert runtime_snapshot.output_kind == "file_preview"
    assert runtime_snapshot.error_code == "WORKSPACE_TOOL_EXECUTION_FAILED"
    assert runtime_snapshot.plan == {
        "tool_name": "read_workspace_text",
        "tool_input": {"rel_path": "backend/app/main.py"},
        "reason": "Prompt references a workspace file path.",
    }
    response_kwargs = build_workspace_tool_response_kwargs(runtime_snapshot)

    assert response_kwargs["workspace_tool_name"] == "read_workspace_text"
    assert response_kwargs["workspace_tool_category"] == "context"
    assert response_kwargs["workspace_tool_error_code"] == "WORKSPACE_TOOL_EXECUTION_FAILED"
    assert response_kwargs["workspace_tool_descriptor"].name == "read_workspace_text"
    assert response_kwargs["workspace_tool_plan"].tool_input == {
        "rel_path": "backend/app/main.py",
    }
    assert response_kwargs["workspace_tool"].title == "读取工作区文本"


def test_workspace_tool_failure_descriptor_prefers_specific_tool_error_code():
    descriptor = build_failure_descriptor(
        error_type="workflow_error",
        failure_event="workspace_tool_failed",
        failure_phase="tools",
        failure_details={
            "tool_name": "missing_tool",
            "tool_title": "缺失工具",
            "tool_error_code": "WORKSPACE_TOOL_UNREGISTERED",
        },
    )

    assert descriptor["error_code"] == "WORKSPACE_TOOL_UNREGISTERED"
    assert descriptor["failure_domain"] == "workspace_tool_registry"
    assert "缺失工具" in descriptor["summary"]
