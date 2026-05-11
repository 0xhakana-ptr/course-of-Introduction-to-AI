from .core import list_core_action_definitions
from .models import (
    AgentActionDefinition,
    AgentActionDescriptor,
    AgentActionResult,
)
from .registry import AgentActionRegistry
from .run import list_run_action_definitions
from .workspace import list_workspace_action_definitions


def build_default_action_registry() -> AgentActionRegistry:
    return AgentActionRegistry(
        [
            *list_core_action_definitions(),
            *list_workspace_action_definitions(),
            *list_run_action_definitions(),
        ]
    )


default_action_registry = build_default_action_registry()


__all__ = [
    "AgentActionDefinition",
    "AgentActionDescriptor",
    "AgentActionRegistry",
    "AgentActionResult",
    "build_default_action_registry",
    "default_action_registry",
]
