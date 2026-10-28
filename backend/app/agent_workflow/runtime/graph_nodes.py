"""Agent runtime graph node registration — compatibility re-export.

The implementation lives in ``state/runtime_graph_nodes.py``; this module keeps
the documented ``runtime/graph_nodes.py`` import path working.
"""

from ..state.runtime_graph_nodes import (  # noqa: F401
    register_agent_graph_nodes,
)

__all__ = ["register_agent_graph_nodes"]
