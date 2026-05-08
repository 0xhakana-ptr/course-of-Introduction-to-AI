from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.run_interface import create_run, execute_run


def test_run_dependency_not_found_uses_standard_error_shape(client):
    response = client.get("/runs/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert payload["ok"] is False
    assert payload["detail"] == "run not found"
    assert payload["error"]["code"] == "run_not_found"
    assert payload["error"]["message"] == "run not found"
    assert payload["error"]["path"] == "/runs/not-found"


def test_run_conflict_uses_standard_error_shape(client):
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "done"

    response = client.post(f"/runs/{run.run_id}/cancel")

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert "does not support cancel" in payload["detail"]
    assert payload["error"]["code"] == "run_cannot_cancel"
    assert payload["error"]["path"] == f"/runs/{run.run_id}/cancel"


def test_validation_error_uses_standard_error_shape(client):
    response = client.post("/chat", json={"prompt": "", "context": None})

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["detail"] == "请求参数校验失败。"
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["path"] == "/chat"
    assert isinstance(payload["error"]["details"], list)
    assert payload["error"]["details"]


def test_unexpected_error_uses_standard_error_shape(client, monkeypatch):
    async def broken_generate_chat_response(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "backend.app.api.chat_routes.generate_chat_response",
        broken_generate_chat_response,
    )

    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.post("/chat", json={"prompt": "hello", "context": None})

    assert response.status_code == 500
    payload = response.json()
    assert payload["ok"] is False
    assert payload["detail"] == "服务器内部错误。"
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "服务器内部错误。"
    assert payload["error"]["path"] == "/chat"
