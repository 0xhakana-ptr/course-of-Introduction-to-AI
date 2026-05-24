"""End-to-end vision pipeline test - runs every step and reports results."""
import sys, os, time, logging

# Setup
os.chdir(r"D:\codeAIAGENT\cyber-waifu-vue\backend")
sys.path.insert(0, ".")

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
print("=" * 60)
print("VISION PIPELINE END-TO-END TEST")
print("=" * 60)

# Step 1: Config
print("\n[1] Loading config...")
from app.vision.config import get_vision_config
cfg = get_vision_config()
print(f"    model_path = {cfg.model_path} (exists={cfg.model_path.exists()})")
print(f"    cache_dir = {cfg.cache_dir} (exists={cfg.cache_dir.exists()})")
print(f"    interval = {cfg.interval_seconds}s")
print(f"    enabled = {cfg.enabled}")
print(f"    confidence = {cfg.confidence_threshold}")
print(f"    cooldown = {cfg.quip_cooldown_seconds}s")

# Step 2: Screenshot
print("\n[2] Reading screenshot...")
from app.vision.screenshot import capture_screenshot
img = capture_screenshot()
if img is None:
    print("    FAILED: No screenshot file found")
    # Check what's on disk
    import pathlib
    ss_dir = pathlib.Path(cfg.cache_dir)
    print(f"    Directory contents: {list(ss_dir.glob('*')) if ss_dir.exists() else 'DIR NOT FOUND'}")
    sys.exit(1)
print(f"    OK: {img.size}, mode={img.mode}")

# Step 3: ONNX inference
print("\n[3] Running ONNX inference...")
from app.vision.inference import run_inference, describe_detections, _ensure_ort
ort_ok = _ensure_ort()
print(f"    ONNX loaded: {ort_ok}")
if not ort_ok:
    sys.exit(1)
detections = run_inference(img)
print(f"    Detections: {len(detections)} items")
print(f"    Summary: {describe_detections(detections)}")
for d in detections:
    print(f"      {d['class_name']}: conf={d['confidence']:.3f}")

# Step 4: Activity analysis
print("\n[4] Analyzing activity...")
from app.vision.analyzer import analyze_activity
analysis = analyze_activity(detections)
print(f"    has_content: {analysis.get('has_content')}")
print(f"    activity_label: {analysis.get('activity_label')}")
print(f"    element_summary: {analysis.get('element_summary')}")
print(f"    mood_hint: {analysis.get('mood_hint')}")
print(f"    is_duplicate: {analysis.get('is_duplicate')}")

if not analysis.get("has_content"):
    print("    SKIP: No meaningful content")
    sys.exit(0)
if analysis.get("is_duplicate"):
    print("    SKIP: Duplicate scene (cooldown)")
    sys.exit(0)

# Step 5: Roleplay Layer 2 - LLM call
print("\n[5] Calling Layer 2 RoleplayAgent.emit_vision_quip()...")
from app.agent_workflow.roleplay import roleplay_agent
from app.llm.client import llm_is_configured

print(f"    LLM configured: {llm_is_configured()}")

if not llm_is_configured():
    print("    FAILED: LLM not configured. Check .env file")
    sys.exit(1)

try:
    result = roleplay_agent.emit_vision_quip(analysis)
    print(f"    Result: {result}")
except Exception as e:
    print(f"    EXCEPTION: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("PIPELINE TEST COMPLETE")
