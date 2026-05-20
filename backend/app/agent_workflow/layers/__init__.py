"""Agent workflow layers package.

Layer 1 (routing_guard) lives here.
Layer 2 (roleplay) has moved to agent_workflow/roleplay.py.
"""
from .routing_guard import routing_guard, RoutingDecision, INTENT_CHAT, INTENT_CODING, INTENT_UNKNOWN

def _get_roleplay_agent():
    from ..roleplay import roleplay_agent
    return roleplay_agent

__all__ = [
    "routing_guard",
    "RoutingDecision",
    "INTENT_CHAT",
    "INTENT_CODING",
    "INTENT_UNKNOWN",
    "_get_roleplay_agent",
]