path = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\engine.py"
with open(path, encoding="utf-8-sig") as f:
    content = f.read()

old = "result.final_state if hasattr(result, 'final_state') else {}"
new = "result.state if hasattr(result, 'state') else {}"

if old in content:
    content = content.replace(old, new)
    print("FIXED: result.final_state -> result.state!")
else:
    print("NOT FOUND")

with open(path, "w", encoding="utf-8-sig") as f:
    f.write(content)
