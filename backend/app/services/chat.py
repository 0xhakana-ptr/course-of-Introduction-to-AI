"""Compatibility re-export → services.chat_interface.

The chat implementation lives in ``chat_interface.py``; this module keeps the
historical ``services.chat`` import path working for API routes and tests.
"""

from .chat_interface import *  # noqa: F401, F403
from .chat_interface import ChatServiceResult, build_agent_reply, generate_chat_response

__all__ = ["ChatServiceResult", "build_agent_reply", "generate_chat_response"]
