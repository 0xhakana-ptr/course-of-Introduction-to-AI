"""Rewrite monitor.py _emit_vision_quip to use roleplay layer."""
import pathlib

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\monitor.py")
content = path.read_text("utf-8")

# Find and replace the _emit_vision_quip method
old_method_start = content.find("    async def _emit_vision_quip(self, analysis):")
old_method_end = content.find("\n\nvision_monitor = VisionMonitor()")

if old_method_start > 0 and old_method_end > old_method_start:
    new_method = '''    async def _emit_vision_quip(self, analysis):
        """Delegate to Layer 2 RoleplayAgent for character-aware quip generation.

        The vision observation (activity, elements, mood) is injected into
        the roleplay layer so the character reacts naturally to the screen.
        """
        try:
            from ..agent_workflow.roleplay import roleplay_agent
            await asyncio.to_thread(roleplay_agent.emit_vision_quip, analysis)
        except Exception:
            logger.exception("Vision quip generation failed")
'''
    content = content[:old_method_start] + new_method + content[old_method_end:]
    path.write_text(content, "utf-8")
    print("monitor.py _emit_vision_quip rewritten")
else:
    print(f"Markers not found: start={old_method_start}, end={old_method_end}")
    # Print surrounding content
    for i, line in enumerate(content.split("\n")):
        if "_emit_vision_quip" in line:
            print(f"Line {i+1}: {line[:120]}")
        if "vision_monitor" in line and "VisionMonitor" in line:
            print(f"Line {i+1}: {line[:120]}")
