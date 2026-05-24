path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    s = line.strip()
    if s == "return { ok: false, output: 'model does not support param control' }":
        # Check context: this should be in the param get block
        # Find dead code after this line, ending before closing }
        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if stripped == '}' and j + 1 < len(lines) and 'param set' in lines[j + 1]:
                break
            j += 1
        if j > i + 1:
            print('Removing dead code lines', i + 2, 'to', j)
            del lines[i + 1:j]
        break

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done")
