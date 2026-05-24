import pathlib

# Read the existing file to get the Chinese prompt templates (they were working before)
orig = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\__pycache__\analyzer.cpython-313.pyc")
# Can't read .pyc easily. Let me just check what the backup situation is.

# Better approach: read the original from git
import subprocess
result = subprocess.run(
    ["git", "show", "HEAD:backend/app/vision/analyzer.py"],
    capture_output=True, text=True, cwd=r"D:\codeAIAGENT\cyber-waifu-vue"
)
if result.returncode == 0:
    old_content = result.stdout
    # Now modify: replace the _cooldown, analyze_activity part while keeping Chinese prompts
    lines = old_content.split("\n")
    new_lines = []
    in_header = True
    for i, line in enumerate(lines):
        if line.startswith("_cooldown: dict") or line.startswith("_cooldown ="):
            # Replace cooldown section
            new_lines.append("_cooldown: OrderedDict[str, float] = OrderedDict()")
            new_lines.append("_COOLDOWN_MAX_SIZE = 200")
            new_lines.append("")
            new_lines.append("")
            new_lines.append("def _cooldown_prune() -> None:")
            new_lines.append('    """Evict oldest entries when cooldown cache exceeds max size."""')
            new_lines.append("    while len(_cooldown) > _COOLDOWN_MAX_SIZE:")
            new_lines.append("        _cooldown.popitem(last=False)")
            # Skip old cooldown-related lines
            skip = True
            continue
        if line.startswith("def analyze_activity"):
            skip = False
        if line.startswith("    fingerprint") and "md5" in line:
            # Add move_to_end + prune after _cooldown[fingerprint] = now
            # We'll handle this differently
            pass
        new_lines.append(line)
    print("Lines:", len(new_lines))
else:
    print("Git failed:", result.stderr[:200])
