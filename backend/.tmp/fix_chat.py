fp = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\services\chat.py"
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'assistant_output = result.error or "???????????????"'
new = 'assistant_output = result.error or "抱歉，出了一点问题，请再试一次。"'

if old in content:
    content = content.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: services/chat.py fixed!")
else:
    print("Pattern not found, checking...")
    # Find it
    import re
    for m in re.finditer(r'[^"]*\?{5,}[^"]*', content):
        print(f"  Found: {m.group()[:100]}...")
