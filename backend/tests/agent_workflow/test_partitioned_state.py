import json

from backend.app.agent_workflow.state import (
    CodingWorkflowState,
    EngineeringState,
    FrontendState,
    find_frontend_state_violations,
)


def test_frontend_state_excludes_raw_engineering_payload():
    frontend = FrontendState.from_mapping(
        {
            "ui_status": "coding_failed",
            "phase": "qa",
            "quip": "我正在检查失败原因。",
            "progress": 50,
            "raw_error": "SECRET_RAW_ERROR",
            "stderr": "SECRET_STDERR",
            "workflow_trace": [{"details": {"raw_error": "SECRET_TRACE"}}],
            "auth_request": {
                "prompt": "确认后继续",
                "raw_error": "SECRET_AUTH_ERROR",
                "blocked_action_name": "workspace.test",
            },
        }
    )

    payload = frontend.as_dict()
    dumped = json.dumps(payload, ensure_ascii=False)

    assert payload["ui_status"] == "coding_failed"
    assert payload["current_phase"] == "qa"
    assert payload["roleplay_line"] == "我正在检查失败原因。"
    assert payload["auth_request"]["blocked_action_name"] == "workspace.test"
    assert "SECRET" not in dumped
    assert find_frontend_state_violations(payload) == []


def test_engineering_state_uses_refs_instead_of_raw_payloads():
    engineering = EngineeringState.from_mapping(
        {
            "tasks_list": ["创建文件", "运行测试"],
            "current_task": "运行测试",
            "target_files": ["notes/demo.txt"],
            "current_code_or_patch": "SECRET_FULL_CODE",
            "current_code_or_patch_ref": "artifact://patches/1",
            "raw_error": "SECRET_STACK_TRACE",
            "raw_error_ref": "artifact://errors/1",
            "error_summary": "测试失败：断言不匹配。",
            "repair_count": 1,
            "artifact_refs": ["artifact://patches/1", "artifact://errors/1"],
        }
    )

    payload = engineering.as_dict()
    dumped = json.dumps(payload, ensure_ascii=False)

    assert payload["tasks_list"] == ["创建文件", "运行测试"]
    assert payload["current_code_or_patch_ref"] == "artifact://patches/1"
    assert payload["raw_error_ref"] == "artifact://errors/1"
    assert payload["error_summary"] == "测试失败：断言不匹配。"
    assert "raw_error" not in payload
    assert "current_code_or_patch" not in payload
    assert "SECRET" not in dumped


def test_engineering_state_can_clear_raw_error_ref_after_summary():
    engineering = EngineeringState(raw_error_ref="artifact://errors/2")

    summarized = engineering.with_error_summary("文件不存在。")

    assert summarized.raw_error_ref is None
    assert summarized.error_summary == "文件不存在。"


def test_coding_workflow_state_is_json_serializable_and_partitioned():
    state = CodingWorkflowState.from_mapping(
        {
            "turn_id": "turn_1",
            "session_id": "session_1",
            "user_input": "请创建 notes/demo.txt",
            "intent": "coding",
            "ui_status": "loop_planned",
            "action_plan": {
                "action_name": "workspace.write",
                "raw_error": "SECRET_PLAN_ERROR",
            },
            "workflow_trace": [
                {
                    "node": "plan_node",
                    "event": "loop_planned",
                    "details": {"stderr": "SECRET_TRACE_STDERR"},
                }
            ],
            "tasks_list": ["创建文件"],
            "current_task": "创建文件",
            "target_files": ["notes/demo.txt"],
            "raw_error": "SECRET_RAW_ERROR",
            "raw_error_ref": "artifact://errors/3",
            "tool_name": "workspace.write",
            "tool_input": {
                "rel_path": "notes/demo.txt",
                "raw_error": "SECRET_TOOL_INPUT",
            },
            "tool_result": {"raw_error": "SECRET_TOOL_RESULT"},
            "tool_result_ref": "artifact://tool-results/1",
        }
    )

    payload = state.as_dict()
    dumped = json.dumps(payload, ensure_ascii=False)

    assert payload["turn"]["turn_id"] == "turn_1"
    assert payload["frontend"]["ui_status"] == "loop_planned"
    assert payload["engineering"]["raw_error_ref"] == "artifact://errors/3"
    assert payload["tool"]["tool_input"]["rel_path"] == "notes/demo.txt"
    assert payload["tool"]["tool_result_ref"] == "artifact://tool-results/1"
    assert "SECRET" not in dumped
    assert find_frontend_state_violations(payload["frontend"]) == []
