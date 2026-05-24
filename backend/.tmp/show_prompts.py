import sys
sys.path.insert(0, r"D:\codeAIAGENT\cyber-waifu-vue\backend")

# 1. ONNX inference output
from PIL import Image
img = Image.open(r"D:\codeAIAGENT\cyber-waifu-vue\backend\.tmp_cache\vision_screenshots\screenshot_latest.png")
from app.vision.inference import run_inference, describe_detections, _ensure_ort
print("=== ONNX Inference Output ===")
print(f"ONNX loaded: {_ensure_ort()}")
detections = run_inference(img)
print(f"Raw detections ({len(detections)} items):")
for d in detections:
    print(f"  class={d['class_name']:15s} conf={d['confidence']:.3f}")
print(f"\nSummary: {describe_detections(detections)}")

# 2. Activity analysis output
from app.vision.analyzer import analyze_activity
analysis = analyze_activity(detections)
print(f"\n=== Activity Analysis ===")
for k, v in analysis.items():
    print(f"  {k}: {v}")

# 3. Prompt construction
from app.agent_workflow.roleplay import ROLEPLAY_SYSTEM_PROMPT
activity = analysis.get("activity_label", "unknown")
elements = analysis.get("element_summary", "")
mood_hint = analysis.get("mood_hint", "neutral")

vision_prompt = (
    f"[Screen] {elements}, activity: {activity}. "
    f"You are desktop sprite Unnamed, you peeked at the user screen. "
    f"React with ONE natural, cheeky quip (<=30 chars). "
    f'Output ONLY valid JSON: {{"quip": "<=30 char quip", "expression": "name"}}'
)

state_context = f"Screen: {elements}\nActivity: {activity}\nMood hint: {mood_hint}"

print(f"\n=== Prompt sent to LLM ===")
print(f"--- USER PROMPT ---\n{vision_prompt}\n")
print(f"--- SYSTEM PROMPT (first 500 chars) ---")
print(ROLEPLAY_SYSTEM_PROMPT[:500] + "...")
print(f"\n--- State context injected into system prompt ---")
print(state_context)
