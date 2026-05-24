import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = path.read_bytes()
first_500 = raw[:500]
print(repr(first_500))
# Check for \r\n 
has_crlf = b"\r\n" in raw
has_lf = b"\n" in raw
print(f"has CRLF: {has_crlf}, has LF: {has_lf}")
