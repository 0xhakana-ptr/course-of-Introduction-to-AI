import re
path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()
m = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
if m:
    script = m.group(1)
    brace = 0
    in_str = False
    str_ch = ""
    in_tmpl = False
    in_comm = False
    in_line = False
    i = 0
    while i < len(script):
        ch = script[i]
        nxt = script[i+1] if i+1 < len(script) else ""
        prev = script[i-1] if i > 0 else ""
        if in_line and ch == "\n":
            in_line = False
            i += 1
            continue
        if in_line:
            i += 1
            continue
        if in_comm and ch == "*" and nxt == "/":
            in_comm = False
            i += 2
            continue
        if in_comm:
            i += 1
            continue
        if not in_str and not in_tmpl and ch == "/" and nxt == "/":
            in_line = True
            i += 2
            continue
        if not in_str and not in_tmpl and ch == "/" and nxt == "*":
            in_comm = True
            i += 2
            continue
        if not in_str and not in_tmpl and ch == "`" and prev != "\\":
            in_tmpl = not in_tmpl
        elif not in_tmpl and (ch == '"' or ch == "'"):
            if not in_str:
                in_str = True
                str_ch = ch
            elif ch == str_ch and prev != "\\":
                in_str = False
        if in_str or in_tmpl or in_comm or in_line:
            i += 1
            continue
        if ch == "{":
            brace += 1
        if ch == "}":
            brace -= 1
        i += 1
    print("Brace balance:", brace, "(0 = balanced)")
else:
    print("No script section found")
