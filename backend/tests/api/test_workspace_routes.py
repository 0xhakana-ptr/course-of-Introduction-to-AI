from backend.app.core.config import settings
from backend.app.tools.safe_fs import get_effective_workspace_dir
from backend.app.tools.workspace_tools import read_workspace_text


def test_workspace_route_reports_effective_workspace(client):
    response = client.get("/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == str(get_effective_workspace_dir())
    assert payload["exists"] is True
    assert payload["is_default"] is True


def test_workspace_route_updates_file_tool_workspace(client, tmp_path):
    selected_workspace = tmp_path / "selected-workspace"
    selected_workspace.mkdir()

    response = client.put("/workspace", json={"path": str(selected_workspace)})

    assert response.status_code == 200
    assert response.json() == {"path": str(selected_workspace.resolve()), "updated": True}
    assert settings.workspace_dir == selected_workspace.resolve()
    assert settings.runs_dir == selected_workspace.resolve() / "runs"
    assert settings.accessible_project_root is None

    chat_response = client.post(
        "/chat",
        json={"prompt": "请创建 notes/from-selected.txt，内容是selected ok", "context": None},
    )

    assert chat_response.status_code == 200
    assert chat_response.json()["ok"] is True
    assert read_workspace_text("notes/from-selected.txt")["content"] == "selected ok"
    assert (selected_workspace / "notes" / "from-selected.txt").read_text(
        encoding="utf-8"
    ) == "selected ok"


def test_workspace_route_rejects_missing_directory(client, tmp_path):
    missing = tmp_path / "missing"

    response = client.put("/workspace", json={"path": str(missing)})

    assert response.status_code == 400


def test_workspace_route_uses_selected_workspace_even_when_project_root_was_configured(
    client,
    monkeypatch,
    tmp_path,
):
    configured_project_root = tmp_path / "project-root"
    configured_project_root.mkdir()
    selected_workspace = tmp_path / "selected-workspace"
    selected_workspace.mkdir()
    monkeypatch.setattr(settings, "accessible_project_root", configured_project_root)

    response = client.put("/workspace", json={"path": str(selected_workspace)})

    assert response.status_code == 200
    assert get_effective_workspace_dir() == selected_workspace.resolve()
    assert not (configured_project_root / "notes").exists()
