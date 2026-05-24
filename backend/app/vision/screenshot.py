# -*- coding: utf-8 -*-
'''Screenshot reader: reads PNG screenshots saved by Electron desktopCapturer.

Electron writes `screenshot_latest.png` via an atomic rename (tmp -> final).
Python reads it for ONNX inference.
'''

from __future__ import annotations

import logging
import time
from pathlib import Path

from PIL import Image

from .config import get_vision_config

logger = logging.getLogger(__name__)


def capture_screenshot() -> Image.Image | None:
    '''Read the latest screenshot from disk (written by Electron).

    Returns None if the file doesn't exist, is stale, or can't be read.
    '''
    cfg = get_vision_config()
    path = cfg.cache_dir / "screenshot_latest.png"

    if not path.exists():
        logger.debug("No screenshot file at %s", path)
        return None

    # Check file freshness: skip if older than 2 cycles
    max_age = max(cfg.interval_seconds * 10, 300)  # tolerate up to 5min stale
    try:
        mtime = path.stat().st_mtime
        age = time.time() - mtime
        if age > max_age:
            logger.info("Screenshot is stale (age=%.0fs > %.0fs), skipping", age, max_age)
            return None
    except OSError:
        return None

    try:
        img = Image.open(path)
        img.load()  # force full read
        logger.debug("Read screenshot: %s (%dx%d)", path, img.width, img.height)
        return img
    except Exception as exc:
        logger.warning("Failed to read screenshot: %s", exc)
        return None
