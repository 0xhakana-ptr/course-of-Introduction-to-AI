from backend.app.agent_workflow.agent_graph import run_agent
from backend.app.services.run_interface import get_run


def test_agent_graph_routes_coding_intent_to_run_tool():
    result = run_agent("write python code", None, intent="coding")

    assert result["ok"] is True
    assert result["intent"] == "coding"
    assert result["run_id"]
    assert result["run_status"] == "queued"

    run = get_run(str(result["run_id"]))
    assert run is not None
    assert run.status == "queued"
