import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app"
all_ok = True
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache')]
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        with open(fp, 'r', encoding='utf-8') as fh:
            lines = fh.readlines()
        for i, line in enumerate(lines, 1):
            # Check for 3+ consecutive ? in string literals
            if re.search(r'["\']([^"\']*\?{3,}[^"\']*)["\']', line):
                stripped = line.strip()
                if not stripped.startswith('#'):
                    rel = os.path.relpath(fp, base)
                    print(f"BROKEN: {rel}:{i}: {stripped[:120]}")
                    all_ok = False

if all_ok:
    print("ALL CLEAN - No broken Chinese text found!")
