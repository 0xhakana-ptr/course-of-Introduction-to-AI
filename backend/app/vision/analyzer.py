# -*- coding: utf-8 -*-
"""Activity analyzer: YOLO detections -> activity -> LLM prompt."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import Counter, OrderedDict
from typing import Any

from .config import ACTIVITY_PROFILES

logger = logging.getLogger(__name__)

_MIN_TOTAL_DETECTIONS = 2

_cooldown: OrderedDict[str, float] = OrderedDict()
_COOLDOWN_MAX_SIZE = 200


def _cooldown_prune() -> None:
    """Evict oldest entries when cooldown cache exceeds max size."""
    while len(_cooldown) > _COOLDOWN_MAX_SIZE:
        _cooldown.popitem(last=False)


def analyze_activity(detections: list[dict[str, object]]) -> dict[str, Any]:
    """Analyze detections and return structured activity info."""
    if not detections:
        return {
            "has_content": False,
            "element_summary": "screen appears empty or static",
            "activity_label": "idle",
            "mood_hint": "lonely",
            "is_duplicate": False,
        }

    counts = Counter(d["class_name"] for d in detections)
    parts = [f"{count} {name}" for name, count in counts.most_common()]
    element_summary = ", ".join(parts)

    total = sum(counts.values())
    if total < _MIN_TOTAL_DETECTIONS:
        return {
            "has_content": False,
            "element_summary": element_summary,
            "activity_label": "minimal",
            "mood_hint": "neutral",
            "is_duplicate": False,
        }

    activity_label = "using computer"
    mood_hint = "neutral"

    for required_dets, label, mood in ACTIVITY_PROFILES:
        match = all(
            counts.get(class_name, 0) >= min_count
            for class_name, min_count in required_dets
        )
        if match:
            activity_label = label
            mood_hint = mood
            break

    fingerprint = hashlib.md5(
        f"{element_summary}:{activity_label}".encode()
    ).hexdigest()
    now = time.time()
    is_duplicate = False
    if fingerprint in _cooldown:
        from .config import get_vision_config
        cfg = get_vision_config()
        if now - _cooldown[fingerprint] < cfg.quip_cooldown_seconds:
            is_duplicate = True
    _cooldown[fingerprint] = now
    _cooldown.move_to_end(fingerprint)
    _cooldown_prune()

    return {
        "has_content": True,
        "element_summary": element_summary,
        "activity_label": activity_label,
        "mood_hint": mood_hint,
        "is_duplicate": is_duplicate,
    }


VISION_QUIP_SYSTEM_PROMPT = """# System

You are a desktop mascot a.k.a. "Unnamed" -- a tsundere, cheeky desktop sprite with emotions.

## Rules
1. Only output: quip (<=30 chars) + expression name
2. No chat_line, no chat window
3. Natural, sassy, in-character
4. User working -> encourage or grumble
5. User slacking -> tease them
6. Tone: chaotic-good, cute, chuunibyou

## expression: neutral / happy / proud / blush / worried / sad / surprised / thinking / focused

## Output format
JSON only: {"quip": "<=30 char line", "expression": "name"}

## Examples
- Many tabs: "So many tabs, CPU is sobbing~"
- File manager: "Organizing? Need me to help?~"
- Code window: "Injecting magic... watching you (^_^)"
- Empty screen: "So boring, whatcha doing~"
- Long idle: "Time to touch some fish?"
"""

VISION_PROMPT_TEMPLATES: dict[str, str] = {
    "browsing": "User screen shows many browser tabs, appears to be browsing. Elements: {elements}",
    "multitasking": "Multiple active windows detected, user is multitasking. Elements: {elements}",
    "using an application": "User is using an application. Elements: {elements}",
    "managing files": "User is working in a file manager. Elements: {elements}",
    "navigating files": "User is browsing file directories. Elements: {elements}",
    "deep in research": "Many tabs open, user is deep in research. Elements: {elements}",
    "minimal": "Very little screen content, user may be resting. Elements: {elements}",
    "idle": "Screen is empty, user may have stepped away.",
}


def build_vision_prompt(analysis: dict[str, Any]) -> str:
    """Build a prompt for the LLM to generate a vision-based quip."""
    activity = analysis.get("activity_label", "using computer")
    elements = analysis.get("element_summary", "")

    template = VISION_PROMPT_TEMPLATES.get(
        activity,
        "User screen status: {elements}",
    )
    prompt = template.format(elements=elements)
    prompt += "\nBased on the above screen info, generate a short quip (<=30 chars) matching character personality."
    return prompt
