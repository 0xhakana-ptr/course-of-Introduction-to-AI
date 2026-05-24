path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Check function-level structure by tracking indentation
lines = content.split("\n")
depth = 0
issues = []
# Only look at script section
in_script = False
for i, line in enumerate(lines):
    if "<script" in line:
        in_script = True
        continue
    if "</script>" in line:
        in_script = False
        continue
    if not in_script:
        continue
    
    stripped = line.strip()
    # Count braces
    for ch in stripped:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    
    if depth < 0:
        issues.append(f"Line {i+1}: depth went negative")
        depth = 0

if issues:
    for issue in issues[:10]:
        print(issue)
else:
    print(f"No negative depth issues. Final depth: {depth}")
