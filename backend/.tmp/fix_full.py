path = r"D:\codeAIAGENT\cyber-waifu-vue\src\App.vue"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# The damage: after the 'model does not support param control' return in setLive2DParam,
# everything from the closing brace of that else through the param dispatch was deleted.
# The orphaned code starts with "    }" which was the closing of the outer if(head==='param')?

# What needs to be inserted at the break point (after the 'model does not support param control' line):

insert = """\
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
    return { ok: true, output: lines.join('\\n') }
  }
  if (typeof model.getParamFloat === 'function') {
    return { ok: false, output: 'Cubism2 parameter enumeration not supported; use param get <id> with a known ID' }
  }
  return { ok: false, output: 'model does not support param enumeration' }
}

async function executeLive2DCommand(commandLine: string): Promise<{ ok: boolean; output: string }> {
  const cmd = commandLine.trim()
  const args = tokenizeCommand(cmd)
  const head = (args[0] ?? '').toLowerCase()

  if (!head || head === 'help' || head === '?') {
    return {
      ok: true,
      output:
        '可用命令：\\n' +
        '- help\\n' +
        '- status\\n' +
        '- meta [reload]\\n' +
        '- list motions\\n' +
        '- list expressions\\n' +
        '- param list                （列出所有模型参数）\\n' +
        '- param set <id> <0~1>       （设置参数值）\\n' +
        '- param get <id>             （获取参数值）\\n' +
        '- motion <group> [index]  （index 省略=随机）\\n' +
        '- motion <file.motion3.json>（按文件播放动作）\\n' +
        '- expr <name|index>       （设置为仅该表情）\\n' +
        '- expr <file.exp3.json>    （按文件设置表情）\\n' +
        '- expr add <name|index>   （叠加一个表情）\\n' +
        '- expr add <file.exp3.json>（按文件叠加表情）\\n' +
        '- expr remove <name|index>（移除一个表情）\\n' +
        '- expr remove <file.exp3.json>（移除按文件叠加的表情）\\n' +
        '- expr clear              （清空所有叠加表情）\\n' +
        '- expr active             （查看当前已叠加表情）\\n' +
        '- startup expr <a,b,c>    （设置启动默认表情，逗号分隔）\\n' +
        '- startup clear           （清除启动默认表情）\\n' +
        '- startup show            （查看启动默认表情）\\n' +
        '- stop                   （停止所有动作）\\n' +
        '- focus <x> <y> [instant]（x/y: -1..1）\\n' +
        '- tap <x> <y>            （x/y: 屏幕坐标，像素）\\n',
    }
  }

  if (head === 'status') {
    const loaded = Boolean(currentModel)
    return {
      ok: true,
      output:
        'loaded=' + loaded + '\\n' +
        'modelUrl=' + (currentModelSettingsUrl ?? '(none)') + '\\n' +
        'type=' + (isModel3.value ? 'model3' : 'model') + '\\n',
    }
  }

  if (head === 'meta') {
    const force = (args[1] ?? '').toLowerCase() === 'reload'
    const meta = await ensureMetaLoaded(force)
    if (!meta) {
      return {
        ok: false,
        output:
          '未加载模型元数据。' +
          (lastMetaError ? '\\n原因：' + lastMetaError : '') +
          '\\nmodelUrl=' + (currentModelSettingsUrl ?? modelUrl.value ?? '(none)'),
      }
    }
    const motionGroups = Object.keys(meta.motions)
    return {
      ok: true,
      output:
        'motions: ' + motionGroups.length + ' groups\\n' +
        (motionGroups.length ? motionGroups.map(function(g) { return '- ' + g + ': ' + meta.motions[g] }).join('\\n') + '\\n' : '') +
        'expressions: ' + meta.expressions.length + '\\n' +
        (meta.expressions.length ? meta.expressions.map(function(e) { return '- ' + e }).join('\\n') + '\\n' : ''),
    }
  }

  if (head === 'list') {
    const target = (args[1] ?? '').toLowerCase()
    void ensureMetaLoaded(false)

    if (target === 'motions') {
      const cat = buildLive2DActionCatalog()
      if (!cat.ok) return { ok: false, output: cat.error ?? 'list failed' }
      if (!cat.motions.length) return { ok: true, output: '(none)' }
      return {
        ok: true,
        output: cat.motions.map(function(a) { return a.id + '  # ' + a.label }).join('\\n'),
      }
    }
    if (target === 'expressions') {
      const cat = buildLive2DActionCatalog()
      if (!cat.ok) return { ok: false, output: cat.error ?? 'list failed' }
      if (!cat.expressions.length) return { ok: true, output: '(none)' }
      return {
        ok: true,
        output: cat.expressions.map(function(a) { return a.id + '  # ' + a.label }).join('\\n'),
      }
    }

    return { ok: false, output: '用法：list motions | list expressions' }
  }


  if (!currentModel) return { ok: false, output: '模型尚未加载完成（currentModel is null）' }

  if (head === 'param') {
    const sub = (args[1] ?? '').toLowerCase()
    if (sub === 'list') {
      return listLive2DParams()
    }
    if (sub === 'set') {
      const id = args[2]
      const value = parseFloat(String(args[3] ?? ''))
      if (!id || isNaN(value)) return { ok: false, output: '用法：param set <id> <0~1>' }
      return setLive2DParam(String(id), value)
    }
    if (sub === 'get') {
      const id = args[2]
      if (!id) return { ok: false, output: '用法：param get <id>' }
      const model = getCoreModel()
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
      return { ok: false, output: 'model does not support param control' }
"""

# Find the break point
for i, line in enumerate(lines):
    s = line.strip()
    if s == "return { ok: false, output: 'model does not support param control' }":
        # This is in setLive2DParam. Check context
        # The orphaned code follows immediately
        print("Found break at line", i + 1)
        
        # Remove all orphaned code after this line until we find 'motion' handler
        j = i + 1
        while j < len(lines):
            if "'motion'" in lines[j] and 'if (head ===' in lines[j]:
                break
            j += 1
        
        print("Orphaned code ends at line", j + 1)
        
        # Build new content
        new_content = lines[:i+1] + [insert + "\n"] + lines[j:]
        
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_content)
        print("File reconstructed successfully")
        break
