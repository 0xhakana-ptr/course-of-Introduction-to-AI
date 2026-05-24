import os, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app"

# Check for any remaining references to old paths
patterns = [
    'chat_action',
    'services.chat_interface',
    'services.run_interface',
]

for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ('__pycache__',)]
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        with open(fp, 'r', encoding='utf-8') as fh:
            for i, line in enumerate(fh, 1):
                for pat in patterns:
                    if pat in line and 'noqa' not in line and 're-export' not in line and 'Compatibility' not in line:
                        rel = os.path.relpath(fp, base)
                        if pat == 'chat_action' and 'chat_action' in rel:
                            continue
                        if pat in ('services.run_interface', 'services.chat_interface') and ('import' not in line):
                            continue
                        if 'import' in line or 'from' in line:
                            print(f"OLD IMPORT: {rel}:{i}: {line.strip()[:120]}")

print("Done checking.")
