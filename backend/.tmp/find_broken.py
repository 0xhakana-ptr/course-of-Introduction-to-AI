# Read roleplay.py and find lines with actual "?" marks (not encoding artifacts)
import sys
sys.stdout.reconfigure(encoding='utf-8')

fp = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py"
with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== Lines with literal '????' in roleplay.py ===")
for i, line in enumerate(lines, 1):
    if '????' in line and not line.strip().startswith('#'):
        print(f"L{i}: {line.rstrip()[:150]}")

print("\n=== Lines with literal '??~' ===")
for i, line in enumerate(lines, 1):
    if '??~' in line:
        print(f"L{i}: {line.rstrip()[:150]}")

print("\n=== Search for '??' in quoted strings (potential broken text) ===")
in_string = False
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    # Check if this line contains a string with multiple consecutive ??
    import re
    matches = re.findall(r'[\"\']([^\"\']*\?{2,}[^\"\']*)[\"\']', stripped)
    for m in matches:
        print(f"L{i}: '{m}'")
