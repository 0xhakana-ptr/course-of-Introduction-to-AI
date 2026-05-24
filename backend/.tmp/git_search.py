import subprocess, pathlib
os.chdir(r"D:\codeAIAGENT\cyber-waifu-vue")

# Try git stash list
result = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
print(f"Stash: {result.stdout[:200]}")

# Try git reflog
result = subprocess.run(["git", "reflog", "--oneline", "-5"], capture_output=True, text=True)
print(f"Reflog: {result.stdout[:300]}")

# Try git show from earlier commit
result = subprocess.run(["git", "diff", "HEAD", "--", "backend/app/agent_workflow/roleplay.py"], capture_output=True, text=True)
print(f"Diff size: {len(result.stdout)}")
if len(result.stdout) < 500:
    print(result.stdout)
