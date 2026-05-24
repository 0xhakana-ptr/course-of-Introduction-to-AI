# -*- coding: utf-8 -*-
'''Vision module configuration.'''

from __future__ import annotations

import os
from pathlib import Path

# Model path (relative to project root)
_VISION_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _VISION_DIR.parents[1]  # backend/
_MODEL_PATH = _PROJECT_ROOT.parent / "vision" / "best.onnx"

# Screenshot cache directory
_CACHE_DIR = _VISION_DIR.parents[1] / ".tmp_cache" / "vision_screenshots"

# YOLOv8 class labels (from model metadata)
CLASS_NAMES: dict[int, str] = {
    0: "activewindow",
    1: "address bar",
    2: "folder",
    3: "menubar",
    4: "tab",
    5: "window",
}
NUM_CLASSES: int = len(CLASS_NAMES)

# Activity mapping: which class combos suggest which activity
# (class_name, min_count) tuples -> activity scenario text
ACTIVITY_PROFILES: list[tuple[list[tuple[str, int]], str, str]] = [
    # (required_detections, activity_label, mood_hint)
    ([("tab", 3), ("activewindow", 1)], "browsing", "neutral"),
    ([("activewindow", 1), ("menubar", 1)], "using an application", "neutral"),
    ([("folder", 2)], "managing files", "neutral"),
    ([("address bar", 1), ("folder", 1)], "navigating files", "neutral"),
    ([("tab", 5)], "deep in research", "focused"),
    ([("activewindow", 3)], "multitasking hard", "focused"),
]

class VisionConfig:
    def __init__(self) -> None:
        self.model_path: Path = _MODEL_PATH
        self.cache_dir: Path = _CACHE_DIR
        self.interval_seconds: int = int(
            os.getenv("VISION_INTERVAL_SECONDS", "60").strip() or "60"
        )
        self.enabled: bool = (
            os.getenv("VISION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.confidence_threshold: float = float(
            os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.4").strip() or "0.4"
        )
        self.quip_cooldown_seconds: int = int(
            os.getenv("VISION_QUIP_COOLDOWN_SECONDS", "120").strip() or "120"
        )
        self.max_cached_screenshots: int = int(
            os.getenv("VISION_MAX_CACHED_SCREENSHOTS", "10").strip() or "10"
        )


_config: VisionConfig | None = None


def get_vision_config() -> VisionConfig:
    global _config
    if _config is None:
        _config = VisionConfig()
    return _config
