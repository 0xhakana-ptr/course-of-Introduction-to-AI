# Use uncompyle6 or pycdc if available
import subprocess, pathlib

# Try pip install uncompyle6 quick
result = subprocess.run(
    ["pip", "install", "uncompyle6", "-q"],
    capture_output=True, text=True, timeout=30
)
print(f"pip result: {result.returncode}")

if result.returncode == 0:
    import uncompyle6
    pyc = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\__pycache__\roleplay.cpython-311.pyc")
    out = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay_recovered.py")
    with open(pyc, "rb") as fi, open(out, "w", encoding="utf-8") as fo:
        uncompyle6.decompile_file(fi, fo)
    content = out.read_text("utf-8")
    lines = content.split("\n")
    print(f"Recovered: {len(lines)} lines")
    for l in lines[:5]:
        print(l[:100])
else:
    print("uncompyle6 not available, trying alternative...")
