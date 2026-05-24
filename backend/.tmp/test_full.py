import sys, logging
sys.path.insert(0, r"D:\codeAIAGENT\cyber-waifu-vue\backend")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from PIL import Image
img = Image.open(r"D:\codeAIAGENT\cyber-waifu-vue\backend\.tmp_cache\vision_screenshots\screenshot_latest.png")
img.load()
print(f"Image: {img.size}")

from app.vision.inference import run_inference, describe_detections, _ensure_ort
print(f"ONNX: {_ensure_ort()}")
detections = run_inference(img)
print(f"Detections: {len(detections)} - {describe_detections(detections)}")

from app.vision.analyzer import analyze_activity
a = analyze_activity(detections)
print(f"Analysis: content={a.get('has_content')}, activity={a.get('activity_label')}, dup={a.get('is_duplicate')}")

if a.get("has_content") and not a.get("is_duplicate"):
    print("--- Calling Layer 2 ---")
    from app.agent_workflow.roleplay import roleplay_agent
    from app.llm.client import llm_is_configured
    print(f"LLM configured: {llm_is_configured()}")
    r = roleplay_agent.emit_vision_quip(a)
    print(f"Roleplay result: {r}")
else:
    print("Skipped LLM call")
print("DONE")
