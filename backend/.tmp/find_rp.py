import pathlib
# Search for any roleplay.py or roleplay_recovered in the project
base = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue")
for f in base.rglob("roleplay*.py"):
    print(f"  {f} ({f.stat().st_size} bytes)")
