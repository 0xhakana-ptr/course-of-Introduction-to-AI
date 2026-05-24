import pathlib, re

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = path.read_bytes()
text = raw.decode("utf-8", errors="replace")

# Fix 1: broken coding line
text = text.replace("# -*- coding:\n    utf-8 -*-", "# -*- coding: utf-8 -*-")

# Fix 2: add newlines before key import keywords
text = re.sub(r'(?<=[a-zA-Z_])import\s', r'\nimport ', text)
text = re.sub(r'(?<=[a-zA-Z_])from\s', r'\nfrom ', text)

# Fix 3: add newline between # comments and subsequent code
text = re.sub(r'(#[^\n]*?)(?=[a-zA-Z_])', r'\1\n', text)

# Fix 4: add newlines after closing triple quote
text = re.sub(r'(""")(?=[a-zA-Z_#@])', r'\1\n', text)

# Fix 5: add newline between : and subsequent code at module level
text = re.sub(r':\s+(?=[a-zA-Z_])', r':\n', text)

# Write
path.write_text(text, "utf-8")
lines = text.split("\n")
print(f"Fixed: {len(lines)} lines")
print("First 20 lines:")
for l in lines[:20]:
    print(f"  {l[:120]}")
