import pathlib, ast

path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
raw = path.read_bytes()
text = raw.decode("utf-8", errors="replace")

# Try to parse with ast and unparse
try:
    tree = ast.parse(text)
    new_text = ast.unparse(tree)
    # Add the coding header and imports that ast strips
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"AST unparse: {len(new_text.split(chr(10)))} lines")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    # Show context around error
    lines = text.split("\n")
    lineno = e.lineno - 1
    if 0 <= lineno < len(lines):
        print(f"Line {e.lineno}: {lines[lineno][:200]}")
