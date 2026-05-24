import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = path.read_bytes()
text = raw.decode("utf-8", errors="replace")
lines = text.split("\n")
print(f"Lines: {len(lines)}")
print(f"RoleplayMood: {'class RoleplayMood' in text}")
print(f"roleplay_agent: {'roleplay_agent = RoleplayAgent()' in text}")
print(f"emit_vision_quip: {'emit_vision_quip' in text}")
