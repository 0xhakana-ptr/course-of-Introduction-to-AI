import pathlib, re

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = path.read_bytes()
text = raw.decode("utf-8", errors="replace")

# Strategy: insert \n before key Python tokens
# 1. Before class/def at top level
text = re.sub(r'(?<=\S)\s+(class\s+\w+|def\s+\w+|async\s+def\s+\w+|@\w+)', r'\n\n\1', text)
# 2. Before # comments
text = re.sub(r'\s+(#[^\n]*)', r'\n\1', text)
# 3. After triple quotes
text = re.sub(r'(""")(?!\s*\n)', r'\1\n', text)
# 4. Before triple quotes
text = re.sub(r'(?<!\n)(""")', r'\n\1', text)
# 5. After colon + space -> newline + indent (for function/class bodies)
text = re.sub(r':\s+(?=[a-z_\(\"#])', r':\n    ', text)
# 6. Newline after closing parentheses at statement level
text = re.sub(r'\)\s+(?=[a-z_@#])', r')\n', text)

# Write back
path.write_text(text, "utf-8")
lines = text.split("\n")
print(f"Fixed: {len(lines)} lines")
# Print last few lines
for l in lines[-5:]:
    print(l[:100])
