import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\screenshot.py")
content = path.read_text("utf-8")
# Change: max_age = cfg.interval_seconds * 2.5  ->  * 10
old = "max_age = cfg.interval_seconds * 2.5"
new = "max_age = max(cfg.interval_seconds * 10, 300)  # tolerate up to 5min stale"
if old in content:
    content = content.replace(old, new)
    path.write_text(content, "utf-8")
    print("Fixed stale tolerance")
else:
    print("Pattern not found")
