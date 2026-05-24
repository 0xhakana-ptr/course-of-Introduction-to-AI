import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app"
files_to_check = [
    "agent_workflow/roleplay.py",
    "agent_workflow/engine.py",
    "agent_workflow/intent.py",
    "agent_workflow/actions/run.py",
    "agent_workflow/formatters.py",
    "agent_workflow/output/node_events.py",
    "agent_workflow/output/action_events.py",
    "agent_workflow/output/completion_events.py",
    "agent_workflow/output/text.py",
    "api/error_handlers.py",
    "messaging/message_sender.py",
    "messaging/queue.py",
    "services/character.py",
    "services/run.py",
    "services/chat.py",
    "core/config.py",
    "core/text_utils.py",
    "schemas.py",
]

for rel in files_to_check:
    fp = os.path.join(base, rel)
    if not os.path.exists(fp):
        print(f"NOT FOUND: {rel}")
        continue
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find strings containing 3+ consecutive ? characters
    broken = re.findall(r'["\']([^"\']*\?{3,}[^"\']*)["\']', content)
    if broken:
        print(f"\n{rel}:")
        for b in broken[:10]:
            print(f"  '{b}'")
