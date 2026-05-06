from backend.app.services.run_action.recovery import recover_interrupted_runs
from backend.app.services.run_interface import create_run, execute_run, get_run, get_run_attempt
from backend.app.storage.run_store import append_run_attempt, update_run_record, utc_now_iso


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
