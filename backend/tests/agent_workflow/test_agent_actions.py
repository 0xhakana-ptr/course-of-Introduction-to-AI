from backend.app.agent_workflow.actions import build_default_action_registry
from backend.app.message_queue import message_queue
from backend.app.services.run_interface import get_run
from backend.app.tools.workspace_tools import read_workspace_text


def test_default_action_registry_exposes_required_actions():
    registry = build_default_action_registry()
    descriptors = registry.list_descriptors()
    names = {str(descriptor["name"]) for descriptor in descriptors}

    assert {
        "chat.reply",
        "workspace.read",
        "workspace.write",
        "workspace.list",
        "workspace.test",
        "workspace.export_desktop",
        "run.create",
        "run.inspect",
        "run.retry",
        "run.rerun",
        "run.cancel",
        "character.quip",
        "character.motion",
        "character.expression",
        "ask_user_confirmation",
        "final.answer",
    }.issubset(names)

    export_descriptor = next(
        descriptor for descriptor in descriptors
        if descriptor["name"] == "workspace.export_desktop"
    )
    cancel_descriptor = next(
        descriptor for descriptor in descriptors
        if descriptor["name"] == "run.cancel"
    )
    test_descriptor = next(
        descriptor for descriptor in descriptors
        if descriptor["name"] == "workspace.test"
    )
    assert export_descriptor["requires_confirmation"] is True
    assert export_descriptor["safety_level"] == "high"
    assert cancel_descriptor["requires_confirmation"] is True
    assert test_descriptor["requires_confirmation"] is True
    assert test_descriptor["safety_level"] == "high"


def test_action_registry_executes_workspace_write_action():
    registry = build_default_action_registry()

    result = registry.execute(
        "workspace.write",
        {
            "rel_path": "notes/action.txt",
            "content": "hello action",
        },
    )

    assert result.ok is True
    assert "已在 workspace 中创建文本文件" in result.summary
    assert result.metadata["tool_name"] == "write_workspace_text"
    assert read_workspace_text("notes/action.txt")["content"] == "hello action"


def test_action_registry_blocks_desktop_export_when_not_configured():
    registry = build_default_action_registry()

    result = registry.execute(
        "workspace.export_desktop",
        {
            "rel_path": "action.txt",
            "content": "desktop",
        },
    )

    assert result.ok is False
    assert result.error == "desktop export is disabled or not configured"
    assert result.metadata["tool_error_code"] == "WORKSPACE_TOOL_TARGET_DISABLED"
    assert "不能直接写桌面路径" in result.summary


def test_action_registry_wraps_run_create_and_inspect():
    registry = build_default_action_registry()

    create_result = registry.execute(
        "run.create",
        {
            "prompt": "build a small demo",
            "context": None,
        },
    )

    assert create_result.ok is True
    assert isinstance(create_result.data, dict)
    run_id = str(create_result.data["run_id"])
    assert get_run(run_id) is not None

    inspect_result = registry.execute("run.inspect", {"run_id": run_id})

    assert inspect_result.ok is True
    assert inspect_result.metadata["run_id"] == run_id
    assert inspect_result.metadata["status"] == "queued"


def test_action_registry_executes_character_quip_action():
    registry = build_default_action_registry()

    result = registry.execute(
        "character.quip",
        {
            "content": "开始处理。",
            "node_name": "action_test",
        },
    )

    assert result.ok is True
    messages = message_queue.get_messages()
    assert len(messages) == 1
    assert messages[0]["_channel"] == "agent:quip"
    assert messages[0]["content"] == "开始处理。"
    assert messages[0]["node_name"] == "action_test"


def test_action_registry_reports_unregistered_action():
    registry = build_default_action_registry()

    result = registry.execute("missing.action", {})

    assert result.ok is False
    assert result.error == "unregistered agent action: missing.action"
