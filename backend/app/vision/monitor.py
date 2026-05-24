# -*- coding: utf-8 -*-
"""Vision monitor: 30s screenshot -> ONNX -> LLM -> quip.

Orchestrates the full vision-awareness pipeline running as a background
async task inside the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from .config import get_vision_config
from .screenshot import capture_screenshot
from .inference import run_inference, describe_detections
from .analyzer import analyze_activity, build_vision_prompt, VISION_QUIP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# --- Early imports (fail fast at startup instead of per-tick) ---
_IMPORT_ERRORS: list[str] = []

try:
    from ..agent_workflow.runtime_tracker import runtime_tracker  # noqa: F401
except ImportError as exc:
    _IMPORT_ERRORS.append(f"runtime_tracker: {exc}")

try:
    from ..agent_workflow.roleplay import get_session_mood  # noqa: F401
except ImportError as exc:
    _IMPORT_ERRORS.append(f"roleplay.get_session_mood: {exc}")

try:
    from ..llm.client import call_llm_sync, llm_is_configured  # noqa: F401
except ImportError as exc:
    _IMPORT_ERRORS.append(f"llm.client: {exc}")

try:
    from ..messaging.message_sender import message_sender  # noqa: F401
except ImportError as exc:
    _IMPORT_ERRORS.append(f"message_sender: {exc}")


def _send_frontend_error(code: str, message: str) -> None:
    """Best-effort frontend notification that vision hit an error."""
    try:
        from ..messaging.message_sender import message_sender as ms
        ms.send_error(code=code, message=message, node_name="vision_monitor",
            event_type="system.error", event_source="system", event_stage="system",
        )
    except Exception:
        pass


class VisionMonitor:
    def __init__(self):
        self._cfg = get_vision_config()

    async def run_loop(self):
        if not self._cfg.enabled:
            logger.info("Vision monitor disabled (VISION_ENABLED=false)")
            return
        if _IMPORT_ERRORS:
            logger.error("Vision monitor disabled due to import errors: %s", "; ".join(_IMPORT_ERRORS))
            _send_frontend_error("vision.import_failed", "; ".join(_IMPORT_ERRORS))
            return
        logger.info("Vision monitor started: interval=%ds threshold=%.2f cooldown=%ds",
            self._cfg.interval_seconds, self._cfg.confidence_threshold, self._cfg.quip_cooldown_seconds)
        while True:
            await asyncio.sleep(self._cfg.interval_seconds)
            try:
                await self._tick()
            except Exception:
                logger.exception("Vision monitor tick failed")

    async def _tick(self):
        from ..agent_workflow.runtime_tracker import runtime_tracker as rt
        if rt.task_running:
            return
        img = capture_screenshot()
        if img is None:
            logger.info("Vision tick: no screenshot file yet")
            return
        detections = run_inference(img)
        logger.info("Vision inference: %d detections", len(detections))
        analysis = analyze_activity(detections)
        if not analysis.get("has_content"):
            logger.info("Vision tick: no meaningful UI elements (%s)", analysis.get("element_summary", ""))
            return
        if analysis.get("is_duplicate"):
            logger.info("Vision tick skipped: duplicate scene (cooldown)")
            return
        await self._emit_vision_quip(analysis)

    async def _emit_vision_quip(self, analysis):
        """Delegate to Layer 2 RoleplayAgent for character-aware quip generation.

        The vision observation (activity, elements, mood) is injected into
        the roleplay layer so the character reacts naturally to the screen.
        """
        try:
            from ..agent_workflow.roleplay import roleplay_agent
            await asyncio.to_thread(roleplay_agent.emit_vision_quip, analysis)
        except Exception:
            logger.exception("Vision quip generation failed")


vision_monitor = VisionMonitor()