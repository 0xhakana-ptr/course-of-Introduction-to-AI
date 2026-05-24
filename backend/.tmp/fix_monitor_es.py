import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\vision\monitor.py")
content = path.read_text("utf-8")
old1 = 'event_source="vision"'
new1 = 'event_source="system"'
if old1 in content:
    content = content.replace(old1, new1)
    path.write_text(content, "utf-8")
    print("Fixed monitor.py")
else:
    print("Not found in monitor.py")
