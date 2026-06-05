# 系统测试问题报告

**测试日期**: 2026-05-20
**Python 版本**: 3.9.11
**项目版本**: 0.6.5

---

## 测试结果摘要

| 指标 | 数量 |
|------|------|
| 总测试数 | 301 |
| 通过 | 183 (60.8%) |
| 失败 | 117 (38.9%) |
| 跳过 | 1 (0.3%) |

---

## 1. Python 版本兼容性问题 (已部分修复)

### 原始问题
项目使用了 Python 3.10+ 的类型注解语法，但当前运行环境是 Python 3.9.11。

### 已修复
- ✅ 添加 `from __future__ import annotations` 到 77+ 文件
- ✅ 移除 `@dataclass(slots=True)` 中的 `slots=True` (25 文件)
- ✅ 修复 `isinstance(x, list | tuple)` 语法 (4 处)
- ✅ 修复类型别名 `Type = A | B` 语法 (3 处)
- ✅ 修复 TypedDict 类型注解 (6 文件)
- ✅ 安装 `eval_type_backport` 包

### 待修复
- ⏳ Pydantic 模型需要 `model_rebuild()` 调用
  - `RunDetailSection`
  - 其他使用 `Dict[str, Any]` 的模型

---

## 2. 缺失模块

### 问题
`backend.app.services.character_action.events` 模块不存在

### 影响
- `tests/services/test_character_events.py` 无法加载

### 解决方案
- 选项 A: 创建缺失的模块
- 选项 B: 删除或更新测试文件

---

## 3. 测试预期过时

部分测试的预期与当前业务逻辑不符：

| 测试 | 预期 | 实际 |
|------|------|------|
| test_chat_route_gracefully_degrades_without_llm | ok=False | ok=True |
| test_chat_test_command_keeps_response_contract | intent='chat' | intent='coding' |

需要审查这些测试是否需要更新。

---

## 4. 已修复文件清单

### Python 3.10+ 类型语法修复 (77 文件)

<details>
<summary>点击展开完整列表</summary>

```
app/message_queue.py
app/schemas.py
app/agent_workflow/actions/models.py
app/agent_workflow/actions/registry.py
app/agent_workflow/actions/workspace.py
app/agent_workflow/coding/artifacts.py
app/agent_workflow/coding/coding_graph.py
app/agent_workflow/coding/planner.py
app/agent_workflow/coding/result.py
app/agent_workflow/coding/worker_payloads.py
app/agent_workflow/contracts/workflow_nodes.py
app/agent_workflow/contracts/workflow_results.py
app/agent_workflow/diagnostics/failure.py
app/agent_workflow/diagnostics/runtime.py
app/agent_workflow/diagnostics/support.py
app/agent_workflow/file/context.py
app/agent_workflow/file/file_graph.py
app/agent_workflow/file/result.py
app/agent_workflow/layers/roleplay_output.py
app/agent_workflow/layers/routing_guard.py
app/agent_workflow/layers/work_engine.py
app/agent_workflow/loop/action_plan.py
app/agent_workflow/loop/agent_loop_graph.py
app/agent_workflow/loop/file_followups.py
app/agent_workflow/loop/planning.py
app/agent_workflow/memory/hermes_memory.py
app/agent_workflow/output/action_events.py
app/agent_workflow/output/completion_events.py
app/agent_workflow/output/node_events.py
app/agent_workflow/output/text.py
app/agent_workflow/repair/repair_decision_graph.py
app/agent_workflow/repair/retry_guidance.py
app/agent_workflow/repair/support.py
app/agent_workflow/runtime/models.py
app/agent_workflow/state/display_state.py
app/agent_workflow/state/engineering_state.py
app/agent_workflow/state/runtime_state.py
app/agent_workflow/state/run_state.py
app/agent_workflow/state/run_support.py
app/agent_workflow/state/state_support.py
app/agent_workflow/summary/support.py
app/agent_workflow/trace/messages.py
app/agent_workflow/trace/runtime.py
app/agent_workflow/utils/shared.py
app/api/error_responses.py
app/api/message_routes.py
app/api/query_params.py
app/api/route_support.py
app/core/logging_config.py
app/core/text_utils.py
app/llm/client.py
app/messaging/message_sender.py
app/messaging/runtime_events.py
app/services/character_interface.py
app/services/chat_interface.py
app/services/run_interface.py
app/services/chat_action/intent.py
app/services/chat_action/types.py
app/services/run_action/codegen.py
app/services/run_action/control.py
app/services/run_action/formatters.py
app/services/run_action/lifecycle.py
app/services/run_action/recovery.py
app/services/run_action/types.py
app/storage/conversation_store.py
app/storage/file_context_store.py
app/storage/run_store.py
app/tools/safe_execute_command.py
app/tools/safe_fs.py
app/tools/workspace_tools.py
app/tools/workspace_tool_models.py
app/tools/workspace/file_ops.py
app/tools/workspace/utils.py
```

</details>

### dataclass slots=True 移除 (25 文件)

<details>
<summary>点击展开完整列表</summary>

```
app/agent_workflow/actions/models.py
app/agent_workflow/coding/planner.py
app/agent_workflow/coding/result.py
app/agent_workflow/coding/worker_payloads.py
app/agent_workflow/contracts/workflow_results.py
app/agent_workflow/diagnostics/support.py
app/agent_workflow/file/result.py
app/agent_workflow/layers/roleplay_output.py
app/agent_workflow/layers/routing_guard.py
app/agent_workflow/loop/action_plan.py
app/agent_workflow/output/node_events.py
app/agent_workflow/output/roleplay_agent.py
app/agent_workflow/repair/support.py
app/agent_workflow/runtime/models.py
app/agent_workflow/state/display_state.py
app/agent_workflow/state/engineering_state.py
app/agent_workflow/state/runtime_state.py
app/agent_workflow/state/run_state.py
app/agent_workflow/summary/support.py
app/llm/client.py
app/services/character_interface.py
app/services/chat_action/types.py
app/services/run_action/control.py
app/services/run_action/types.py
app/tools/workspace_tools.py
```

</details>

---

## 5. 下一步行动

1. **优先**: 为所有 Pydantic 模型添加 `model_rebuild()`
2. **中等**: 处理缺失的 `character_action.events` 模块
3. **后续**: 审查测试预期与业务逻辑的一致性

---

## 附录：批量修复脚本

### 修复 Python 3.10+ 类型语法

```python
import re
from pathlib import Path

backend_dir = Path("backend/app")

for py_file in backend_dir.rglob("*.py"):
    content = py_file.read_text(encoding="utf-8")

    # 检测需要修复的语法
    needs_future = bool(re.search(r':\s*\w+\s*\|\s*None', content))

    if needs_future and "from __future__ import annotations" not in content:
        lines = content.split('\n')
        lines.insert(0, "from __future__ import annotations")
        content = '\n'.join(lines)

    # 添加 typing imports
    if "Optional" not in content and needs_future:
        content = re.sub(
            r'from typing import ([^\n]+)',
            r'from typing import \1, Optional, Dict, List',
            content
        )

    # 替换类型注解
    content = re.sub(r':\s*str\s*\|\s*None', r': Optional[str]', content)
    content = re.sub(r':\s*int\s*\|\s*None', r': Optional[int]', content)
    content = re.sub(r':\s*(\w+)\s*\|\s*None', r': Optional[\1]', content)

    py_file.write_text(content, encoding="utf-8")
```

### 移除 dataclass slots 参数

```python
import re
from pathlib import Path

for py_file in Path("backend").rglob("*.py"):
    content = py_file.read_text(encoding="utf-8")

    content = re.sub(r'@dataclass\(slots=True\)', '@dataclass', content)
    content = re.sub(r'@dataclass\(frozen=True,\s*slots=True\)', '@dataclass(frozen=True)', content)
    content = re.sub(r'@dataclass\(slots=True,\s*frozen=True\)', '@dataclass(frozen=True)', content)

    py_file.write_text(content, encoding="utf-8")
```
