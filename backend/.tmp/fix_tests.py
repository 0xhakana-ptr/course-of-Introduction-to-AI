import os

base = r"D:\codeAIAGENT\cyber-waifu-vue\backend\tests"
fixes = {
    'from backend.app.services.chat_action.types import ChatServiceResult': 'from backend.app.services.chat import ChatServiceResult',
    'from backend.app.services.chat_action.intent import detect_intent': 'from backend.app.agent_workflow.intent import detect_intent',
    'from backend.app.services.character_action.events import CHARACTER_EVENTS': 'from backend.app.services.character import CHARACTER_EVENTS',
    'from backend.app.services.chat_action import': 'from backend.app.services.chat import',
    'from backend.app.services.character_action': 'from backend.app.services.character',
}

for root, dirs, files in os.walk(base):
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()
        changed = False
        for old, new in fixes.items():
            if old in content:
                content = content.replace(old, new)
                changed = True
                rel = os.path.relpath(fp, base)
                print(f"Fixed: {rel}: {old[:60]}...")
        if changed:
            with open(fp, 'w', encoding='utf-8') as fh:
                fh.write(content)

print("\nTest import fixes complete!")
