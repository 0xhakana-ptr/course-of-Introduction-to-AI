import subprocess, pathlib
result = subprocess.run(
    ["git", "show", "HEAD:backend/app/agent_workflow/roleplay.py"],
    capture_output=True, cwd=r"D:\codeAIAGENT\cyber-waifu-vue"
)
out = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
out.write_bytes(result.stdout)
print(f"Written {len(result.stdout)} bytes")

# Verify import
import sys
sys.path.insert(0, r"D:\codeAIAGENT\cyber-waifu-vue\backend")
from app.agent_workflow.roleplay import roleplay_agent, RoleplayMood
print("IMPORT OK")
