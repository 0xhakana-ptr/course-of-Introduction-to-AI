import pathlib, marshal, dis, types, sys

# Find the newest valid pyc for roleplay
pydir = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\__pycache__")
pycs = sorted(pydir.glob("roleplay.cpython-*.pyc"), key=lambda p: p.stat().st_mtime, reverse=True)
print(f"Found {len(pycs)} pyc files")
for pyc in pycs:
    print(f"  {pyc.name} ({pyc.stat().st_mtime})")
    # Try to load it
    try:
        with open(pyc, "rb") as f:
            magic = f.read(4)
            flags = f.read(4)
            timestamp = f.read(4)
            size = f.read(4)
            code = marshal.load(f)
        # Check if it has our emit_vision_quip
        for const in code.co_consts:
            if isinstance(const, types.CodeType) and const.co_name == "emit_vision_quip":
                print(f"    HAS emit_vision_quip")
        print(f"    code object names: {[c for c in code.co_names if 'emit' in c or 'vision' in c]}")
    except Exception as e:
        print(f"    Error: {e}")
