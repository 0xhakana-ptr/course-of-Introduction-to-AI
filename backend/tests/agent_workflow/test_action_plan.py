from backend.app.agent_workflow.loop.agent_loop_graph import _build_action_plan
from backend.app.services.run_interface import create_run
from backend.app.tools.safe_fs import safe_write_file


def test_action_plan_contract_for_chat_intent():
    plan = _build_action_plan(
        {
            "user_input": "hello",
            "context": "ctx",
            "intent": "chat",
        }
    )

    payload = plan.as_dict()
    details = plan.plan_details()

    assert plan.action_name == "chat.reply"
    assert payload["planner_source"] == "rules"
    assert payload["safety_level"] == "low"
    assert payload["requires_confirmation"] is False
    assert payload["terminal"] is True
    assert details["intent"] == "chat"
    assert details["action_plan"]["action_name"] == "chat.reply"


def test_action_plan_contract_for_workspace_write():
    plan = _build_action_plan(
        {
            "user_input": "请创建 notes/action-plan.txt，内容是plan ok",
            "intent": "coding",
        }
    )

    payload = plan.as_dict()
    details = plan.plan_details()

    assert plan.action_name == "workspace.write"
    assert payload["planner_source"] == "rules"
    assert payload["safety_level"] == "medium"
    assert payload["requires_confirmation"] is False
    assert payload["next_action_queue"] == []
    assert details["intent"] == "coding"
    assert details["workspace_tool_plan"]["tool_name"] == "write_workspace_text"
    assert details["action_plan"]["action_input"]["rel_path"] == "notes/action-plan.txt"


def test_action_plan_contract_for_run_control():
    run = create_run("build a demo", None)
    plan = _build_action_plan(
        {
            "user_input": f"请查看 run_id {run.run_id} 的状态",
            "intent": "coding",
        }
    )

    payload = plan.as_dict()
    details = plan.plan_details()

    assert plan.action_name == "run.inspect"
    assert payload["planner_source"] == "rules"
    assert payload["safety_level"] == "low"
    assert payload["requires_confirmation"] is False
    assert details["run_action"] == "inspect"
    assert details["target_run_id"] == run.run_id


def test_action_plan_contract_for_runtime_confirmation():
    safe_write_file(
        "backend/tests/test_action_plan_demo.py",
        "def test_action_plan_demo():\n"
        "    assert True\n",
    )

    plan = _build_action_plan(
        {
            "user_input": "请运行 backend/tests/test_action_plan_demo.py 的测试",
            "intent": "coding",
        }
    )

    payload = plan.as_dict()
    details = plan.plan_details()

    assert plan.action_name == "ask_user_confirmation"
    assert payload["planner_source"] == "rules"
    assert payload["requires_confirmation"] is True
    assert details["confirmation_required"] is True
    assert details["blocked_action_name"] == "workspace.test"
    assert details["blocked_action_plan"]["action_name"] == "workspace.test"
    assert details["action_plan"]["action_name"] == "ask_user_confirmation"


def test_action_plan_contract_for_queued_action():
    plan = _build_action_plan(
        {
            "user_input": "继续读文件",
            "intent": "coding",
            "action_queue": [
                {
                    "action_name": "workspace.read",
                    "action_input": {"rel_path": "notes/action-plan.txt"},
                }
            ],
        }
    )

    payload = plan.as_dict()
    details = plan.plan_details()

    assert plan.action_name == "workspace.read"
    assert payload["planner_source"] == "queue"
    assert payload["next_action_queue"] == []
    assert details["queued_action"] is True
    assert details["next_action_queue"] == []
