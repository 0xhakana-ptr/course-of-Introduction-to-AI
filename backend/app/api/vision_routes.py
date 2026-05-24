# -*- coding: utf-8 -*-
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/vision", tags=["vision"])


class VisionTestResponse(BaseModel):
    ok: bool
    steps: list[dict]


@router.post("/test")
async def vision_test():
    """Manually trigger one vision tick and return full diagnostic."""
    steps = []

    try:
        from ..vision.screenshot import capture_screenshot
        from ..vision.inference import run_inference, describe_detections, _ensure_ort
        from ..vision.analyzer import analyze_activity

        # Step 1: screenshot
        img = capture_screenshot()
        steps.append({"step": "screenshot", "ok": img is not None, "detail": str(img.size) if img else "no file"})
        if not img:
            return {"ok": False, "steps": steps}

        # Step 2: ONNX
        ort_ok = _ensure_ort()
        steps.append({"step": "onnx_loaded", "ok": ort_ok})
        if not ort_ok:
            return {"ok": False, "steps": steps}

        detections = run_inference(img)
        steps.append({"step": "inference", "ok": True, "detail": f"{len(detections)} detections: {describe_detections(detections)}"})

        # Step 3: analysis
        analysis = analyze_activity(detections)
        steps.append({"step": "analysis", "ok": True, "detail": {
            "has_content": analysis.get("has_content"),
            "activity_label": analysis.get("activity_label"),
            "element_summary": analysis.get("element_summary"),
            "is_duplicate": analysis.get("is_duplicate"),
            "mood_hint": analysis.get("mood_hint"),
        }})

        if not analysis.get("has_content"):
            return {"ok": False, "steps": steps}

        if analysis.get("is_duplicate"):
            steps.append({"step": "skipped", "detail": "duplicate scene (cooldown)"})
            return {"ok": False, "steps": steps}

        # Step 4: LLM call
        from ..llm.client import call_llm_sync, llm_is_configured
        if not llm_is_configured():
            steps.append({"step": "llm", "ok": False, "detail": "LLM not configured"})
            return {"ok": False, "steps": steps}

        from ..vision.analyzer import build_vision_prompt, VISION_QUIP_SYSTEM_PROMPT
        prompt = build_vision_prompt(analysis)
        steps.append({"step": "prompt", "ok": True, "detail": prompt[:200]})

        result = call_llm_sync(prompt=prompt, context=None, system_prompt=VISION_QUIP_SYSTEM_PROMPT, temperature=0.85, max_tokens=120)
        steps.append({"step": "llm_call", "ok": result.ok, "detail": (result.output or result.error or "")[:300]})

        if not result.ok:
            return {"ok": False, "steps": steps}

        # Step 5: parse + send
        from ..vision.monitor import VisionMonitor
        vm = VisionMonitor()
        parsed = vm._parse_quip_json(result.output)
        steps.append({"step": "parse", "ok": parsed is not None, "detail": str(parsed)[:200] if parsed else "parse failed"})

        if parsed:
            from ..messaging.message_sender import message_sender
            quip = str(parsed.get("quip", "")).strip()
            expression = str(parsed.get("expression", "neutral")).strip()
            if quip:
                message_sender.send_quip(content=quip, node_name="vision_test", priority="high", duration=5000,
                    metadata={"event_type": "vision.test", "event_source": "vision_test"})
                message_sender.send_expression(expression=expression, node_name="vision_test",
                    intensity=0.85, duration=4000, transition="smooth", mode="set")
                steps.append({"step": "sent", "ok": True, "detail": f"quip={quip}, expr={expression}"})
            else:
                steps.append({"step": "empty_quip", "ok": False})

        return {"ok": True, "steps": steps}

    except Exception as exc:
        steps.append({"step": "error", "ok": False, "detail": str(exc)})
        return {"ok": False, "steps": steps}
