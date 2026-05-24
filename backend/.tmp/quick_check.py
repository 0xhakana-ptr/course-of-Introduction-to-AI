import pathlib
p = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = p.read_bytes()
# Check if file ends properly
ends_ok = raw.rstrip().endswith(b"roleplay_agent = RoleplayAgent()")
print(f"Ends OK: {ends_ok}")
print(f"Size: {len(raw)} bytes")
# Can it be imported?
import importlib.util, sys
spec = importlib.util.spec_from_file_location("roleplay", str(p))
if spec:
    try:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["roleplay"] = mod
        spec.loader.exec_module(mod)
        print("IMPORT: OK")
        print("emit_vision_quip:", hasattr(mod.roleplay_agent, "emit_vision_quip"))
    except Exception as e:
        print(f"IMPORT ERROR: {type(e).__name__}: {e}")
