# -*- coding: utf-8 -*-
"""Three-layer agent architecture.

Layer 1: Routing Guard  - Intent detection + routing (routing_guard.py)
Layer 2: Roleplay Agent  - Persona wrapper, user-facing (roleplay_output.py)
Layer 3: Work Agent      - Actual work execution via LangGraph (work_engine.py)

Flow: User -> L1(Routing) -> L2(Roleplay) -> L3(Work) -> L2 -> Frontend
"""

from .routing_guard import RoutingDecision, RoutingGuard, routing_guard
from .work_engine import WorkAgent, WorkAgentResult, work_agent
from .roleplay_output import RoleplayAgent, RoleplayResponse, roleplay_agent

__all__ = [
    "RoutingDecision",
    "RoutingGuard",
    "routing_guard",
    "RoleplayAgent",
    "RoleplayResponse",
    "roleplay_agent",
    "WorkAgent",
    "WorkAgentResult",
    "work_agent",
]
