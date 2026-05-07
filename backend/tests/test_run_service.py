import threading
import time

from backend.app.services.run_action.recovery import recover_interrupted_runs
from backend.app.services.run_action.types import ScriptGenerationResult
from backend.app.services.run_interface import create_run, execute_run, get_run, get_run_attempt
from backend.app.storage.run_store import append_run_attempt, update_run_record, utc_now_iso


def wait_for(predicate, timeout_seconds: float = 5.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        value = predicate()
        if value is not None:
            return value
        time.sleep(0.05)
    return None


def test_run_endpoints_expose_attempt_script_output_and_logs(client):
    run = create_run("build a calculator demo", None)

    executed = execute_run(run.run_id)
    assert executed is not None
    assert executed.status == "done"
    assert executed.generator == "template"
    assert executed.attempt_count == 1
    assert executed.artifacts

    run_response = client.get(f"/runs/{run.run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "done"
    assert run_payload["attempt_count"] == 1

    attempts_response = client.get(f"/runs/{run.run_id}/attempts")
    assert attempts_response.status_code == 200
    attempts_payload = attempts_response.json()
    assert attempts_payload["attempt_count"] == 1
    assert attempts_payload["attempts"][0]["status"] == "done"
    assert attempts_payload["attempts"][0]["script_available"] is True

    script_response = client.get(f"/runs/{run.run_id}/attempts/1/script")
    assert script_response.status_code == 200
    script_payload = script_response.json()
    assert script_payload["attempt_file_name"].startswith("attempt_1_")
    assert "def add(a, b):" in script_payload["content"]

    output_response = client.get(
        f"/runs/{run.run_id}/attempts/1/output",
        params={"stream": "stdout", "offset": 0, "limit": 200},
    )
    assert output_response.status_code == 200
    output_payload = output_response.json()
    assert output_payload["stream"] == "stdout"
    assert "Calculator demo:" in output_payload["content"]
    assert output_payload["has_more"] is False

    log_response = client.get(f"/runs/{run.run_id}/logs")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert "Background execution started." in log_payload["content"]
    assert "Run finished successfully." in log_payload["content"]

    summary_response = client.get("/runs/summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["total"] == 1
    assert summary_payload["items"][0]["run_id"] == run.run_id


def test_recover_interrupted_runs_marks_running_attempts_failed():
    run = create_run("recover this run", None)
    run_id = run.run_id
    started_at = utc_now_iso()
    update_run_record(
        run_id,
        status="running",
        output="任务正在后台执行。",
        started_at=started_at,
        attempts=[],
    )
    append_run_attempt(
        run_id,
        {
            "attempt_number": 1,
            "generator": "template",
            "repair_round": 0,
            "status": "running",
            "source_file_name": "demo.py",
            "attempt_file_name": "attempt_1_demo.py",
            "script_rel_path": f"runs/{run_id}/generated/attempt_1_demo.py",
            "command": "python attempt_1_demo.py",
            "cwd": f"runs/{run_id}/generated",
            "stdout": "",
            "stderr": "",
            "error": None,
            "started_at": started_at,
            "finished_at": None,
        },
    )

    result = recover_interrupted_runs()

    assert result.scanned_count == 1
    assert result.recovered_count == 1
    assert result.recovered_run_ids == [run_id]

    recovered_run = get_run(run_id)
    assert recovered_run is not None
    assert recovered_run.status == "failed"
    assert "服务重启" in recovered_run.output

    recovered_attempt = get_run_attempt(run_id, 1)
    assert recovered_attempt is not None
    assert recovered_attempt.status == "failed"
    assert "服务重启" in (recovered_attempt.error or "")


def test_run_failure_without_llm_records_non_repairable_result(client):
    run = create_run("please run a broken fail demo", None)

    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "failed"
    assert executed.generator == "template"
    assert executed.attempt_count == 1
    assert executed.repair_attempted is False
    assert executed.repair_count == 0
    assert "未配置真实大模型，无法自动修复失败脚本。" in executed.output

    attempts_response = client.get(f"/runs/{run.run_id}/attempts")
    assert attempts_response.status_code == 200
    attempts_payload = attempts_response.json()
    assert attempts_payload["attempts"][0]["status"] == "failed"
    assert attempts_payload["attempts"][0]["generator"] == "template"

    stderr_response = client.get(
        f"/runs/{run.run_id}/attempts/1/output",
        params={"stream": "stderr", "offset": 0, "limit": 500},
    )
    assert stderr_response.status_code == 200
    stderr_payload = stderr_response.json()
    assert "Intentional demo failure" in stderr_payload["content"]

    log_response = client.get(f"/runs/{run.run_id}/logs")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert "未配置真实大模型，无法自动修复失败脚本。" in log_payload["content"]
    assert "Run failed." in log_payload["content"]

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_failed"
    assert run.run_id in chat_messages[0]["content"]
    assert "状态: failed" in chat_messages[0]["content"]


def test_run_repair_flow_can_succeed_after_initial_failure(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.generate_script_with_llm",
        lambda prompt, context: ScriptGenerationResult(
            ok=False,
            error="simulated initial generation failure",
        ),
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.generate_repaired_script_with_llm",
        lambda **kwargs: ScriptGenerationResult(
            ok=True,
            file_name="repaired_demo.py",
            script_content='print("repair succeeded")\n',
            raw_output='FILENAME: repaired_demo.py\n```python\nprint("repair succeeded")\n```',
        ),
    )

    run = create_run("please run a broken fail demo", None)

    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "done"
    assert executed.generator == "llm_repair"
    assert executed.attempt_count == 2
    assert executed.repair_attempted is True
    assert executed.repair_count == 1
    assert len(executed.artifacts) == 2
    assert "自动修复后重试成功" in executed.output

    attempts_response = client.get(f"/runs/{run.run_id}/attempts")
    assert attempts_response.status_code == 200
    attempts_payload = attempts_response.json()
    assert attempts_payload["attempt_count"] == 2
    assert attempts_payload["attempts"][0]["status"] == "failed"
    assert attempts_payload["attempts"][0]["generator"] == "template"
    assert attempts_payload["attempts"][1]["status"] == "done"
    assert attempts_payload["attempts"][1]["generator"] == "llm_repair"

    script_response = client.get(f"/runs/{run.run_id}/attempts/2/script")
    assert script_response.status_code == 200
    script_payload = script_response.json()
    assert 'print("repair succeeded")' in script_payload["content"]

    output_response = client.get(
        f"/runs/{run.run_id}/attempts/2/output",
        params={"stream": "stdout", "offset": 0, "limit": 200},
    )
    assert output_response.status_code == 200
    output_payload = output_response.json()
    assert "repair succeeded" in output_payload["content"]

    log_response = client.get(f"/runs/{run.run_id}/logs")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert "Requesting LLM repair 1/1." in log_payload["content"]
    assert "Using LLM-repaired Python script for the next attempt." in log_payload["content"]

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 3
    assert chat_messages[0]["node_name"] == "task_repairing"
    assert run.run_id in chat_messages[0]["content"]
    assert "下一步:" in chat_messages[0]["content"]
    assert chat_messages[1]["node_name"] == "task_retry_done"
    assert "本轮结果:" in chat_messages[1]["content"]
    assert chat_messages[2]["node_name"] == "task_done"


def test_run_repair_flow_fails_when_repaired_script_is_unusable(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.generate_script_with_llm",
        lambda prompt, context: ScriptGenerationResult(
            ok=False,
            error="simulated initial generation failure",
        ),
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.generate_repaired_script_with_llm",
        lambda **kwargs: ScriptGenerationResult(
            ok=False,
            error="simulated repair parse failure",
            raw_output="repair raw output that cannot be parsed",
        ),
    )

    run = create_run("please run a broken fail demo", None)

    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "failed"
    assert executed.generator == "template"
    assert executed.attempt_count == 1
    assert executed.repair_attempted is True
    assert executed.repair_count == 1
    assert "simulated repair parse failure" in executed.output

    attempts_response = client.get(f"/runs/{run.run_id}/attempts")
    assert attempts_response.status_code == 200
    attempts_payload = attempts_response.json()
    assert attempts_payload["attempt_count"] == 1
    assert attempts_payload["attempts"][0]["status"] == "failed"
    assert attempts_payload["attempts"][0]["generator"] == "template"

    log_response = client.get(f"/runs/{run.run_id}/logs")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert "Requesting LLM repair 1/1." in log_payload["content"]
    assert "simulated repair parse failure" in log_payload["content"]
    assert "LLM repair raw preview: repair raw output that cannot be parsed" in log_payload["content"]
    assert "Run failed." in log_payload["content"]


def test_run_repair_retry_failure_emits_retry_outcome_before_final_failure(
    monkeypatch,
    client,
):
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.generate_script_with_llm",
        lambda prompt, context: ScriptGenerationResult(
            ok=False,
            error="simulated initial generation failure",
        ),
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.generate_repaired_script_with_llm",
        lambda **kwargs: ScriptGenerationResult(
            ok=True,
            file_name="repaired_but_still_broken.py",
            script_content='print("retry still fails")\nraise RuntimeError("retry failure")\n',
            raw_output=(
                "FILENAME: repaired_but_still_broken.py\n"
                '```python\nprint("retry still fails")\nraise RuntimeError("retry failure")\n```'
            ),
        ),
    )

    run = create_run("please run a broken fail demo", None)

    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "failed"
    assert executed.generator == "llm_repair"
    assert executed.attempt_count == 2
    assert executed.repair_attempted is True
    assert executed.repair_count == 1

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 3
    assert chat_messages[0]["node_name"] == "task_repairing"
    assert chat_messages[1]["node_name"] == "task_retry_failed"
    assert "下一步:" in chat_messages[1]["content"]
    assert chat_messages[2]["node_name"] == "task_failed"


def test_run_service_respects_repair_decision_graph(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.services.run_interface.repair_llm_is_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.generate_script_with_llm",
        lambda prompt, context: ScriptGenerationResult(
            ok=False,
            error="simulated initial generation failure",
        ),
    )
    monkeypatch.setattr(
        "backend.app.services.run_interface.run_repair_workflow",
        lambda **kwargs: type(
            "FakeRepairWorkflow",
            (),
            {
                "should_attempt_repair": False,
                "reason": "模拟的 QA 决策：本次失败不进入自动修复。",
                "analysis_note": "检测到这是一个受控失败场景，直接结束更合适。",
                "analysis_source": "test",
                "failure_summary": "simulated failure summary",
                "repaired_result": None,
            },
        )(),
    )

    run = create_run("please run a broken fail demo", None)

    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "failed"
    assert executed.repair_attempted is False
    assert executed.repair_count == 0
    assert "模拟的 QA 决策：本次失败不进入自动修复。" in executed.output

    log_response = client.get(f"/runs/{run.run_id}/logs")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert "Repair analysis (test):" in log_payload["content"]
    assert "模拟的 QA 决策：本次失败不进入自动修复。" in log_payload["content"]


def test_retry_route_creates_follow_up_run_for_failed_source(client):
    failed_run = create_run("please run a broken fail demo", None)
    failed_result = execute_run(failed_run.run_id)
    assert failed_result is not None
    assert failed_result.status == "failed"

    response = client.post(f"/runs/{failed_run.run_id}/retry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] != failed_run.run_id
    assert payload["status"] == "queued"
    assert payload["source_run_id"] == failed_run.run_id
    assert payload["trigger_mode"] == "retry"

    follow_up = client.get(f"/runs/{payload['run_id']}")
    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert follow_up_payload["status"] == "failed"
    assert follow_up_payload["source_run_id"] == failed_run.run_id
    assert follow_up_payload["trigger_mode"] == "retry"


def test_retry_route_rejects_non_failed_source(client):
    successful_run = create_run("build a calculator demo", None)
    successful_result = execute_run(successful_run.run_id)
    assert successful_result is not None
    assert successful_result.status == "done"

    response = client.post(f"/runs/{successful_run.run_id}/retry")

    assert response.status_code == 409
    assert "does not support retry" in response.json()["detail"]


def test_rerun_route_creates_follow_up_run_for_successful_source(client):
    successful_run = create_run("build a calculator demo", None)
    successful_result = execute_run(successful_run.run_id)
    assert successful_result is not None
    assert successful_result.status == "done"

    response = client.post(f"/runs/{successful_run.run_id}/rerun")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] != successful_run.run_id
    assert payload["status"] == "queued"
    assert payload["source_run_id"] == successful_run.run_id
    assert payload["trigger_mode"] == "rerun"

    follow_up = client.get(f"/runs/{payload['run_id']}")
    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert follow_up_payload["status"] == "done"
    assert follow_up_payload["source_run_id"] == successful_run.run_id
    assert follow_up_payload["trigger_mode"] == "rerun"


def test_cancel_route_can_cancel_queued_run(client):
    run = create_run("build a calculator demo", None)

    response = client.post(f"/runs/{run.run_id}/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["cancel_requested"] is True
    assert "尚未开始执行" in payload["output"]

    executed = execute_run(run.run_id)
    assert executed is not None
    assert executed.status == "cancelled"
    assert executed.attempt_count == 0


def test_cancel_route_can_stop_running_run(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.services.run_action.lifecycle.resolve_initial_script",
        lambda run_id, prompt, context: (
            "sleepy.py",
            "import time\n"
            'print("start")\n'
            "time.sleep(5)\n"
            'print("end")\n',
            "template",
        ),
    )
    run = create_run("sleep for cancel test", None)

    worker = threading.Thread(target=execute_run, args=(run.run_id,), daemon=True)
    worker.start()

    running_attempt = wait_for(
        lambda: (
            attempt
            if (attempt := get_run_attempt(run.run_id, 1)) is not None and attempt.status == "running"
            else None
        ),
        timeout_seconds=5,
    )
    assert running_attempt is not None

    response = client.post(f"/runs/{run.run_id}/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"running", "cancelled"}
    assert payload["cancel_requested"] is True

    worker.join(timeout=10)
    assert worker.is_alive() is False

    final_run = get_run(run.run_id)
    assert final_run is not None
    assert final_run.status == "cancelled"
    assert final_run.cancel_requested is True
    assert "任务已取消" in final_run.output

    final_attempt = get_run_attempt(run.run_id, 1)
    assert final_attempt is not None
    assert final_attempt.status == "cancelled"
    assert "取消" in (final_attempt.error or "")

    log_response = client.get(f"/runs/{run.run_id}/logs")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert "Cancellation requested during execution." in log_payload["content"]
    assert "Run cancelled." in log_payload["content"]

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_cancelled"
    assert run.run_id in chat_messages[0]["content"]
    assert "状态: cancelled" in chat_messages[0]["content"]


def test_cancel_route_rejects_finished_run(client):
    successful_run = create_run("build a calculator demo", None)
    successful_result = execute_run(successful_run.run_id)
    assert successful_result is not None
    assert successful_result.status == "done"

    response = client.post(f"/runs/{successful_run.run_id}/cancel")

    assert response.status_code == 409
    assert "does not support cancel" in response.json()["detail"]


def test_cancel_route_rejects_unknown_run(client):
    response = client.post("/runs/not-found/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"
