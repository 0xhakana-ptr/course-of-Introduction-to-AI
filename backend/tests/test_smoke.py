from backend.app.main import app


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
