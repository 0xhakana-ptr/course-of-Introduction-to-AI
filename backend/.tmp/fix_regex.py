import re

path = r'D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\monitor.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The correct regex line
correct_line = "        m = re.search(\n            r'\\{\\s*\"quip\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"\\s*,\\s*\"expression\"\\s*:\\s*\"([^\"]*)\"\\s*\\}',\n            raw, re.DOTALL,\n        )\n"

# Find the mangled section and replace
lines = content.split('\n')
new_lines = []
skip_until_match = False
i = 0
while i < len(lines):
    line = lines[i]
    if 'm = re.search(' in line and "''" in line:
        # Find the end of this statement (closing paren)
        new_lines.append('        m = re.search(')
        new_lines.append("            r'\\{\\s*\"quip\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"\\s*,\\s*\"expression\"\\s*:\\s*\"([^\"]*)\"\\s*\\}',")
        new_lines.append('            raw, re.DOTALL,')
        new_lines.append('        )')
        i += 1
        # Skip until we find the closing paren line
        while i < len(lines) and not lines[i].strip().startswith('raw,') and not lines[i].strip().startswith(')'):
            i += 1
        i += 1
        continue
    new_lines.append(line)
    i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

# Verify
with open(path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 're.search' in line:
            print(f'Line {i}: {line.rstrip()[:120]}')
print('Done')
