from backend.app.agent_workflow.coding.worker_payloads import (
    SEND_API_AVAILABLE,
    build_coder_worker_payload,
    build_debugger_worker_payload,
    build_executor_worker_payload,
    build_pm_worker_payload,
    build_qa_worker_payload,
)


def test_coding_worker_payloads_redact_raw_engineering_state():
    state = {
        "user_input": "请创建 notes/payload.txt，内容是 payload",
        "context": "project context",
        "current_task": "创建 notes/payload.txt",
        "workspace_action_name": "workspace.write",
        "workspace_action_input": {
            "rel_path": "notes/payload.txt",
            "content": "payload",
        },
        "raw_error": "SECRET RAW ERROR",
        "raw_error_ref": "artifact://coding/raw-error/1",
        "stdout": "SECRET STDOUT",
        "stderr": "SECRET STDERR",
        "workflow_trace": [{"node": "executor_node"}],
        "action_result": {"error": "SECRET ACTION ERROR"},
    }

    pm_payload = build_pm_worker_payload(state, target_node="pm_node")
    coder_payload = build_coder_worker_payload(state, target_node="coder_node")
    executor_payload = build_executor_worker_payload(
        {
            **state,
            "executor_action_name": "workspace.write",
            "executor_action_input": state["workspace_action_input"],
        },
        target_node="executor_node",
    )
    qa_payload = build_qa_worker_payload(state, target_node="qa_node")
    debugger_payload = build_debugger_worker_payload(
        {
            **state,
            "error_summary": "workspace.write failed",
            "coder_plan": {
                "executor_action_name": "workspace.write",
                "executor_action_input": state["workspace_action_input"],
            },
            "repair_count": 0,
            "max_debug_steps": 1,
        },
        target_node="debugger_node",
    )

    payloads = [pm_payload, coder_payload, executor_payload, qa_payload, debugger_payload]
    dumped_payloads = "\n".join(str(payload.payload) for payload in payloads)
    dumped_redacted_keys = "\n".join(str(payload.redacted_keys) for payload in payloads)

    assert "SECRET" not in dumped_payloads
    assert "workflow_trace" not in dumped_payloads
    assert "action_result" not in dumped_payloads
    assert "raw_error_ref" not in debugger_payload.payload
    assert qa_payload.payload["raw_error_ref"] == "artifact://coding/raw-error/1"
    assert "raw_error" in dumped_redacted_keys


def test_coding_worker_payload_can_build_langgraph_send_when_available():
    payload = build_debugger_worker_payload(
        {
            "current_task": "读取缺失文件",
            "error_summary": "没有找到 workspace 路径 `notes/missing.txt`",
            "executor_action_name": "workspace.read",
            "executor_action_input": {"rel_path": "notes/missing.txt"},
            "repair_count": 0,
            "max_debug_steps": 1,
        },
        target_node="debugger_node",
    )

    assert payload.send_api_available is SEND_API_AVAILABLE
    if SEND_API_AVAILABLE:
        send = payload.to_send()
        assert send.node == "debugger_node"
        assert send.arg["error_summary"].startswith("没有找到 workspace 路径")
