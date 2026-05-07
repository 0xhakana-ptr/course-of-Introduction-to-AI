from backend.app.agent_workflow.repair_decision_graph import (
    evaluate_repair_decision,
    run_repair_workflow,
)
from backend.app.services.run_action.types import ScriptGenerationResult


def test_repair_decision_graph_blocks_when_llm_is_unavailable():
    decision = evaluate_repair_decision(
        prompt="build a demo",
        context=None,
        file_name="broken_demo.py",
        script_content='raise RuntimeError("Intentional demo failure")\n',
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: Intentional demo failure",
            "stdout": "This demo will fail intentionally.",
            "error": "RuntimeError: Intentional demo failure",
        },
        repair_count=0,
        max_repair_attempts=1,
        llm_configured=False,
    )

    assert decision.should_attempt_repair is False
    assert decision.reason == "未配置真实大模型，无法自动修复失败脚本。"
    assert "RuntimeError" in decision.analysis_note


def test_repair_decision_graph_allows_repair_when_budget_remains():
    decision = evaluate_repair_decision(
        prompt="build a demo",
        context=None,
        file_name="broken_demo.py",
        script_content='raise RuntimeError("Intentional demo failure")\n',
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: Intentional demo failure",
            "stdout": "This demo will fail intentionally.",
            "error": "RuntimeError: Intentional demo failure",
        },
        repair_count=0,
        max_repair_attempts=1,
        llm_configured=True,
    )

    assert decision.should_attempt_repair is True
    assert "准备尝试自动修复" in decision.reason
    assert decision.analysis_source in {"fallback", "llm"}


def test_repair_decision_graph_uses_llm_analysis_when_available(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.llm_is_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.call_llm_sync",
        lambda *args, **kwargs: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": "脚本在运行时抛出了异常，建议针对报错位置修正逻辑后再重试。",
                "error": None,
            },
        )(),
    )

    decision = evaluate_repair_decision(
        prompt="build a demo",
        context=None,
        file_name="broken_demo.py",
        script_content='raise RuntimeError("Intentional demo failure")\n',
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: Intentional demo failure",
            "stdout": "This demo will fail intentionally.",
            "error": "RuntimeError: Intentional demo failure",
        },
        repair_count=0,
        max_repair_attempts=1,
        llm_configured=True,
    )

    assert decision.should_attempt_repair is True
    assert decision.analysis_source == "llm"
    assert "建议针对报错位置修正逻辑后再重试" in decision.analysis_note


def test_repair_workflow_graph_returns_generated_script(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.generate_repaired_script_with_llm",
        lambda **kwargs: ScriptGenerationResult(
            ok=True,
            file_name="repaired_demo.py",
            script_content='print("repair succeeded")\n',
            raw_output='FILENAME: repaired_demo.py\n```python\nprint("repair succeeded")\n```',
        ),
    )

    result = run_repair_workflow(
        run_id="run_demo_1",
        prompt="build a demo",
        context=None,
        file_name="broken_demo.py",
        script_content='raise RuntimeError("Intentional demo failure")\n',
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: Intentional demo failure",
            "stdout": "This demo will fail intentionally.",
            "error": "RuntimeError: Intentional demo failure",
            "generator": "template",
        },
        attempt_number=1,
        current_generator="template",
        repair_count=0,
        max_repair_attempts=1,
        llm_configured=True,
    )

    assert result.should_attempt_repair is True
    assert result.repaired_result is not None
    assert result.repaired_result.ok is True
    assert result.repaired_result.file_name == "repaired_demo.py"
    assert result.feedback_text is not None
    assert result.retry_guidance is None
    assert result.retry_next_action is None
    assert result.retry_node_name is None
    assert "run_id: run_demo_1" in result.feedback_text
    assert "下一步:" in result.feedback_text


def test_repair_workflow_graph_skips_generation_when_repair_is_blocked(monkeypatch):
    called = {"value": False}

    def fake_generate(**kwargs):
        called["value"] = True
        return ScriptGenerationResult(ok=False, error="should not be called")

    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.generate_repaired_script_with_llm",
        fake_generate,
    )

    result = run_repair_workflow(
        run_id="run_demo_2",
        prompt="build a demo",
        context=None,
        file_name="broken_demo.py",
        script_content='raise RuntimeError("Intentional demo failure")\n',
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: Intentional demo failure",
            "stdout": "This demo will fail intentionally.",
            "error": "RuntimeError: Intentional demo failure",
            "generator": "template",
        },
        attempt_number=1,
        current_generator="template",
        repair_count=1,
        max_repair_attempts=1,
        llm_configured=True,
    )

    assert result.should_attempt_repair is False
    assert result.repaired_result is None
    assert result.feedback_text is None
    assert result.retry_guidance is None
    assert result.retry_next_action is None
    assert result.retry_node_name is None
    assert called["value"] is False


def test_repair_workflow_graph_returns_retry_guidance_for_failed_repair_attempt():
    result = run_repair_workflow(
        run_id="run_demo_3",
        prompt="build a demo",
        context=None,
        file_name="broken_demo.py",
        script_content='raise RuntimeError("Intentional demo failure")\n',
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: Intentional demo failure",
            "stdout": "This demo will fail intentionally.",
            "error": "RuntimeError: Intentional demo failure",
            "generator": "llm_repair",
        },
        attempt_number=2,
        current_generator="llm_repair",
        repair_count=1,
        max_repair_attempts=2,
        llm_configured=True,
    )

    assert result.should_attempt_repair is True
    assert result.retry_guidance is not None
    assert result.retry_guidance.node_name == "task_retry_repairing"
    assert "继续分析这次失败" in result.retry_guidance.next_action
    assert result.retry_node_name == "task_retry_repairing"
    assert result.retry_next_action is not None
    assert "继续分析这次失败" in result.retry_next_action
