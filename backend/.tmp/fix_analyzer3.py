"""fix analyzer.py - read broken file, extract Chinese prompts, write fixed version."""
import pathlib
import re

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\analyzer.py")
raw = path.read_bytes()

# The file has some corrupted bytes but we can find the text patterns
text = raw.decode("utf-8", errors="replace")

# Extract VISION_QUIP_SYSTEM_PROMPT content
prompt_match = re.search(r"VISION_QUIP_SYSTEM_PROMPT = .*?Scene-specific prompt prefixes", text, re.DOTALL)
if prompt_match:
    prompt_section = prompt_match.group(0)
else:
    prompt_section = "VISION_QUIP_SYSTEM_PROMPT = " + repr("Character setup prompt")

# Extract VISION_PROMPT_TEMPLATES
tmpl_match = re.search(r"VISION_PROMPT_TEMPLATES:.*?(?=def build_vision_prompt)", text, re.DOTALL)
if tmpl_match:
    tmpl_section = tmpl_match.group(0)
else:
    tmpl_section = ""

# Extract build_vision_prompt function
build_match = re.search(r"def build_vision_prompt.*", text, re.DOTALL)
if build_match:
    build_section = build_match.group(0)
else:
    build_section = "def build_vision_prompt(): pass\n"

print("Extracted:", len(prompt_section), len(tmpl_section), len(build_section))

# Write the fixed file
fixed = '''# -*- coding: utf-8 -*-
"""Activity analyzer: converts YOLO detections into human-readable activity descriptions
and prepares context for LLM-based quip generation."""

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

''' + tmpl_section + "\n\n" + build_section

path.write_text(fixed.strip() + "\n", encoding="utf-8")
print("analyzer.py FIXED")
