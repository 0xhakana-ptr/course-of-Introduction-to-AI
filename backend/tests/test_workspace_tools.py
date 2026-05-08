from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import (
    build_workspace_overview,
    list_workspace_entries,
    read_workspace_text,
    run_workspace_tests,
    summarize_command_failure,
)


def test_workspace_tools_can_list_entries_and_read_text_preview():
    safe_write_file("demo/readme.txt", "hello world")
    safe_write_file("demo/nested/info.txt", "nested data")

    listing = list_workspace_entries("demo", recursive=True, max_entries=10)
    preview = read_workspace_text("demo/readme.txt", max_chars=5)

    assert listing["path"] == "demo"
    assert listing["recursive"] is True
    assert listing["total"] == 3
    assert listing["truncated"] is False
    assert listing["items"] == [
        {"path": "demo/nested", "kind": "dir"},
        {"path": "demo/nested/info.txt", "kind": "file"},
        {"path": "demo/readme.txt", "kind": "file"},
    ]
    assert preview["path"] == "demo/readme.txt"
    assert preview["content"] == "hello"
    assert preview["total_chars"] == 11
    assert preview["truncated"] is True


def test_workspace_tools_can_run_pytest_and_build_failure_summary():
    safe_write_file(
        "tests/test_demo_failure.py",
        "def test_demo_failure():\n"
        '    assert False, "boom"\n',
    )

    result = run_workspace_tests(["tests/test_demo_failure.py"], max_output_chars=500)
    summary = summarize_command_failure(result)

    assert result["ok"] is False
    assert result["target_paths"] == ["tests/test_demo_failure.py"]
    assert result["command"][1:3] == ["-m", "pytest"]
    assert result["stdout_length"] > 0
    assert "boom" in result["summary"]
    assert summary == result["summary"]


def test_workspace_tools_can_build_workspace_overview():
    safe_write_file("README.md", "project intro")
    safe_write_file("backend/README.md", "backend intro")
    safe_write_file("backend/requirements.txt", "fastapi\npytest\n")

    overview = build_workspace_overview()

    assert "Workspace top-level entries:" in overview
    assert "[dir] backend" in overview
    assert "README.md preview:" in overview
    assert "project intro" in overview
    assert "backend/README.md preview:" in overview
    assert "backend intro" in overview
