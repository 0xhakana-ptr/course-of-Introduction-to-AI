import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

def try_all_recoveries(text):
    """Try every possible encoding reversal and return best result."""
    results = []
    for enc in ['gbk', 'gb2312', 'gb18030', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            recovered = text.encode(enc).decode('utf-8')
            if recovered != text:
                cn = len(re.findall(r'[\u4e00-\u9fff]', recovered))
                results.append((enc, recovered, cn))
        except:
            pass
    return results

# Check specific lines from roleplay.py
fp = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py"
with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check lines around the ROLEPLAY_SYSTEM_PROMPT (line 27-90)
for i in range(26, min(95, len(lines))):
    line = lines[i].rstrip('\n\r')
    if not line.strip() or line.strip().startswith('#') or line.strip().startswith('"') == False:
        # Only check lines that look like string content
        if any(ord(c) > 127 for c in line) and not line.strip().startswith('#'):
            results = try_all_recoveries(line)
            if results:
                print(f"L{i+1}: RECOVERABLE")
                for enc, rec, cn in results[:1]:
                    print(f"  [{enc}] -> {rec[:120]}")
            else:
                # Check what's in the line
                high_chars = [f'U+{ord(c):04X}({c})' for c in line if ord(c) > 127][:5]
                print(f"L{i+1}: UNRECOVERABLE (high chars: {high_chars})")
                print(f"  content: {line[:120]}")
