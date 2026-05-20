from backend.app.agent_workflow.graphs.coding_planner import parse_llm_coding_plan_json


def test_parse_llm_coding_plan_json_accepts_safe_workspace_write():
    result = parse_llm_coding_plan_json(
        """
        {
          "tasks_list": ["Create a small note file"],
          "executor_action_name": "workspace.write",
          "executor_action_input": {
            "rel_path": "notes/planner.txt",
            "content": "hello from planner",
            "overwrite": false
          },
          "target_files": ["notes/planner.txt"],
          "reason": "The user asked for a text file."
        }
        """,
        prompt="请创建 notes/planner.txt，内容是 hello from planner",
    )

    assert result.ok is True
    assert result.plan is not None
    assert result.plan.executor_action_name == "workspace.write"
    assert result.plan.executor_action_input == {
        "rel_path": "notes/planner.txt",
        "content": "hello from planner",
        "overwrite": False,
    }
    assert result.plan.target_files == ["notes/planner.txt"]


def test_parse_llm_coding_plan_json_rejects_invalid_json_without_crashing():
    result = parse_llm_coding_plan_json(
        "I will write the file now.",
        prompt="请创建 notes/planner.txt",
    )

    assert result.ok is False
    assert result.error_kind == "invalid_json"
    assert result.plan is None


def test_parse_llm_coding_plan_json_rejects_forbidden_local_execution_keys():
    result = parse_llm_coding_plan_json(
        """
        {
          "tasks_list": ["Run command"],
          "executor_action_name": "workspace.write",
          "executor_action_input": {
            "rel_path": "notes/planner.txt",
            "content": "hello",
            "shell_command": "del *"
          },
          "target_files": ["notes/planner.txt"],
          "reason": "bad idea"
        }
        """,
        prompt="请创建 notes/planner.txt",
    )

    assert result.ok is False
    assert result.error_kind == "invalid_action_input"
    assert result.plan is None


def test_parse_llm_coding_plan_json_rejects_unsupported_action():
    result = parse_llm_coding_plan_json(
        """
        {
          "tasks_list": ["Run arbitrary command"],
          "executor_action_name": "terminal.run",
          "executor_action_input": {"command": "echo hi"},
          "target_files": [],
          "reason": "unsupported"
        }
        """,
        prompt="运行命令",
    )

    assert result.ok is False
    assert result.error_kind == "unsupported_action"
    assert result.plan is None
