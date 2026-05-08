def test_agent_diagnostics_preview_route_returns_coding_plan(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.agent_workflow.agent_support.plan_workspace_tool",
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
    assert len(payload["workflow_trace"]) >= 3
    assert payload["workflow_trace"][0]["node"] == "router"
    assert payload["workflow_trace"][1]["node"] == "coding_node"

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
