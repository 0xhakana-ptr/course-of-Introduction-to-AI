import importlib

import pytest

from backend.app.agent_workflow.loop.agent_loop_graph import run_agent_loop


@pytest.mark.skip(reason="Old test - requires full runtime environment")
def test_agent_loop_graph_imports():
    """Verify that the simplified agent_loop_graph module imports cleanly."""
    loop_module = importlib.import_module(
        "backend.app.agent_workflow.loop.agent_loop_graph"
    )
    assert hasattr(loop_module, "run_agent_loop")
    assert hasattr(loop_module, "agent_loop_graph")
    assert hasattr(loop_module, "plan_node")
    assert hasattr(loop_module, "act_node")
    assert hasattr(loop_module, "observe_node")
    assert not hasattr(loop_module, "perceive_node")  # was removed
