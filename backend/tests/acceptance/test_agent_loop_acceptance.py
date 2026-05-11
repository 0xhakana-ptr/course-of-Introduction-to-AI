import importlib

import pytest

from backend.app.message_queue import message_queue
from backend.app.services.run_interface import create_run, execute_run, get_run
from backend.app.tools.safe_fs import safe_write_file
from backend.app.tools.workspace_tools import read_workspace_text


def _fake_llm_result(output: str, *, ok: bool = True, error: str | None = None):
    return type(
        "FakeLLMResult",
        (),
        {
            "ok": ok,
            "output": output,
            "error": error,
        },
    )()


def _messages(client) -> list[dict[str, object]]:
    response = client.get("/messages")
    assert response.status_code == 200
    return response.json()["messages"]


def _assert_workflow_terminal(
    messages: list[dict[str, object]],
    *,
    event_type: str = "workflow.completed",
) -> dict[str, object]:
    terminals = [
        message
        for message in messages
        if message.get("type") == "status"
        and message.get("event_type") in {"workflow.completed", "workflow.failed"}
    ]

    assert terminals, "expected a workflow terminal event"
    terminal = terminals[-1]
    assert terminal["event_type"] == event_type
    assert terminal["status"] == ("error" if event_type == "workflow.failed" else "done")
    return terminal


def _assert_action_event(
    messages: list[dict[str, object]],
    *,
    action_name: str,
    event_type: str = "workflow.action_completed",
) -> dict[str, object]:
    matches = [
        message
        for message in messages
        if message.get("type") == "status"
        and message.get("event_type") == event_type
        and (message.get("metadata") or {}).get("action_name") == action_name
    ]

    assert matches, f"expected {event_type} for {action_name}"
    return matches[-1]


@pytest.mark.parametrize(
    ("prompt", "reply"),
    [
        ("你是谁", "我是桌宠 Agent。"),
        ("我是谁", "我还不知道你的名字，但我会记住这次对话里的信息。"),
        ("1+1=？", "1+1=2。"),
    ],
)
def test_acceptance_chat_prompts_return_workflow_terminal(monkeypatch, client, prompt, reply):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: _fake_llm_result(reply),
    )

    response = client.post("/chat", json={"prompt": prompt, "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "chat"
    assert payload["output"] == reply
    assert payload["runtime_mode"] == "loop"
    assert payload["route_scope"] == "primary_loop"

    messages = _messages(client)
    _assert_action_event(messages, action_name="chat.reply")
    _assert_workflow_terminal(messages)


def test_acceptance_workspace_write_returns_terminal_and_creates_file(client):
    response = client.post(
        "/chat",
        json={"prompt": "请创建 notes/p1-write.txt，内容是p1 ok", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"] is None
    assert "已在 workspace 中创建文本文件" in payload["output"]
    assert read_workspace_text("notes/p1-write.txt")["content"] == "p1 ok"

    messages = _messages(client)
    _assert_action_event(messages, action_name="workspace.write")
    _assert_workflow_terminal(messages)


def test_acceptance_workspace_explicit_overwrite_returns_terminal_and_updates_file(client):
    safe_write_file("notes/p1-overwrite.txt", "old")

    response = client.post(
        "/chat",
        json={"prompt": "请覆盖 notes/p1-overwrite.txt，内容是new", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert "已在 workspace 中覆盖文本文件" in payload["output"]
    assert read_workspace_text("notes/p1-overwrite.txt")["content"] == "new"

    messages = _messages(client)
    _assert_action_event(messages, action_name="workspace.write")
    _assert_workflow_terminal(messages)


def test_acceptance_workspace_write_supports_quoted_chinese_space_path(client):
    response = client.post(
        "/chat",
        json={"prompt": "请创建 `notes/中文 文件.txt`，内容是你好", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert "已在 workspace 中创建文本文件" in payload["output"]
    assert read_workspace_text("notes/中文 文件.txt")["content"] == "你好"

    messages = _messages(client)
    _assert_action_event(messages, action_name="workspace.write")
    _assert_workflow_terminal(messages)


def test_acceptance_workspace_write_then_read_returns_terminal(client):
    response = client.post(
        "/chat",
        json={
            "prompt": "请创建 notes/p2-multistep.txt，内容是p2 ok，然后读出来确认",
            "context": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"] is None
    assert "我读到了 `notes/p2-multistep.txt` 的内容" in payload["output"]
    assert "p2 ok" in payload["output"]

    messages = _messages(client)
    _assert_action_event(messages, action_name="workspace.write")
    _assert_action_event(messages, action_name="workspace.read")
    _assert_workflow_terminal(messages)


def test_acceptance_workspace_read_returns_terminal_and_content(client):
    safe_write_file("notes/p1-read.txt", "read me")

    response = client.post(
        "/chat",
        json={"prompt": "请读取 notes/p1-read.txt", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert "read me" in payload["output"]

    messages = _messages(client)
    _assert_action_event(messages, action_name="workspace.read")
    _assert_workflow_terminal(messages)


def test_acceptance_workspace_missing_read_returns_failed_terminal(client):
    response = client.post(
        "/chat",
        json={"prompt": "请读取 notes/missing.txt", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["intent"] == "coding"
    assert "没有找到 workspace 路径 `notes/missing.txt`" in payload["output"]

    messages = _messages(client)
    _assert_action_event(
        messages,
        action_name="workspace.read",
        event_type="workflow.action_failed",
    )
    _assert_workflow_terminal(messages, event_type="workflow.failed")


def test_acceptance_workspace_list_returns_terminal_and_listing(client):
    safe_write_file("notes/listed/info.txt", "listed")

    response = client.post(
        "/chat",
        json={"prompt": "请列出 notes/listed 目录结构", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert "notes/listed/info.txt" in payload["output"]

    messages = _messages(client)
    _assert_action_event(messages, action_name="workspace.list")
    _assert_workflow_terminal(messages)


def test_acceptance_desktop_export_disabled_returns_clear_terminal(client):
    response = client.post(
        "/chat",
        json={"prompt": "帮我在桌面创建 notes/p1-desk.txt，内容是desktop", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"] is None
    assert "DESKTOP_EXPORT_ENABLED=true" in payload["output"]

    messages = _messages(client)
    _assert_action_event(
        messages,
        action_name="workspace.export_desktop",
        event_type="workflow.action_failed",
    )
    _assert_action_event(messages, action_name="final.answer")
    _assert_workflow_terminal(messages)


def test_acceptance_run_create_returns_terminal_and_run_id(client):
    response = client.post(
        "/chat",
        json={"prompt": "请实现一个简单的计算器 demo", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"]
    assert payload["runtime_mode"] == "loop"
    assert get_run(payload["run_id"]) is not None

    messages = _messages(client)
    _assert_action_event(messages, action_name="run.create")
    _assert_workflow_terminal(messages)


def test_acceptance_run_inspect_returns_terminal(client):
    run = create_run("build a demo", None)

    response = client.post(
        "/chat",
        json={"prompt": f"请查看 run_id {run.run_id} 的状态", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"] == run.run_id
    assert "任务已创建，等待后台执行" in payload["output"]

    messages = _messages(client)
    _assert_action_event(messages, action_name="run.inspect")
    _assert_workflow_terminal(messages)


def test_acceptance_run_cancel_returns_terminal(client):
    run = create_run("build a demo", None)

    response = client.post(
        "/chat",
        json={"prompt": f"请确认取消 run_id {run.run_id}", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"] == run.run_id
    assert "取消请求" in payload["output"]
    assert get_run(run.run_id).status == "cancelled"

    messages = _messages(client)
    _assert_action_event(messages, action_name="run.cancel")
    _assert_workflow_terminal(messages)


def test_acceptance_run_retry_returns_terminal(client):
    failed_run = create_run("please run a broken fail demo", None)
    failed_result = execute_run(failed_run.run_id)
    assert failed_result is not None
    assert failed_result.status == "failed"
    message_queue.clear()

    response = client.post(
        "/chat",
        json={"prompt": f"请 retry run_id {failed_run.run_id}", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"]
    assert payload["run_id"] != failed_run.run_id

    messages = _messages(client)
    _assert_action_event(messages, action_name="run.retry")
    _assert_workflow_terminal(messages)


def test_acceptance_run_rerun_returns_terminal(client):
    successful_run = create_run("build a calculator demo", None)
    successful_result = execute_run(successful_run.run_id)
    assert successful_result is not None
    assert successful_result.status == "done"
    message_queue.clear()

    response = client.post(
        "/chat",
        json={"prompt": f"请重新运行 run_id {successful_run.run_id}", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"]
    assert payload["run_id"] != successful_run.run_id

    messages = _messages(client)
    _assert_action_event(messages, action_name="run.rerun")
    _assert_workflow_terminal(messages)


def test_acceptance_chat_failure_returns_failed_terminal(monkeypatch, client):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: _fake_llm_result(
            "调用大模型接口失败。",
            ok=False,
            error="llm failed",
        ),
    )

    response = client.post("/chat", json={"prompt": "你好", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["intent"] == "chat"
    assert payload["error"] == "llm failed"

    messages = _messages(client)
    _assert_action_event(
        messages,
        action_name="chat.reply",
        event_type="workflow.action_failed",
    )
    _assert_workflow_terminal(messages, event_type="workflow.failed")
