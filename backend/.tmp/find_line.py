import pathlib
p = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
lines = p.read_bytes().split(b"\n")
# Show lines 435-450 as raw bytes
for i in range(434, min(450, len(lines))):
    line = lines[i]
    try:
        decoded = line.decode("utf-8")
        if "\ufffd" in decoded:
            print(f"Line {i+1} CORRUPTED: {decoded[:100]}")
    except:
        print(f"Line {i+1} BINARY: {line[:80]}")
