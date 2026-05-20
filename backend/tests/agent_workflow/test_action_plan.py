from backend.app.agent_workflow.graphs.loop_agent_loop_graph import _build_action_plan_from_routing


def test_action_plan_pass_through_chat():
    """Routing pass-through: action_name/input flow from state through plan."""
    action_name, action_input, plan_details = _build_action_plan_from_routing(
        {
            "user_input": "hello",
            "context": "ctx",
            "intent": "chat",
            "action_name": "chat.reply",
            "action_input": {"prompt": "hello"},
        }
    )
    assert action_name == "chat.reply"
    assert action_input.get("prompt") == "hello"
    assert plan_details.get("intent") == "chat"
    assert plan_details.get("routed") is True
    assert plan_details.get("planner_source") == "rules"


def test_action_plan_pass_through_coding():
    """Coding routing: action_name passes through without LLM."""
    action_name, action_input, plan_details = _build_action_plan_from_routing(
        {
            "user_input": "write a file",
            "intent": "coding",
            "action_name": "workspace.write",
            "action_input": {"prompt": "write a demo"},
        }
    )
    assert action_name == "workspace.write"
    assert action_input.get("prompt") == "write a demo"
    assert plan_details.get("intent") == "coding"
    assert plan_details.get("routed") is True


def test_action_plan_missing_action_name_raises():
    """State without action_name raises ValueError."""
    import pytest
    with pytest.raises(ValueError, match="without action_name"):
        _build_action_plan_from_routing(
            {
                "user_input": "no action name",
                "intent": "coding",
            }
        )


def test_action_plan_default_intent():
    """When intent is missing, defaults to 'coding'."""
    action_name, action_input, plan_details = _build_action_plan_from_routing(
        {
            "action_name": "run.create",
            "action_input": {"prompt": "run something"},
        }
    )
    assert action_name == "run.create"
    assert plan_details.get("intent") == "coding"
