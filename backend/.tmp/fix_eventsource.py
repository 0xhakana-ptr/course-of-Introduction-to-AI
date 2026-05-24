"""Fix event_source="vision" to "system" in roleplay.py"""
import pathlib

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
content = path.read_text("utf-8")

# Fix all occurrences of event_source="vision" -> "system"
content = content.replace('event_source="vision"', 'event_source="system"')
content = content.replace("event_source='vision'", "event_source='system'")

path.write_text(content, "utf-8")
print("Fixed event_source in roleplay.py")
