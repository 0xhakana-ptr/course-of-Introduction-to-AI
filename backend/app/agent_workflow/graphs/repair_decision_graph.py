"""Compatibility import: graphs.repair_decision_graph -> agent_workflow.repair.repair_decision_graph.

Module aliasing keeps the historical import path AND its monkeypatch targets
pointing at the same module object as the documented location.
"""
import sys

from ..repair import repair_decision_graph as _impl

sys.modules[__name__] = _impl
