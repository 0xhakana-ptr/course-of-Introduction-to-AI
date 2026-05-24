import sys, re, os
sys.stdout.reconfigure(encoding='utf-8')

def try_recover(text):
    """Try multiple recovery strategies for mojibake Chinese text."""
    strategies = []
    
    # Strategy 1: GBK reversal (UTF-8 bytes decoded as GBK)
    try:
        recovered = text.encode('gbk').decode('utf-8')
        if recovered != text:
            strategies.append(('gbk->utf8', recovered))
    except:
        pass
    
    # Strategy 2: Latin-1 reversal
    try:
        recovered = text.encode('latin-1').decode('utf-8')
        if recovered != text:
            strategies.append(('latin1->utf8', recovered))
    except:
        pass
    
    # Strategy 3: cp1252 reversal
    try:
        recovered = text.encode('cp1252').decode('utf-8')
        if recovered != text:
            strategies.append(('cp1252->utf8', recovered))
    except:
        pass
    
    return strategies

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def is_garbled(text):
    """Heuristic: if text has many high-codepoint chars but no CJK, it's likely garbled."""
    if not text.strip():
        return False
    # If it has real Chinese characters, it's probably not garbled
    if has_chinese(text):
        return False
    # Check for high Unicode chars (above U+2000) that aren't CJK
    high_chars = [c for c in text if ord(c) > 0x2000 and not (0x4e00 <= ord(c) <= 0x9fff)]
    return len(high_chars) > len(text) * 0.3

files_to_check = [
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\engine.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\intent.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\actions\run.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\formatters.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\api\error_handlers.py",
    r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\messaging\message_sender.py",
]

for filepath in files_to_check:
    if not os.path.exists(filepath):
        print(f"\nFILE NOT FOUND: {filepath}")
        continue
    
    rel = os.path.relpath(filepath, r"D:\codeAIAGENT\cyber-waifu-vue\backend")
    print(f"\n{'='*60}")
    print(f"FILE: {rel}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    garbled_count = 0
    recoverable = 0
    for i, line in enumerate(lines, 1):
        if is_garbled(line):
            garbled_count += 1
            strategies = try_recover(line.strip())
            if strategies:
                recoverable += 1
                for strat_name, recovered in strategies:
                    print(f"  L{i}: [{strat_name}] {recovered[:100]}")
            else:
                # Show first 60 chars of the garbled line
                preview = line.strip()[:80]
                print(f"  L{i}: [UNRECOVERABLE] {preview}")
    
    print(f"  Summary: {garbled_count} garbled lines, {recoverable} recoverable, {garbled_count - recoverable} unrecoverable")
