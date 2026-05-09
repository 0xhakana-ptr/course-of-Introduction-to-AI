from backend.app.services.run_interface import create_run


def test_agent_diagnostics_preview_route_returns_coding_plan(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.agent_workflow.agent_builder_support.plan_workspace_tool",
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
    assert payload["error_context"] is None
    assert len(payload["workflow_trace"]) >= 3
    assert payload["workflow_trace"][0]["node"] == "router"
    assert payload["workflow_trace"][0]["node_label"] == "意图路由"
    assert payload["workflow_trace"][0]["phase"] == "routing"
    assert payload["workflow_trace"][0]["event_label"] == "意图已路由"
    assert payload["workflow_trace"][0]["status_level"] == "info"
    assert "coding" in payload["workflow_trace"][0]["message"]
    assert payload["workflow_trace"][1]["node"] == "coding_node"
    assert payload["workflow_trace"][1]["node_label"] == "代码任务预处理"
    assert payload["workflow_trace"][1]["event_label"] == "代码任务请求已解析"
    assert payload["workflow_trace"][1]["status_level"] == "info"

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
        "backend.app.agent_workflow.agent_graph.call_llm_sync",
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
    assert payload["error_context"] is None
    assert [item["node"] for item in payload["workflow_trace"]] == [
        "router",
        "chat_node",
        "roleplay_node",
    ]
    assert payload["workflow_trace"][1]["event_label"] == "聊天回复完成"
    assert payload["workflow_trace"][1]["status_level"] == "info"
    assert "LLM 回复生成" in payload["workflow_trace"][1]["message"]
    assert payload["workflow_trace"][2]["event_label"] == "角色收口已发送"


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
        "backend.app.agent_workflow.agent_graph.call_llm_sync",
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
    assert payload["workflow_trace"][1]["event_label"] == "聊天回复失败"
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
        "backend.app.agent_workflow.agent_graph.call_llm_sync",
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
    assert payload["workflow_trace"][1]["event_label"] == "节点异常"
    assert payload["workflow_trace"][1]["status_level"] == "error"
    assert "未捕获异常" in payload["workflow_trace"][1]["message"]
    assert payload["error_context"]["summary"] == "工作流节点抛出了未捕获异常。"
    assert payload["error_context"]["error_code"] == "WORKFLOW_NODE_EXCEPTION"
    assert payload["error_context"]["failure_domain"] == "workflow_node"
    assert payload["error_context"]["failure_node"] == "chat_node"
    assert payload["error_context"]["failure_node_label"] == "聊天回复"
    assert payload["error_context"]["failure_event"] == "node_exception"
    assert payload["error_context"]["failure_phase"] == "chat"
