import pathlib, re

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = path.read_bytes()
text = raw.decode("utf-8", errors="replace")

# Aggressive splitting: insert \n before every Python keyword
keywords = [
    r'(?<!\n)(class\s+\w+)',      # class declarations
    r'(?<!\n)(def\s+\w+)',        # function declarations  
    r'(?<!\n)(async\s+def\s+\w+)', # async def
    r'(?<!\n)(@\w+)',             # decorators
    r'(?<!\n)(# =====)',          # section comments
    r'(?<!\n)(# ---+)',           # section comments
    r'(?<!\n)(ROLEPLAY_SYSTEM_PROMPT\s*=)',  # constant
    r'(?<!\n)(CHAT_SYSTEM_PROMPT\s*=)',      # constant
    r'(?<!\n)(logger\s*=\s*)',    # logger assignment
    r'(?<!\n)(_session_mood\s*=\s*)', # module-level singleton
    r'(?<!\n)(roleplay_agent\s*=\s*)',  # singleton
]

for kw in keywords:
    text = re.sub(kw, r'\n\1', text, flags=re.MULTILINE)

# Fix the coding line
text = text.replace("# -*- \n", "# -*- ")
text = text.replace("\ncoding:\nutf-8 -*-", " coding: utf-8 -*-")

# Fix merged imports  
text = text.replace("annotationsimport ", "annotations\nimport ")
text = text.replace("}\nlogger", "}\n\nlogger")
text = text.replace('"""\nLayer 2:\nRoleplay Agent.', '"""\nLayer 2: Roleplay Agent.')

# Fix common merges: 'keyword' followed by next statement
for sep in [r'\)\s+(class\s)', r'\)\s+(def\s)', r':\s+(class\s)', r':\s+(def\s)']:
    text = re.sub(sep, r')\n\n\1', text)

path.write_text(text, "utf-8")
lines = text.split("\n")
print(f"Lines: {len(lines)}")
# Count classes and defs
classes = [l for l in lines if l.strip().startswith("class ")]
defs = [l for l in lines if l.strip().startswith("def ")]
print(f"Classes: {len(classes)}, Functions: {len(defs)}")
for c in classes[:5]:
    print(f"  {c.strip()[:80]}")
