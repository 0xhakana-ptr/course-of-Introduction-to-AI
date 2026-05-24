path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Replace lines 1039-1072 (0-indexed: 1038-1071)
# New helpers
new_helpers = """\
// -- Live2D raw parameter control --
function getCoreModel(): any {
  try {
    const im = currentModel?.internalModel
    if (!im) return null
    return im.coreModel ?? null
  } catch { return null }
}

function isCubism4Model(model: any): boolean {
  return typeof model?.getParameterIds === 'function'
}

function setLive2DParam(id: string, value: number): { ok: boolean; output: string } {
  const model = getCoreModel()
  if (!model) return { ok: false, output: 'Live2D model not loaded' }
  const clamped = Math.max(0, Math.min(1, Number(value) || 0))
  if (isCubism4Model(model)) {
    const idx = model.getParameterIndex(id)
    if (idx < 0) return { ok: false, output: 'parameter not found: ' + id }
    model.setParameterValueByIndex(idx, clamped)
  } else if (typeof model.setParamFloat === 'function') {
    model.setParamFloat(id, clamped)
  } else {
    return { ok: false, output: 'model does not support param control' }
  }
  return { ok: true, output: 'param ' + id + ' = ' + clamped.toFixed(3) }
}

function listLive2DParams(): { ok: boolean; output: string } {
  const model = getCoreModel()
  if (!model) return { ok: false, output: 'Live2D model not loaded' }
  if (isCubism4Model(model)) {
    const ids: string[] = model.getParameterIds() ?? []
    if (!ids.length) return { ok: true, output: '(no parameters)' }
    const lines = ids.map(function(id: string) {
      const val = model.getParameterValueById(id)
      return id + ' = ' + (typeof val === 'number' ? val : 0).toFixed(3)
    })
    return { ok: true, output: lines.join('\n') }
  }
  if (typeof model.getParamFloat === 'function') {
    return { ok: false, output: 'Cubism2 parameter enumeration not supported; use param get <id> with a known ID' }
  }
  return { ok: false, output: 'model does not support param enumeration' }
}

"""

# Find the start line (0-indexed)
start = None
for i, line in enumerate(lines):
    if '// -- Live2D raw parameter control --' in line:
        start = i
        break

if start is None:
    print("FAIL: start not found")
    exit(1)

# Find end: the empty line after listLive2DParams }
end = None
for i in range(start + 1, len(lines)):
    stripped = lines[i].strip()
    # We want the last } of the three functions, which is followed by an empty line
    if stripped == '}' and i + 1 < len(lines) and lines[i + 1].strip() == '':
        # Make sure this is after the listLive2DParams function
        if i - start > 20:  # More than 20 lines from start means we're past the helpers
            end = i
            break

if end is None:
    print("FAIL: end not found")
    exit(1)

print("Replacing lines", start + 1, "to", end + 1)

# Replace
new_lines = lines[:start] + [new_helpers] + lines[end + 1:]

# Now fix the param get block
content = ''.join(new_lines)
old_get = """      const model = getCubismModel()
      if (!model) return { ok: false, output: 'model not loaded' }
      const count = model.getParameterCount?.() ?? 0
      for (let i = 0; i < count; i++) {
        if (model.getParameterId?.(i) === String(id)) {
          const val = model.getParameterValueByIndex?.(i) ?? 0
          return { ok: true, output: `$""" + """{id} = $""" + """{(typeof val === 'number' ? val : 0).toFixed(3)}` }
        }
      }
      return { ok: false, output: `parameter not found: $""" + """{id}` }"""

# Find the actual text in content 
# Use a simpler approach - find getCubismModel call in param get block
old_get_start = """      const model = getCubismModel()
      if (!model) return { ok: false, output: 'model not loaded' }"""

new_get = """      const model = getCoreModel()
      if (!model) return { ok: false, output: 'model not loaded' }
      if (isCubism4Model(model)) {
        const idx = model.getParameterIndex(String(id))
        if (idx < 0) return { ok: false, output: 'parameter not found: ' + String(id) }
        const val = model.getParameterValueByIndex(idx)
        return { ok: true, output: String(id) + ' = ' + (typeof val === 'number' ? val : 0).toFixed(3) }
      }
      if (typeof model.getParamFloat === 'function') {
        const val = model.getParamFloat(String(id))
        return { ok: true, output: String(id) + ' = ' + (typeof val === 'number' ? val : 0).toFixed(3) }
      }
      return { ok: false, output: 'model does not support param control' }"""

content = content.replace(old_get_start, new_get)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
