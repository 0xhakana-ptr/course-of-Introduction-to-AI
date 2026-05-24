# -*- coding: utf-8 -*-
'''YOLOv8 ONNX inference for desktop UI element detection.'''

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .config import CLASS_NAMES, NUM_CLASSES, get_vision_config

logger = logging.getLogger(__name__)

# Lazy-loaded ONNX Runtime session
_ort_session: Any = None
_ort_available: bool | None = None


def _ensure_ort() -> bool:
    '''Check if onnxruntime is available. Returns True if ready.'''
    global _ort_available, _ort_session
    if _ort_available is True and _ort_session is not None:
        return True
    if _ort_available is False:
        return False

    try:
        import onnxruntime as ort
        cfg = get_vision_config()
        if not cfg.model_path.exists():
            logger.warning("Vision model not found at %s", cfg.model_path)
            _ort_available = False
            return False
        _ort_session = ort.InferenceSession(
            str(cfg.model_path),
            providers=["CPUExecutionProvider"],
        )
        _ort_available = True
        logger.info("ONNX Runtime loaded, model: %s", cfg.model_path)
        return True
    except ImportError:
        logger.warning("onnxruntime not installed, vision inference disabled")
        _ort_available = False
        return False
    except Exception as exc:
        logger.error("Failed to load ONNX model: %s", exc)
        _ort_available = False
        return False


def preprocess_image(image: Image.Image, target_size: tuple[int, int] = (640, 640)) -> np.ndarray:
    '''Resize, normalize, and prepare image for YOLOv8 inference.

    Returns: numpy array of shape (1, 3, 640, 640) with float32 values in [0, 1].
    '''
    img = image.convert("RGB").resize(target_size, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0  # normalize to [0, 1]
    arr = np.transpose(arr, (2, 0, 1))  # HWC -> CHW
    arr = np.expand_dims(arr, axis=0)  # add batch dim
    return arr.astype(np.float32)


def run_inference(image: Image.Image) -> list[dict[str, object]]:
    '''Run YOLOv8 inference on a PIL image.

    Returns list of detections with {class_name, confidence, bbox}.
    '''
    if not _ensure_ort():
        return []

    cfg = get_vision_config()
    input_tensor = preprocess_image(image)

    input_name = _ort_session.get_inputs()[0].name
    outputs = _ort_session.run(None, {input_name: input_tensor})
    raw = outputs[0]  # shape: (1, 10, 8400)

    return _parse_yolo_output(raw, cfg.confidence_threshold)


def _parse_yolo_output(
    raw: np.ndarray,
    confidence_threshold: float,
) -> list[dict[str, object]]:
    '''Parse YOLOv8 raw output into filtered detections.

    raw shape: (1, 4+NUM_CLASSES, 8400) = (1, 10, 8400)
    Channels layout: [cx, cy, w, h, class_0, ..., class_5]

    We use a simplified approach: find max class score per prediction,
    filter by threshold. No full grid decoding needed for activity analysis.
    '''
    # Transpose to (8400, 10)
    preds = raw[0].T  # shape: (8400, 10)

    bbox = preds[:, :4]          # (8400, 4)
    class_scores = preds[:, 4:]  # (8400, 6)

    # Find max class index and confidence per prediction
    max_indices = np.argmax(class_scores, axis=1)       # (8400,)
    max_confidences = np.max(class_scores, axis=1)      # (8400,)

    # Filter by threshold
    mask = max_confidences >= confidence_threshold
    indices = max_indices[mask]
    confidences = max_confidences[mask]
    boxes = bbox[mask]

    detections: list[dict[str, object]] = []
    for i in range(len(indices)):
        class_id = int(indices[i])
        if class_id not in CLASS_NAMES:
            continue
        detections.append({
            "class_name": CLASS_NAMES[class_id],
            "class_id": class_id,
            "confidence": float(confidences[i]),
            "bbox": boxes[i].tolist(),
        })

    return detections


def describe_detections(detections: list[dict[str, object]]) -> str:
    '''Generate a short text summary of detections.

    Example: "1 activewindow, 3 tabs, 1 menubar"
    '''
    if not detections:
        return "no UI elements detected"

    from collections import Counter
    counts = Counter(d["class_name"] for d in detections)

    if not counts:
        return "no recognizable UI elements"

    parts = [f"{count} {name}" for name, count in counts.most_common(5)]
    return ", ".join(parts)
