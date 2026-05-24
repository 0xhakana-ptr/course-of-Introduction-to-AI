import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

def recover_line(line):
    """Try GBK->UTF-8 recovery. If it produces real Chinese, return recovered text."""
    stripped = line.rstrip('\n\r')
    if not stripped:
        return stripped
    try:
        recovered = stripped.encode('gbk').decode('utf-8')
        # Check if recovered text has more Chinese chars than before
        orig_cn = len(re.findall(r'[\u4e00-\u9fff]', stripped))
        rec_cn = len(re.findall(r'[\u4e00-\u9fff]', recovered))
        if rec_cn > 0 and recovered != stripped:
            return recovered
    except:
        pass
    return stripped

files = [
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\engine.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\intent.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\actions\run.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\formatters.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\api\error_handlers.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\messaging\message_sender.py",
]

for fp in files:
    rel = os.path.relpath(fp, r"D:\codeAIAGENT\cyber-waifu-vue\backend")
    with open(fp, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    changed = 0
    for i, line in enumerate(lines):
        recovered = recover_line(line)
        if recovered != line.rstrip('\n\r'):
            changed += 1
    
    if changed > 0:
        print(f"{rel}: {changed} lines recoverable")
    else:
        # Check if file even has CJK chars
        content = ''.join(lines)
        cjk = len(re.findall(r'[\u4e00-\u9fff]', content))
        print(f"{rel}: {changed} lines changed, {cjk} CJK chars in file")
