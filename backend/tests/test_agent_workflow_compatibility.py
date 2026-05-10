import importlib


def test_agent_workflow_root_compatibility_modules_alias_real_modules():
    module_pairs = [
        ("agent_graph", "graph.agent_graph"),
        ("agent_builder_support", "graph.builder_support"),
        ("agent_graph_support", "graph.graph_support"),
        ("agent_constants", "state.constants"),
        ("agent_routing_support", "state.routing"),
        ("agent_run_state", "state.run_state"),
        ("agent_run_support", "state.run_support"),
        ("agent_state_support", "state.state_support"),
        ("agent_text_support", "output.text"),
        ("roleplay", "output.roleplay"),
        ("run_summary_graph", "summary.run_summary_graph"),
        ("attempt_summary_graph", "summary.attempt_summary_graph"),
        ("summary_support", "summary.support"),
        ("repair_decision_graph", "repair.repair_decision_graph"),
        ("repair_support", "repair.support"),
        ("retry_guidance", "repair.retry_guidance"),
        ("diagnostics_failure", "diagnostics.failure"),
        ("diagnostics_support", "diagnostics.support"),
        ("trace_runtime", "trace.runtime"),
        ("trace_messages", "trace.messages"),
        ("workflow_nodes", "contracts.workflow_nodes"),
        ("workflow_results", "contracts.workflow_results"),
        ("node_mappings", "contracts.node_mappings"),
    ]

    for old_name, new_name in module_pairs:
        old_module = importlib.import_module(f"backend.app.agent_workflow.{old_name}")
        new_module = importlib.import_module(f"backend.app.agent_workflow.{new_name}")

        assert old_module is new_module
