"""Compatibility re-exports for layers package."""
from ..router import routing_guard, RoutingDecision, INTENT_CHAT, INTENT_CODING, INTENT_UNKNOWN  # noqa: F401

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
