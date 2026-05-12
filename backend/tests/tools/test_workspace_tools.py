import pytest
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.schemas import WorkspaceToolDescriptorInfo, WorkspaceToolInfo
from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import (
    WORKSPACE_TOOL_NAME_LIST,
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_TEST,
    WORKSPACE_TOOL_NAME_WRITE,
    WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW,
    WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE,
    WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW,
    WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
    WORKSPACE_TOOL_ERROR_TARGET_DISABLED,
    WORKSPACE_TOOL_ERROR_UNREGISTERED,
    build_workspace_tool_context,
    build_workspace_tool_user_output,
    build_workspace_overview,
    execute_workspace_tool_plan,
    get_workspace_tool_descriptor,
    get_workspace_tool_definition,
    list_workspace_tool_descriptors,
    list_workspace_entries,
    list_workspace_tool_names,
    normalize_workspace_tool_plan,
    normalize_workspace_tool_result,
    plan_workspace_tool,
    read_workspace_text,
    run_workspace_tests,
    summarize_command_failure,
    write_workspace_text,
)
from backend.app.tools.workspace_tool_models import WorkspaceToolPlan


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
    user_output = build_workspace_tool_user_output(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_READ
    assert plan["tool_input"] == {"rel_path": "backend/app/demo.txt"}
    assert plan.get("terminal") is not True
    assert result["ok"] is True
    assert result["tool_input"] == {"rel_path": "backend/app/demo.txt"}
    assert result["tool_category"] == "context"
    assert result["tool_output_kind"] == WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW
    assert result["tool_error_code"] is None
    assert context is not None
    assert "Workspace file preview (backend/app/demo.txt)" in context
    assert "demo content" in context
    assert user_output is not None
    assert "我读到了 `backend/app/demo.txt` 的内容" in user_output
    assert "demo content" in user_output


def test_workspace_tool_planning_marks_pure_file_preview_terminal():
    safe_write_file("backend/app/demo.txt", "demo content")

    plan = plan_workspace_tool("请读取 backend/app/demo.txt")

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_READ
    assert plan["tool_input"] == {"rel_path": "backend/app/demo.txt"}
    assert plan["terminal"] is True


def test_workspace_tool_planning_marks_pure_listing_terminal():
    safe_write_file("demo/nested/info.txt", "nested data")

    plan = plan_workspace_tool("请列出 demo/nested 目录结构")
    result = execute_workspace_tool_plan(plan)
    user_output = build_workspace_tool_user_output(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_LIST
    assert plan["tool_input"] == {
        "rel_path": "demo/nested",
        "recursive": False,
        "max_entries": 12,
    }
    assert plan["terminal"] is True
    assert user_output is not None
    assert "我列出了 `demo/nested` 下的内容" in user_output
    assert "文件: demo/nested/info.txt" in user_output


def test_workspace_tool_planning_keeps_codegen_listing_nonterminal():
    safe_write_file("demo/nested/info.txt", "nested data")

    plan = plan_workspace_tool("请根据 demo/nested 目录结构实现一个功能")

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_LIST
    assert plan.get("terminal") is not True


def test_workspace_tool_planning_can_select_pytest_tool():
    safe_write_file(
        "backend/tests/test_demo_pass.py",
        "def test_demo_pass():\n"
        "    assert True\n",
    )

    plan = plan_workspace_tool("请先运行 backend/tests/test_demo_pass.py 的测试")
    result = execute_workspace_tool_plan(plan)
    context = build_workspace_tool_context(result)
    user_output = build_workspace_tool_user_output(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_TEST
    assert plan["tool_input"] == {"test_paths": ["backend/tests/test_demo_pass.py"]}
    assert plan["terminal"] is True
    assert result["ok"] is True
    assert result["tool_input"] == {"test_paths": ["backend/tests/test_demo_pass.py"]}
    assert context is not None
    assert "Workspace pytest result:" in context
    assert user_output is not None
    assert "我运行完测试了" in user_output
    assert "结果: 通过" in user_output


def test_workspace_tool_planning_keeps_codegen_pytest_nonterminal():
    safe_write_file(
        "backend/tests/test_demo_pass.py",
        "def test_demo_pass():\n"
        "    assert True\n",
    )

    plan = plan_workspace_tool("请运行 backend/tests/test_demo_pass.py 的测试并修复失败")

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_TEST
    assert plan["tool_input"] == {"test_paths": ["backend/tests/test_demo_pass.py"]}
    assert plan.get("terminal") is not True


def test_workspace_tools_can_write_text_inside_workspace():
    result = write_workspace_text("notes/demo.txt", "hello workspace")
    preview = read_workspace_text("notes/demo.txt")

    assert result["path"] == "notes/demo.txt"
    assert result["created"] is True
    assert result["overwritten"] is False
    assert result["chars_written"] == len("hello workspace")
    assert preview["content"] == "hello workspace"


def test_workspace_tool_planning_can_select_workspace_write_tool():
    plan = plan_workspace_tool("请创建 notes/todo.txt，内容是buy milk")
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["terminal"] is True
    assert plan["tool_input"] == {
        "rel_path": "notes/todo.txt",
        "content": "buy milk",
        "overwrite": False,
        "target_location": "workspace",
    }
    assert result["ok"] is True
    assert result["tool_category"] == "execution"
    assert result["tool_output_kind"] == WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE
    assert result["tool_error_code"] is None
    assert "已在 workspace 中创建文本文件" in result["summary"]
    assert read_workspace_text("notes/todo.txt")["content"] == "buy milk"


def test_workspace_tool_planning_writes_non_txt_text_path():
    plan = plan_workspace_tool("请创建 notes/todo.md，内容是# Todo")
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["tool_input"] == {
        "rel_path": "notes/todo.md",
        "content": "# Todo",
        "overwrite": False,
        "target_location": "workspace",
    }
    assert result["ok"] is True
    assert read_workspace_text("notes/todo.md")["content"] == "# Todo"


def test_workspace_tool_planning_trims_followup_from_written_content():
    plan = plan_workspace_tool("请创建 notes/followup.txt，内容是hello，然后读出来确认")
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["tool_input"]["content"] == "hello"
    assert result["ok"] is True
    assert read_workspace_text("notes/followup.txt")["content"] == "hello"


def test_workspace_tool_planning_supports_quoted_chinese_space_path():
    plan = plan_workspace_tool("请创建 `notes/中文 文件.txt`，内容是你好")
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["tool_input"] == {
        "rel_path": "notes/中文 文件.txt",
        "content": "你好",
        "overwrite": False,
        "target_location": "workspace",
    }
    assert result["ok"] is True
    assert read_workspace_text("notes/中文 文件.txt")["content"] == "你好"


def test_workspace_tool_planning_can_read_quoted_chinese_space_path():
    safe_write_file("notes/中文 文件.txt", "你好")

    plan = plan_workspace_tool("请读取 `notes/中文 文件.txt`")
    result = execute_workspace_tool_plan(plan)
    user_output = build_workspace_tool_user_output(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_READ
    assert plan["tool_input"] == {"rel_path": "notes/中文 文件.txt"}
    assert plan["terminal"] is True
    assert result["ok"] is True
    assert user_output is not None
    assert "你好" in user_output


def test_workspace_tool_planning_reports_missing_read_path():
    plan = plan_workspace_tool("请读取 notes/missing.txt")
    result = execute_workspace_tool_plan(plan)
    user_output = build_workspace_tool_user_output(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_READ
    assert plan["tool_input"] == {"rel_path": "notes/missing.txt"}
    assert result["ok"] is False
    assert result["tool_error_code"] == WORKSPACE_TOOL_ERROR_EXECUTION_FAILED
    assert user_output is not None
    assert "没有找到 workspace 路径 `notes/missing.txt`" in user_output


def test_workspace_tool_planning_reports_missing_list_path():
    plan = plan_workspace_tool("请列出 notes/missing-dir 目录结构")
    result = execute_workspace_tool_plan(plan)
    user_output = build_workspace_tool_user_output(result)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_LIST
    assert plan["tool_input"]["rel_path"] == "notes/missing-dir"
    assert result["ok"] is True
    assert result["data"]["exists"] is False
    assert user_output is not None
    assert "没有找到 workspace 路径 `notes/missing-dir`" in user_output


def test_workspace_tool_rejects_desktop_write_target():
    plan = plan_workspace_tool("帮我在桌面创建一个txt文件")
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["terminal"] is True
    assert plan["tool_input"]["target_location"] == "desktop"
    assert result["ok"] is False
    assert result["tool_error_code"] == WORKSPACE_TOOL_ERROR_TARGET_DISABLED
    assert "桌面导出功能没有开启" in result["summary"]


def test_workspace_tool_can_export_text_to_configured_desktop_dir(monkeypatch, tmp_path):
    export_dir = tmp_path / "desktop-exports"
    monkeypatch.setattr(settings, "desktop_export_enabled", True)
    monkeypatch.setattr(settings, "desktop_export_dir", export_dir)

    plan = plan_workspace_tool("帮我在桌面创建 `notes/桌面 文件.txt`，内容是buy milk")
    result = execute_workspace_tool_plan(plan)
    exported_file = export_dir / "桌面 文件.txt"

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["terminal"] is True
    assert plan["tool_input"]["target_location"] == "desktop"
    assert result["ok"] is True
    assert result["tool_output_kind"] == WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE
    assert result["tool_error_code"] is None
    assert exported_file.read_text(encoding="utf-8") == "buy milk"
    assert str(exported_file) in result["summary"]


def test_workspace_tool_planning_falls_back_to_workspace_overview():
    plan = plan_workspace_tool("帮我写一个新的 python 脚本")

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_OVERVIEW
    assert plan["tool_input"] == {"rel_path": "."}
    assert plan.get("terminal") is not True


def test_workspace_tool_registry_can_resolve_registered_tools():
    names = list_workspace_tool_names()
    read_tool = get_workspace_tool_definition(WORKSPACE_TOOL_NAME_READ)
    read_descriptor = get_workspace_tool_descriptor(WORKSPACE_TOOL_NAME_READ)
    descriptors = list_workspace_tool_descriptors()

    assert WORKSPACE_TOOL_NAME_OVERVIEW in names
    assert WORKSPACE_TOOL_NAME_READ in names
    assert WORKSPACE_TOOL_NAME_TEST in names
    assert WORKSPACE_TOOL_NAME_WRITE in names
    assert read_tool is not None
    assert read_tool.name == WORKSPACE_TOOL_NAME_READ
    assert read_descriptor is not None
    assert read_descriptor["category"] == "context"
    assert read_descriptor["output_kind"] == WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW
    assert any(item["name"] == WORKSPACE_TOOL_NAME_OVERVIEW for item in descriptors)
    overview_descriptor = next(
        item for item in descriptors if item["name"] == WORKSPACE_TOOL_NAME_OVERVIEW
    )
    assert overview_descriptor["output_kind"] == WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW


def test_workspace_tool_descriptors_follow_public_schema():
    descriptors = list_workspace_tool_descriptors()

    assert descriptors
    for descriptor in descriptors:
        parsed = WorkspaceToolDescriptorInfo.model_validate(descriptor)
        assert parsed.name
        assert parsed.category in {"context", "execution"}
        assert parsed.output_kind in {
            "overview_text",
            "entry_listing",
            "file_preview",
            "command_result",
            "file_write",
        }

    with pytest.raises(ValidationError):
        WorkspaceToolDescriptorInfo.model_validate(
            {
                "name": "bad_tool",
                "title": "Bad",
                "description": "Invalid category should be rejected.",
                "category": "misc",
                "output_kind": "overview_text",
            }
        )


def test_workspace_tool_info_rejects_unknown_error_code():
    with pytest.raises(ValidationError):
        WorkspaceToolInfo.model_validate(
            {
                "name": "read_workspace_text",
                "category": "context",
                "output_kind": "file_preview",
                "error_code": "UNKNOWN_TOOL_ERROR",
            }
        )


def test_workspace_tool_helpers_normalize_plan_and_result_models():
    plan_model = normalize_workspace_tool_plan(
        {
            "tool_name": "read_workspace_text",
            "tool_input": {"rel_path": "backend/app/main.py"},
            "reason": "Prompt references a workspace file path.",
            "terminal": True,
        }
    )
    assert plan_model is not None
    assert plan_model.tool_name == "read_workspace_text"
    assert plan_model.tool_input == {"rel_path": "backend/app/main.py"}
    assert plan_model.terminal is True

    normalized_result = normalize_workspace_tool_result(
        {
            "tool_name": "read_workspace_text",
            "tool_input": {"rel_path": "backend/app/main.py"},
            "ok": True,
            "reason": "Prompt references a workspace file path.",
            "tool_category": "context",
            "tool_output_kind": "file_preview",
            "tool_descriptor": get_workspace_tool_descriptor("read_workspace_text"),
            "summary": "Workspace file preview (backend/app/main.py):\nhello",
        }
    )
    assert normalized_result.tool_name == "read_workspace_text"
    assert normalized_result.tool_input == {"rel_path": "backend/app/main.py"}
    assert normalized_result.tool_descriptor is not None
    assert normalized_result.tool_descriptor.name == "read_workspace_text"

    direct_plan = WorkspaceToolPlan(
        tool_name="build_workspace_overview",
        tool_input={"rel_path": "."},
        reason="Provide a compact workspace overview before creating the run.",
    )
    assert normalize_workspace_tool_plan(direct_plan) is direct_plan


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
    assert result["tool_error_code"] == WORKSPACE_TOOL_ERROR_UNREGISTERED
    assert result["tool_descriptor"] is None
    assert "not registered" in str(result["summary"])
