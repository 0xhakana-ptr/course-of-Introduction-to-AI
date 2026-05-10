from backend.app.agent_workflow.diagnostics.failure import build_failure_descriptor
from backend.app.agent_workflow.diagnostics.support import (
    WorkspaceToolSnapshot,
    build_workspace_tool_response_kwargs,
)
from backend.app.services.run_interface import create_run


def test_agent_diagnostics_preview_route_returns_coding_plan(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.builder_support.plan_workspace_tool",
        lambda prompt: {
            "tool_name": "read_workspace_text",
            "tool_input": {"rel_path": "backend/app/main.py"},
            "reason": "Prompt references a workspace file path.",
        },
    )

    response = client.post(
        "/agent/diagnostics/preview",
        json={"prompt": "please read backend/app/main.py", "context": "ctx"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["selected_route"] == "coding_node"
    assert payload["run_action"] == "create"
    assert payload["workspace_tool_name"] == "read_workspace_text"
    assert payload["workspace_tool_category"] == "context"
    assert payload["workspace_tool_output_kind"] == "file_preview"
    assert payload["workspace_tool_error_code"] is None
    assert payload["workspace_tool_descriptor"]["name"] == "read_workspace_text"
    assert payload["workspace_tool_plan"]["tool_input"] == {"rel_path": "backend/app/main.py"}
    assert payload["workspace_tool"]["name"] == "read_workspace_text"
    assert payload["workspace_tool"]["title"] == "读取工作区文本"
    assert payload["workspace_tool"]["descriptor"]["category"] == "context"
    assert payload["workspace_tool"]["plan"]["tool_name"] == "read_workspace_text"
    assert payload["planned_nodes"] == [
        "router",
        "coding_node",
        "workspace_tool_node",
        "run_tool_node",
        "roleplay_node",
    ]
    assert payload["debug_summary"]["trace_count"] >= 3
    assert payload["debug_summary"]["first_node"] == "router"
    assert payload["debug_summary"]["first_node_label"] == "意图路由"
    assert payload["debug_summary"]["last_node"] == "diagnostics_preview"
    assert payload["debug_summary"]["last_phase"] == "diagnostics"
    assert payload["runtime_event_summary"]["event_count"] >= 3
    assert payload["runtime_event_summary"]["error_event_count"] == 0
    assert payload["runtime_event_summary"]["frontend_visible_count"] == 0
    assert payload["runtime_event_summary"]["event_source_counts"]["workflow"] >= 2
    assert payload["runtime_event_summary"]["last_event_source"] == "diagnostics"
    assert payload["runtime_event_summary"]["last_event_stage"] == "diagnostics"
    assert payload["error_context"] is None
    assert len(payload["workflow_trace"]) >= 3
    assert payload["workflow_trace"][0]["node"] == "router"
    assert payload["workflow_trace"][0]["node_label"] == "意图路由"
    assert payload["workflow_trace"][0]["phase"] == "routing"
    assert payload["workflow_trace"][0]["event_label"] == "意图已路由"
    assert payload["workflow_trace"][0]["event_type"] == "workflow.intent_routed"
    assert payload["workflow_trace"][0]["event_source"] == "workflow"
    assert payload["workflow_trace"][0]["event_stage"] == "routing"
    assert payload["workflow_trace"][0]["frontend_visible"] is False
    assert payload["workflow_trace"][0]["status_level"] == "info"
    assert "coding" in payload["workflow_trace"][0]["message"]
    assert payload["workflow_trace"][1]["node"] == "coding_node"
    assert payload["workflow_trace"][1]["node_label"] == "代码任务预处理"
    assert payload["workflow_trace"][1]["event_label"] == "代码任务请求已解析"
    assert payload["workflow_trace"][1]["event_type"] == "workflow.coding_prepared"
    assert payload["workflow_trace"][1]["event_source"] == "workflow"
    assert payload["workflow_trace"][1]["event_stage"] == "coding"
    assert payload["workflow_trace"][1]["status_level"] == "info"
    assert "规划工作区工具" in payload["workflow_trace"][1]["message"]
    assert "读取工作区文本" in payload["workflow_trace"][1]["message"]

    runs_response = client.get("/runs")
    assert runs_response.status_code == 200
    assert runs_response.json() == []


def test_agent_diagnostics_preview_route_returns_run_control_plan(client):
    run_id = "123e4567-e89b-12d3-a456-426614174000"

    response = client.post(
        "/agent/diagnostics/preview",
        json={"prompt": f"请取消 run_id {run_id}", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["selected_route"] == "coding_node"
    assert payload["run_action"] == "cancel"
    assert payload["target_run_id"] == run_id
    assert payload["workspace_tool_plan"] is None
    assert payload["planned_nodes"] == [
        "router",
        "coding_node",
        "run_control_node",
        "roleplay_node",
    ]
    assert "控制动作" in payload["notes"][0]


def test_agent_diagnostics_run_route_executes_chat_branch(monkeypatch, client):
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

    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "hello", "context": "ctx"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["executable"] is True
    assert payload["executed"] is True
    assert payload["selected_route"] == "chat_node"
    assert payload["output"] == "reply to hello"
    assert payload["debug_summary"]["blocked"] is False
    assert payload["debug_summary"]["error_present"] is False
    assert payload["runtime_event_summary"]["event_count"] == 3
    assert payload["runtime_event_summary"]["event_source_counts"]["chat"] == 1
    assert payload["runtime_event_summary"]["event_source_counts"]["roleplay"] == 1
    assert payload["runtime_event_summary"]["event_stage_counts"]["chat"] == 1
    assert payload["runtime_event_summary"]["last_event_type"] == "roleplay.emitted"
    assert payload["error_context"] is None
    assert [item["node"] for item in payload["workflow_trace"]] == [
        "router",
        "chat_node",
        "roleplay_node",
    ]
    assert payload["workflow_trace"][1]["event_label"] == "聊天回复完成"
    assert payload["workflow_trace"][1]["event_type"] == "chat.response_ready"
    assert payload["workflow_trace"][1]["event_source"] == "chat"
    assert payload["workflow_trace"][1]["event_stage"] == "chat"
    assert payload["workflow_trace"][1]["status_level"] == "info"
    assert "LLM 回复生成" in payload["workflow_trace"][1]["message"]
    assert payload["workflow_trace"][2]["event_label"] == "角色收口已发送"
    assert payload["workflow_trace"][2]["event_type"] == "roleplay.emitted"
    assert payload["workflow_trace"][2]["event_source"] == "roleplay"
    assert payload["workflow_trace"][2]["event_stage"] == "roleplay"


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


def test_agent_diagnostics_run_route_executes_inspect_branch(client):
    run = create_run("write python code", None)

    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": f"请查看 run_id {run.run_id} 的状态", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["executable"] is True
    assert payload["executed"] is True
    assert payload["selected_route"] == "coding_node"
    assert payload["run_action"] == "inspect"
    assert payload["run_id"] == run.run_id
    assert payload["output"]
    assert payload["workflow_trace"][1]["node"] == "coding_node"
    assert payload["workflow_trace"][-1]["node"] == "roleplay_node"


def test_agent_diagnostics_run_route_blocks_side_effecting_coding_paths(client):
    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "write python code", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["executable"] is False
    assert payload["executed"] is False
    assert payload["selected_route"] == "coding_node"
    assert payload["run_action"] == "create"
    assert payload["blocked_reason"]
    assert "preview" in payload["blocked_reason"]
    assert payload["debug_summary"]["blocked"] is True
    assert payload["debug_summary"]["failure_phase"] == "diagnostics"
    assert payload["debug_summary"]["failure_code"] == "DIAGNOSTICS_BLOCKED_SIDE_EFFECT"
    assert payload["debug_summary"]["failure_domain"] == "diagnostics_guard"
    assert payload["runtime_event_summary"]["event_count"] >= 3
    assert payload["runtime_event_summary"]["event_source_counts"]["diagnostics"] == 1
    assert payload["runtime_event_summary"]["last_event_type"] == "diagnostics.coding_path_selected"
    assert payload["workspace_tool"]["name"] == "build_workspace_overview"
    assert payload["workspace_tool"]["descriptor"]["title"] == "工作区概览"
    assert payload["workflow_trace"][-1]["event_label"] == "诊断 coding 路径已确定"
    assert payload["workflow_trace"][-1]["status_level"] == "info"
    assert "后续节点" in payload["workflow_trace"][-1]["message"]
    assert payload["error_context"]["error_type"] == "blocked"
    assert payload["error_context"]["summary"] == "诊断已拦截：当前输入会进入可能产生副作用的运行路径。"
    assert payload["error_context"]["message"] == payload["blocked_reason"]
    assert payload["error_context"]["error_code"] == "DIAGNOSTICS_BLOCKED_SIDE_EFFECT"
    assert payload["error_context"]["failure_domain"] == "diagnostics_guard"
    assert payload["error_context"]["failure_node_label"] == "诊断预览"
    assert payload["error_context"]["failure_phase"] == "diagnostics"
    assert "preview" in payload["error_context"]["suggested_next_step"]


def test_agent_diagnostics_run_route_returns_error_context_for_chat_failure(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": False,
                "output": "调用失败",
                "error": "llm boom",
            },
        )(),
    )

    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "hello", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["executed"] is True
    assert payload["error"] == "llm boom"
    assert payload["debug_summary"]["error_present"] is True
    assert payload["debug_summary"]["failure_node"] == "chat_node"
    assert payload["debug_summary"]["failure_node_label"] == "聊天回复"
    assert payload["debug_summary"]["failure_event"] == "llm_response_failed"
    assert payload["debug_summary"]["failure_phase"] == "chat"
    assert payload["debug_summary"]["failure_code"] == "CHAT_LLM_RESPONSE_FAILED"
    assert payload["debug_summary"]["failure_domain"] == "llm"
    assert payload["runtime_event_summary"]["error_event_count"] == 1
    assert payload["runtime_event_summary"]["event_type_counts"]["chat.response_failed"] == 1
    assert payload["workflow_trace"][1]["event_label"] == "聊天回复失败"
    assert payload["workflow_trace"][1]["event_type"] == "chat.response_failed"
    assert payload["workflow_trace"][1]["event_source"] == "chat"
    assert payload["workflow_trace"][1]["event_stage"] == "chat"
    assert payload["workflow_trace"][1]["status_level"] == "error"
    assert "失败结果" in payload["workflow_trace"][1]["message"]
    assert payload["error_context"]["error_type"] == "workflow_error"
    assert payload["error_context"]["summary"] == "聊天节点返回了失败结果。"
    assert payload["error_context"]["error_code"] == "CHAT_LLM_RESPONSE_FAILED"
    assert payload["error_context"]["failure_domain"] == "llm"
    assert payload["error_context"]["failure_node"] == "chat_node"
    assert payload["error_context"]["failure_node_label"] == "聊天回复"
    assert payload["error_context"]["failure_event"] == "llm_response_failed"
    assert payload["error_context"]["failure_phase"] == "chat"
    assert "LLM" in payload["error_context"]["suggested_next_step"]


def test_agent_diagnostics_run_route_returns_error_context_for_chat_exception(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.agent_workflow.graph.agent_graph.call_llm_sync",
        lambda prompt, context: (_ for _ in ()).throw(RuntimeError("llm raised boom")),
    )

    response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "hello", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["executed"] is True
    assert payload["error"] == "llm raised boom"
    assert payload["debug_summary"]["failure_node"] == "chat_node"
    assert payload["debug_summary"]["failure_event"] == "node_exception"
    assert payload["debug_summary"]["failure_phase"] == "chat"
    assert payload["debug_summary"]["failure_code"] == "WORKFLOW_NODE_EXCEPTION"
    assert payload["debug_summary"]["failure_domain"] == "workflow_node"
    assert payload["runtime_event_summary"]["error_event_count"] == 1
    assert payload["runtime_event_summary"]["event_type_counts"]["workflow.node_exception"] == 1
    assert payload["workflow_trace"][1]["event_label"] == "节点异常"
    assert payload["workflow_trace"][1]["event_type"] == "workflow.node_exception"
    assert payload["workflow_trace"][1]["event_source"] == "chat"
    assert payload["workflow_trace"][1]["event_stage"] == "chat"
    assert payload["workflow_trace"][1]["status_level"] == "error"
    assert "未捕获异常" in payload["workflow_trace"][1]["message"]
    assert payload["error_context"]["summary"] == "工作流节点抛出了未捕获异常。"
    assert payload["error_context"]["error_code"] == "WORKFLOW_NODE_EXCEPTION"
    assert payload["error_context"]["failure_domain"] == "workflow_node"
    assert payload["error_context"]["failure_node"] == "chat_node"
    assert payload["error_context"]["failure_node_label"] == "聊天回复"
    assert payload["error_context"]["failure_event"] == "node_exception"
    assert payload["error_context"]["failure_phase"] == "chat"
