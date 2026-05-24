import subprocess, os
os.chdir(r"D:\codeAIAGENT\cyber-waifu-vue")
result = subprocess.run(["git", "diff", "HEAD", "--", "backend/app/agent_workflow/roleplay.py"], capture_output=True, text=True)
print(f"Diff: {len(result.stdout)} chars")
if result.stdout:
    # Show first 500 chars
    print(result.stdout[:500])
else:
    # No diff = file matches HEAD? Check status
    result2 = subprocess.run(["git", "status", "--short", "backend/app/agent_workflow/roleplay.py"], capture_output=True, text=True)
    print(f"Status: {result2.stdout}")
