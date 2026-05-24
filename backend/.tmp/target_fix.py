import pathlib

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
text = path.read_text("utf-8")

# Fix critical joining issues
fixes = [
    ("# -*- \ncoding:\nutf-8 -*-", "# -*- coding: utf-8 -*-"),
    ('"""\nLayer 2:\nRoleplay Agent.', '"""Layer 2: Roleplay Agent.'),
    ("work,\nwraps results", "work,\nwraps results"),
    ("llm_is_configuredlogger", "llm_is_configured\nlogger"),
    ("# ===== Inlined from", "\n# ===== Inlined from"),
    ("# Personality Definition", "\n# Personality Definition"),
    ("ROLEPLAY_SYSTEM_PROMPT = ", "\nROLEPLAY_SYSTEM_PROMPT = "),
    ("CHAT_SYSTEM_PROMPT = ", "\nCHAT_SYSTEM_PROMPT = "),
]

for old, new in fixes:
    if old in text:
        text = text.replace(old, new)

path.write_text(text, "utf-8")
print("Applied targeted fixes")
