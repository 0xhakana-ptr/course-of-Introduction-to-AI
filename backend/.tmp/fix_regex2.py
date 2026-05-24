import re

path = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\monitor.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the mangled regex line by line
lines = content.split("\n")
new = []
for line in lines:
    if "r'" in line and "quip" in line and "expression" in line and "re.search" not in line:
        new.append('            r\'\{\\s*"quip"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"\\s*,\\s*"expression"\\s*:\\s*"([^"]*)"\\s*\}\',')
    else:
        new.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(new))

# Verify
with open(path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "re.search" in line or ("quip" in line and "expression" in line and "re.search" not in line):
            print(f"Line {i}: {line.rstrip()[:120]}")
