path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "list expressions" in line and "\\n" in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(i + 1, indent + "`- param list                （列出所有模型参数）\\n` +\n")
        lines.insert(i + 2, indent + "`- param set <id> <0~1>       （设置参数值）\\n` +\n")
        lines.insert(i + 3, indent + "`- param get <id>             （获取参数值）\\n` +\n")
        break

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done")
