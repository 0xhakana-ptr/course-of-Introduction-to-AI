from backend.app.main import app
from backend.app.services.run_interface import create_run


def test_main_module_imports():
    assert app.title == "AI Chat Backend"


def test_health_route_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "backend"
    assert "startup_recovery" in payload


def test_llm_diagnostics_without_remote_check(client):
    response = client.get("/llm/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["checked_remote"] is False
    assert payload["request_ok"] is None


def test_chat_route_gracefully_degrades_without_llm(client):
    response = client.post("/chat", json={"prompt": "hello", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "chat"
    assert payload["ok"] is False
    assert "LLM_BASE_URL" in payload["output"]
    assert payload["session_id"]


def test_chat_test_command_keeps_response_contract(client):
    response = client.post("/chat", json={"prompt": "/test chat smoke", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "chat"
    assert payload["ok"] is True
    assert "测试成功" in payload["output"]
    assert payload["session_id"]

    queue_response = client.get("/messages")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    assert queue_payload["ok"] is True
    assert queue_payload["count"] >= 1
    assert queue_payload["messages"][0]["type"] == "chat"
    assert queue_payload["messages"][0]["_channel"] == "agent:chat"


def test_agent_diagnostics_smoke_contract_without_llm(client):
    preview_response = client.post(
        "/agent/diagnostics/preview",
        json={"prompt": "hello", "context": None},
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["ok"] is True
    assert preview_payload["intent"] == "chat"
    assert preview_payload["diagnostics_mode"] == "loop"
    assert preview_payload["route_scope"] == "primary_loop"
    assert preview_payload["selected_route"] == "agent_loop"
    assert preview_payload["action_name"] == "chat.reply"
    assert preview_payload["runtime_event_summary"]["event_count"] >= 2
    assert preview_payload["workflow_trace"][0]["node"] == "plan_node"

    run_response = client.post(
        "/agent/diagnostics/run",
        json={"prompt": "???", "context": None},
    )

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["ok"] is True
    assert run_payload["intent"] == "unknown"
    assert run_payload["diagnostics_mode"] == "loop"
    assert run_payload["route_scope"] == "primary_loop"
    assert run_payload["selected_route"] == "agent_loop"
    assert run_payload["action_name"] == "final.answer"
    assert run_payload["executable"] is True
    assert run_payload["executed"] is True
    assert [item["node"] for item in run_payload["workflow_trace"]] == [
        "plan_node",
        "plan_node",
        "act_node",
        "observe_node",
        "decide_continue_node",
        "finalize_node",
        "roleplay_node",
    ]
    assert run_payload["runtime_event_summary"]["last_event_type"] == "roleplay.emitted"


def test_chat_coding_branch_keeps_response_contract(client):
    response = client.post("/chat", json={"prompt": "write python code", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "coding"
    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["output"], str)
    assert payload["session_id"]
    assert payload["run_id"]

    run_response = client.get(f"/runs/{payload['run_id']}")
    assert run_response.status_code == 200
    assert run_response.json()["status"] in {"queued", "running", "done", "failed", "cancelled"}


def test_chat_can_inspect_existing_run_snapshot(client):
    create_response = client.post(
        "/chat",
        json={"prompt": "write python code", "context": None},
    )
    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]
    assert run_id

    inspect_response = client.post(
        "/chat",
        json={"prompt": f"请查看 run_id {run_id} 的状态", "context": None},
    )
    assert inspect_response.status_code == 200
    inspect_payload = inspect_response.json()
    assert inspect_payload["intent"] == "coding"
    assert inspect_payload["ok"] is True
    assert inspect_payload["run_id"] == run_id
    assert (
        "目前我看到：" in inspect_payload["output"]
        or "摘要:" in inspect_payload["output"]
        or "最终总结：" in inspect_payload["output"]
    )
    assert "接下来：" in inspect_payload["output"] or "需要看细节时" in inspect_payload["output"]


def test_chat_can_cancel_existing_run(client):
    run = create_run("write python code", None)
    run_id = run.run_id
    assert run_id

    cancel_response = client.post(
        "/chat",
        json={"prompt": f"请确认取消 run_id {run_id}", "context": None},
    )
    assert cancel_response.status_code == 200
    cancel_payload = cancel_response.json()
    assert cancel_payload["intent"] == "coding"
    assert cancel_payload["run_id"] == run_id
    assert "取消请求" in cancel_payload["output"]

    run_response = client.get(f"/runs/{run_id}")
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "cancelled"
