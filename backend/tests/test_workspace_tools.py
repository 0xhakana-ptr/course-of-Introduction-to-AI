from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import (
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_TEST,
    build_workspace_tool_context,
    build_workspace_overview,
    execute_workspace_tool_plan,
    get_workspace_tool_definition,
    list_workspace_entries,
    list_workspace_tool_names,
    plan_workspace_tool,
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


def test_workspace_tool_planning_can_select_file_preview():
    safe_write_file("backend/app/demo.txt", "demo content")

    plan = plan_workspace_tool("请修复 backend/app/demo.txt 里的问题")
    result = execute_workspace_tool_plan(plan)
    context = build_workspace_tool_context(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_READ
    assert plan["tool_input"] == {"rel_path": "backend/app/demo.txt"}
    assert result["ok"] is True
    assert result["tool_input"] == {"rel_path": "backend/app/demo.txt"}
    assert context is not None
    assert "Workspace file preview (backend/app/demo.txt)" in context
    assert "demo content" in context


def test_workspace_tool_planning_can_select_pytest_tool():
    safe_write_file(
        "backend/tests/test_demo_pass.py",
        "def test_demo_pass():\n"
        "    assert True\n",
    )

    plan = plan_workspace_tool("请先运行 backend/tests/test_demo_pass.py 的测试")
    result = execute_workspace_tool_plan(plan)
    context = build_workspace_tool_context(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_TEST
    assert plan["tool_input"] == {"test_paths": ["backend/tests/test_demo_pass.py"]}
    assert result["ok"] is True
    assert result["tool_input"] == {"test_paths": ["backend/tests/test_demo_pass.py"]}
    assert context is not None
    assert "Workspace pytest result:" in context


def test_workspace_tool_planning_falls_back_to_workspace_overview():
    plan = plan_workspace_tool("帮我写一个新的 python 脚本")

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_OVERVIEW
    assert plan["tool_input"] == {"rel_path": "."}


def test_workspace_tool_registry_can_resolve_registered_tools():
    names = list_workspace_tool_names()
    read_tool = get_workspace_tool_definition(WORKSPACE_TOOL_NAME_READ)

    assert WORKSPACE_TOOL_NAME_OVERVIEW in names
    assert WORKSPACE_TOOL_NAME_READ in names
    assert WORKSPACE_TOOL_NAME_TEST in names
    assert read_tool is not None
    assert read_tool.name == WORKSPACE_TOOL_NAME_READ


def test_workspace_tool_execution_reports_unregistered_tool():
    result = execute_workspace_tool_plan(
        {
            "tool_name": "missing_tool",
            "tool_input": {"rel_path": "."},
            "reason": "invalid test case",
        }
    )

    assert result["ok"] is False
    assert result["tool_input"] == {"rel_path": "."}
    assert "not registered" in str(result["summary"])
