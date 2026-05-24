import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
lines = path.read_text("utf-8", errors="replace").split("\n")
# Show lines around 441
for i in range(max(0, 435), min(len(lines), 450)):
    line = lines[i]
    if "\ufffd" in line or "lines_list" in line or "append" in line:
        print(f"Line {i+1}: {line[:200]}")
# Count corrupted lines
corrupted = sum(1 for l in lines if "\ufffd" in l)
print(f"Corrupted lines: {corrupted}")
