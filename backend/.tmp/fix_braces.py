path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix: after "return { ok: false, output: 'model does not support param control' }" (in param get),
# we need to add closing braces before the motion handler

old = """      return { ok: false, output: 'model does not support param control' }

  if (head === 'motion') {"""

new = """      return { ok: false, output: 'model does not support param control' }
    }
    return { ok: false, output: '用法：param set <id> <0~1> | param get <id> | param list' }
  }

  if (head === 'motion') {"""

content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
