import pytest
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.schemas import WorkspaceToolDescriptorInfo, WorkspaceToolInfo
from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import (
    WORKSPACE_TOOL_NAME_COPY,
    WORKSPACE_TOOL_NAME_DELETE,
    WORKSPACE_TOOL_NAME_LIST,
    WORKSPACE_TOOL_NAME_MOVE,
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_SEARCH,
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
    copy_workspace_path,
    delete_workspace_path,
    execute_workspace_tool_plan,
    get_workspace_tool_descriptor,
    get_workspace_tool_definition,
    list_workspace_tool_descriptors,
    list_workspace_entries,
    list_workspace_tool_names,
    move_workspace_path,
    normalize_workspace_tool_plan,
    normalize_workspace_tool_result,
    plan_workspace_tool,
    read_workspace_text,
    run_workspace_tests,
    search_workspace_text,
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


def test_workspace_tools_can_move_copy_delete_and_search_text():
    safe_write_file("notes/files/source.txt", "hello file tools\nsecond line")

    moved = move_workspace_path("notes/files/source.txt", "notes/files/renamed.txt")
    copied = copy_workspace_path("notes/files/renamed.txt", "notes/files/copied.txt")
    search = search_workspace_text("hello", rel_path="notes/files")
    deleted = delete_workspace_path("notes/files/copied.txt")

    assert moved["source_path"] == "notes/files/source.txt"
    assert moved["target_path"] == "notes/files/renamed.txt"
    assert copied["source_path"] == "notes/files/renamed.txt"
    assert copied["target_path"] == "notes/files/copied.txt"
    assert search["match_count"] == 2
    assert {match["path"] for match in search["matches"]} == {
        "notes/files/copied.txt",
        "notes/files/renamed.txt",
    }
    assert deleted["path"] == "notes/files/copied.txt"
    with pytest.raises(FileNotFoundError):
        read_workspace_text("notes/files/copied.txt")


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


def test_workspace_tool_planning_preserves_multiline_markdown_content():
    prompt = """请创建 notes/rich.md，内容如下：
# Title

$$
\\int \\frac{1}{x} \\, dx = \\ln|x| + C
$$

```python
print("hello")
```

然后读出来确认"""

    plan = plan_workspace_tool(prompt)
    result = execute_workspace_tool_plan(plan)
    content = read_workspace_text("notes/rich.md")["content"]

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert "# Title" in plan["tool_input"]["content"]
    assert "```python" in plan["tool_input"]["content"]
    assert "\\int \\frac{1}{x}" in plan["tool_input"]["content"]
    assert "然后读出来确认" not in plan["tool_input"]["content"]
    assert result["ok"] is True
    assert content == plan["tool_input"]["content"]


def test_workspace_tool_planning_strips_outer_code_fence_for_code_file():
    prompt = """请创建 scripts/demo.py，代码如下：
```python
print("hello")
```
然后读出来确认"""

    plan = plan_workspace_tool(prompt)
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["tool_input"]["rel_path"] == "scripts/demo.py"
    assert plan["tool_input"]["content"] == 'print("hello")'
    assert result["ok"] is True
    assert read_workspace_text("scripts/demo.py")["content"] == 'print("hello")'


def test_workspace_tool_planning_does_not_trim_followup_words_inside_code_block():
    prompt = """请创建 scripts/followup_words.py，代码如下：
```python
print("然后读出来确认")
```
然后读出来确认"""

    plan = plan_workspace_tool(prompt)
    result = execute_workspace_tool_plan(plan)

    assert plan["tool_name"] == WORKSPACE_TOOL_NAME_WRITE
    assert plan["tool_input"]["content"] == 'print("然后读出来确认")'
    assert result["ok"] is True
    assert read_workspace_text("scripts/followup_words.py")["content"] == 'print("然后读出来确认")'


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


def test_workspace_tool_planning_can_move_copy_delete_and_search_paths():
    safe_write_file("notes/ops/a.txt", "hello ops")

    move_plan = plan_workspace_tool("请把 notes/ops/a.txt 改名为 b.txt")
    move_result = execute_workspace_tool_plan(move_plan)
    copy_plan = plan_workspace_tool("请把 notes/ops/b.txt 复制到 notes/ops/c.txt")
    copy_result = execute_workspace_tool_plan(copy_plan)
    search_plan = plan_workspace_tool("请查找 notes/ops 下包含 hello 的文件")
    search_result = execute_workspace_tool_plan(search_plan)

    assert move_plan["tool_name"] == WORKSPACE_TOOL_NAME_MOVE
    assert move_plan["tool_input"] == {
        "source_path": "notes/ops/a.txt",
        "target_path": "notes/ops/b.txt",
        "overwrite": False,
    }
    assert move_result["ok"] is True
    assert read_workspace_text("notes/ops/b.txt")["content"] == "hello ops"

    assert copy_plan["tool_name"] == WORKSPACE_TOOL_NAME_COPY
    assert copy_plan["tool_input"] == {
        "source_path": "notes/ops/b.txt",
        "target_path": "notes/ops/c.txt",
        "overwrite": False,
        "recursive": False,
    }
    assert copy_result["ok"] is True
    assert read_workspace_text("notes/ops/c.txt")["content"] == "hello ops"

    assert search_plan["tool_name"] == WORKSPACE_TOOL_NAME_SEARCH
    assert search_plan["tool_input"]["rel_path"] == "notes/ops"
    assert search_plan["tool_input"]["query"] == "hello"
    assert search_result["ok"] is True
    assert search_result["data"]["match_count"] == 2

    delete_plan = plan_workspace_tool("请删除 notes/ops/c.txt")
    delete_result = execute_workspace_tool_plan(delete_plan)

    assert delete_plan["tool_name"] == WORKSPACE_TOOL_NAME_DELETE
    assert delete_plan["tool_input"] == {
        "rel_path": "notes/ops/c.txt",
        "recursive": False,
    }
    assert delete_result["ok"] is True
    assert "已删除文件" in delete_result["summary"]


def test_workspace_tool_planning_supports_directory_copy_search_and_recursive_delete():
    safe_write_file("notes/tree/source/a.txt", "hello tree")
    safe_write_file("notes/tree/source/nested/b.txt", "nested tree")

    copy_plan = plan_workspace_tool("请复制 notes/tree/source 目录到 notes/tree/source-copy 目录")
    copy_result = execute_workspace_tool_plan(copy_plan)
    search_plan = plan_workspace_tool("请在 notes/tree/source-copy 下搜索 hello")
    search_result = execute_workspace_tool_plan(search_plan)

    assert copy_plan["tool_name"] == WORKSPACE_TOOL_NAME_COPY
    assert copy_plan["tool_input"] == {
        "source_path": "notes/tree/source",
        "target_path": "notes/tree/source-copy",
        "overwrite": False,
        "recursive": True,
    }
    assert copy_result["ok"] is True
    assert read_workspace_text("notes/tree/source-copy/a.txt")["content"] == "hello tree"
    assert read_workspace_text("notes/tree/source-copy/nested/b.txt")["content"] == "nested tree"

    assert search_plan["tool_name"] == WORKSPACE_TOOL_NAME_SEARCH
    assert search_plan["tool_input"]["rel_path"] == "notes/tree/source-copy"
    assert search_plan["tool_input"]["query"] == "hello"
    assert search_result["ok"] is True
    assert search_result["data"]["match_count"] == 1

    delete_plan = plan_workspace_tool("请删除 notes/tree/source-copy 目录及其内容")
    delete_result = execute_workspace_tool_plan(delete_plan)

    assert delete_plan["tool_name"] == WORKSPACE_TOOL_NAME_DELETE
    assert delete_plan["tool_input"] == {
        "rel_path": "notes/tree/source-copy",
        "recursive": True,
    }
    assert delete_result["ok"] is True
    assert "已删除目录" in delete_result["summary"]
    with pytest.raises(FileNotFoundError):
        read_workspace_text("notes/tree/source-copy/a.txt")


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


def test_workspace_tool_planning_falls_back_to_run_create_for_codegen():
    """包含"写"的代码任务应返回 None，交由 routing 层用 run.create 处理。"""
    plan = plan_workspace_tool("帮我写一个新的 python 脚本")

    assert plan is None


def test_workspace_tool_planning_unrelated_query_still_goes_to_overview():
    """不含写/创建等关键词的普通查询仍回落至 overview。"""
    plan = plan_workspace_tool("帮我看看这个项目里有什么文件")

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
    assert WORKSPACE_TOOL_NAME_MOVE in names
    assert WORKSPACE_TOOL_NAME_COPY in names
    assert WORKSPACE_TOOL_NAME_DELETE in names
    assert WORKSPACE_TOOL_NAME_SEARCH in names
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
            "file_operation",
            "text_search",
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
