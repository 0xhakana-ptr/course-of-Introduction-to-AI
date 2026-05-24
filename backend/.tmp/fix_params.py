import re

path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# New helper functions
new_helpers = '''// -- Live2D raw parameter control --
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
    if (idx < 0) return { ok: false, output: `parameter not found: ${id}` }
    model.setParameterValueByIndex(idx, clamped)
  } else if (typeof model.setParamFloat === 'function') {
    model.setParamFloat(id, clamped)
  } else {
    return { ok: false, output: 'model does not support param control' }
  }
  return { ok: true, output: `param ${id} = ${clamped.toFixed(3)}` }
}

function listLive2DParams(): { ok: boolean; output: string } {
  const model = getCoreModel()
  if (!model) return { ok: false, output: 'Live2D model not loaded' }
  if (isCubism4Model(model)) {
    const ids: string[] = model.getParameterIds() ?? []
    if (!ids.length) return { ok: true, output: '(no parameters)' }
    const lines = ids.map((id) => {
      const val = model.getParameterValueById(id)
      return `${id} = ${(typeof val === 'number' ? val : 0).toFixed(3)}`
    })
    return { ok: true, output: lines.join('\n') }
  }
  if (typeof model.getParamFloat === 'function') {
    return { ok: false, output: 'Cubism2 parameter enumeration not supported; use param get <id> with a known ID' }
  }
  return { ok: false, output: 'model does not support param enumeration' }
}
'''

# Find the old helpers block and replace it
old_pattern = r'// -- Live2D raw parameter control --\nfunction getCubismModel\(\): any \{[^}]*\}\n\nfunction setLive2DParam[^}]*\}\n\nfunction listLive2DParams[^}]*\}'

match = re.search(old_pattern, content, re.DOTALL)
if match:
    content = content[:match.start()] + new_helpers + content[match.end():]
    
    # Now fix the param get block inside executeLive2DCommand
    # Replace the inline get logic
    old_get = '''      const model = getCubismModel()
      if (!model) return { ok: false, output: 'model not loaded' }
      const count = model.getParameterCount?.() ?? 0
      for (let i = 0; i < count; i++) {
        if (model.getParameterId?.(i) === String(id)) {
          const val = model.getParameterValueByIndex?.(i) ?? 0
          return { ok: true, output: `${id} = ${(typeof val === 'number' ? val : 0).toFixed(3)}` }
        }
      }
      return { ok: false, output: `parameter not found: ${id}` }'''
    
    new_get = '''      const model = getCoreModel()
      if (!model) return { ok: false, output: 'model not loaded' }
      if (isCubism4Model(model)) {
        const idx = model.getParameterIndex(String(id))
        if (idx < 0) return { ok: false, output: `parameter not found: ${id}` }
        const val = model.getParameterValueByIndex(idx)
        return { ok: true, output: `${id} = ${(typeof val === 'number' ? val : 0).toFixed(3)}` }
      }
      if (typeof model.getParamFloat === 'function') {
        const val = model.getParamFloat(String(id))
        return { ok: true, output: `${id} = ${(typeof val === 'number' ? val : 0).toFixed(3)}` }
      }
      return { ok: false, output: 'model does not support param control' }'''
    
    content = content.replace(old_get, new_get)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK: helpers and param get block updated")
else:
    print("FAIL: old helpers pattern not found")
