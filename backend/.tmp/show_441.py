import pathlib
p = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
lines = p.read_bytes().split(b"\n")
for i in range(438, min(445, len(lines))):
    print(f"Line {i+1}: {lines[i][:120]}")
