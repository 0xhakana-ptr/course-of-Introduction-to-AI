from backend.app.agent_workflow.repair_decision_graph import (
    evaluate_repair_decision,
    run_repair_workflow,
)
from backend.app.agent_workflow.retry_guidance import build_retry_guidance
from backend.app.agent_workflow.repair_support import (
    build_failure_inspected_state,
    build_feedback_composed_state,
    build_repair_codegen_state,
    build_repair_decision_state,
    build_repair_eligibility_state,
    build_repair_feedback_message,
    select_repair_graph_next_step,
)
from backend.app.agent_workflow.workflow_results import WorkflowRepairResult
from backend.app.services.run_action.types import ScriptGenerationResult, WorkflowChatMessage


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
    assert decision.output == decision.reason
    assert decision.as_dict()["reason"] == decision.reason


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
    assert decision.state["should_attempt_repair"] is True


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
    assert decision.as_dict()["analysis_source"] == "llm"


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
    assert result.feedback_message is not None
    assert result.feedback_message.node_name == "task_repairing"
    assert result.feedback_text is not None
    assert result.retry_guidance is None
    assert result.retry_next_action is None
    assert result.retry_node_name is None
    assert result.output == result.feedback_text
    assert result.as_dict()["feedback_text"] == result.feedback_text
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
    assert result.feedback_message is None
    assert result.feedback_text is None
    assert result.retry_guidance is None
    assert result.retry_next_action is None
    assert result.retry_node_name is None
    assert result.output == result.reason
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
    assert result.as_dict()["retry_node_name"] == "task_retry_repairing"


def test_workflow_repair_result_can_normalize_generic_object_fields():
    fake_repair_workflow = type(
        "FakeRepairWorkflow",
        (),
        {
            "should_attempt_repair": False,
            "reason": "模拟的 QA 决策：这次不继续自动修复。",
            "analysis_note": "这是一个受控失败场景，直接结束更合适。",
            "analysis_source": "test",
            "failure_summary": "simulated failure summary",
            "feedback_text": "我已经分析完这次失败了。",
            "feedback_node_name": "task_repairing",
            "retry_node_name": "task_retry_failed",
            "retry_next_action": "我会结束当前任务并整理失败原因。",
        },
    )()

    result = WorkflowRepairResult.from_value(fake_repair_workflow)

    assert result.should_attempt_repair is False
    assert result.reason == "模拟的 QA 决策：这次不继续自动修复。"
    assert result.analysis_note == "这是一个受控失败场景，直接结束更合适。"
    assert result.feedback_text == "我已经分析完这次失败了。"
    assert result.feedback_node_name == "task_repairing"
    assert result.retry_node_name == "task_retry_failed"
    assert result.retry_next_action == "我会结束当前任务并整理失败原因。"
    assert result.output == "我已经分析完这次失败了。"
    assert result.as_dict()["feedback_node_name"] == "task_repairing"


def test_repair_support_selects_next_step_consistently():
    assert select_repair_graph_next_step({"should_attempt_repair": False}) == "end"
    assert (
        select_repair_graph_next_step(
            {
                "should_attempt_repair": True,
                "generate_feedback": True,
                "generate_repair_script": True,
            }
        )
        == "compose_feedback_node"
    )
    assert (
        select_repair_graph_next_step(
            {
                "should_attempt_repair": True,
                "generate_feedback": True,
                "generate_repair_script": True,
            },
            after_feedback=True,
        )
        == "repair_codegen_node"
    )


def test_repair_support_builds_feedback_message():
    message = build_repair_feedback_message(
        run_id="run_demo_4",
        attempt_number=2,
        current_generator="llm_repair",
        repair_count=1,
        failure_result={
            "command": "python broken_demo.py",
            "returncode": 1,
            "stderr": "Traceback ... RuntimeError: retry failure",
            "stdout": "retry still fails",
            "error": "RuntimeError: retry failure",
        },
        analysis_note="这次自动修复后的脚本仍然在运行时报错。",
    )

    assert message.node_name == "task_repairing"
    assert "run_id: run_demo_4" in message.content
    assert "分析:" in message.content
    assert "下一步:" in message.content


def test_retry_guidance_builder_returns_expected_mapping():
    guidance = build_retry_guidance("task_retry_done")

    assert guidance.node_name == "task_retry_done"
    assert "整理最终结果" in guidance.next_action


def test_repair_support_builds_state_updates_consistently():
    base_state = {
        "current_generator": "llm_repair",
        "decision_reason": "",
    }

    inspected_state = build_failure_inspected_state(
        base_state,
        failure_summary="failure summary",
    )
    blocked_state = build_repair_eligibility_state(
        base_state,
        eligible=False,
        decision_reason="blocked",
    )
    decided_state = build_repair_decision_state(
        base_state,
        current_generator="llm_repair",
        should_attempt_repair=True,
        decision_reason="go repair",
    )

    assert inspected_state["failure_summary"] == "failure summary"
    assert inspected_state["analysis_note"] == "failure summary"
    assert blocked_state["eligible"] is False
    assert blocked_state["decision_reason"] == "blocked"
    assert decided_state["should_attempt_repair"] is True
    assert decided_state["decision_reason"] == "go repair"
    assert decided_state["retry_guidance"] is not None
    assert decided_state["retry_guidance"].node_name == "task_retry_repairing"


def test_repair_support_builds_feedback_and_codegen_state():
    base_state = {"repair_count": 0}
    feedback_message = WorkflowChatMessage(
        node_name="task_repairing",
        content="repair feedback",
    )
    repaired_result = ScriptGenerationResult(
        ok=True,
        file_name="demo.py",
        script_content='print("ok")\n',
        raw_output="raw",
    )

    feedback_state = build_feedback_composed_state(
        base_state,
        feedback_message=feedback_message,
    )
    codegen_state = build_repair_codegen_state(
        base_state,
        repaired_result=repaired_result,
    )

    assert feedback_state["feedback_message"] == feedback_message
    assert codegen_state["repaired_result"] == repaired_result


def test_repair_workflow_returns_failed_result_when_graph_invoke_fails(monkeypatch):
    fake_graph = type(
        "BrokenGraph",
        (),
        {
            "invoke": lambda self, state: (_ for _ in ()).throw(RuntimeError("repair graph boom")),
        },
    )()
    monkeypatch.setattr(
        "backend.app.agent_workflow.repair_decision_graph.repair_decision_graph",
        fake_graph,
    )

    result = evaluate_repair_decision(
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

    assert result.ok is False
    assert result.should_attempt_repair is False
    assert "自动修复工作流执行失败" in result.reason
    assert "repair graph boom" in result.reason
