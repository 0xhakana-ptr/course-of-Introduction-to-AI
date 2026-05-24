path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: isCubism4Model - check getParameterValueById instead of getParameterIds
old_check = "return typeof model?.getParameterIds === 'function'"
new_check = "return typeof model?.getParameterValueById === 'function'"
content = content.replace(old_check, new_check)

# Fix 2: listLive2DParams - use _parameterIds private field
old_list = """  if (isCubism4Model(model)) {
    const ids: string[] = model.getParameterIds() ?? []
    if (!ids.length) return { ok: true, output: '(no parameters)' }
    const lines = ids.map(function(id: string) {
      const val = model.getParameterValueById(id)
      return id + ' = ' + (typeof val === 'number' ? val : 0).toFixed(3)
    })
    return { ok: true, output: lines.join('\\n') }
  }"""

# Note: in the actual file, the \n in join('\\n') is the literal backslash-n in JS source
# Let me use a simpler find pattern
old_list2 = "model.getParameterIds() ?? []"

if old_list2 in content:
    idx = content.find(old_list2)
    # Find the start of the if block
    block_start = content.rfind("if (isCubism4Model(model)) {", 0, idx)
    # Find the closing }
    block_end = content.find("\n  }", idx) + 4  # include \n  }
    
    new_block = """if (isCubism4Model(model)) {
    const rawIds: string[] = (model as any)._parameterIds ?? []
    if (!rawIds.length) return { ok: true, output: '(no parameters)' }
    const lines = rawIds.map(function(id: string) {
      const val = model.getParameterValueById(id)
      return id + ' = ' + (typeof val === 'number' ? val : 0).toFixed(3)
    })
    return { ok: true, output: lines.join('\\n') }
  }"""
    
    content = content[:block_start] + new_block + content[block_end:]
    print("Fixed listLive2DParams")
else:
    print("list pattern not found, searching...")
    if "getParameterIds" in content:
        print("getParameterIds found in content at:", content.find("getParameterIds"))
    else:
        print("getParameterIds NOT in content")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
