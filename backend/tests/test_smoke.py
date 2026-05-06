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


def test_chat_test_command_keeps_response_contract(client):
    response = client.post("/chat", json={"prompt": "/test chat smoke", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "chat"
    assert payload["ok"] is True
    assert "测试成功" in payload["output"]

    queue_response = client.get("/messages")
    assert queue_response.status_code == 200
    queue_payload = queue_response.json()
    assert queue_payload["ok"] is True
    assert queue_payload["count"] >= 1
