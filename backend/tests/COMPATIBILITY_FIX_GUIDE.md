# Python 3.9 兼容性修复指南

**项目**: Cyber Waifu Vue
**当前 Python 版本**: 3.9.11
**代码目标版本**: Python 3.10+
**测试日期**: 2026-05-20

---

## 问题概述

项目代码使用了 Python 3.10+ 的语法特性，在 Python 3.9.11 环境下运行测试会失败。

### 主要兼容性问题

| 问题类型 | Python 3.10+ 语法 | Python 3.9 替代方案 |
|----------|-------------------|---------------------|
| 联合类型注解 | `str \| None` | `Optional[str]` 或 `Union[str, None]` |
| 内置泛型 | `dict[str, object]` | `Dict[str, object]` |
| dataclass slots | `@dataclass(slots=True)` | `@dataclass` (移除 slots) |
| isinstance 联合 | `isinstance(x, A \| B)` | `isinstance(x, (A, B))` |
| 类型别名联合 | `Type = A \| B` | `Type = Union[A, B]` |

---

## 修复步骤

### 步骤 1: 安装依赖

```bash
# Pydantic 类型注解兼容包
pip install eval_type_backport

# 项目依赖
pip install langgraph langchain langchain-openai
```

### 步骤 2: 批量添加 `from __future__ import annotations`

**影响的文件** (~77 个):

<details>
<summary>点击展开完整列表</summary>

```
backend/app/message_queue.py
backend/app/schemas.py
backend/app/agent_workflow/actions/models.py
backend/app/agent_workflow/actions/registry.py
backend/app/agent_workflow/actions/workspace.py
backend/app/agent_workflow/coding/artifacts.py
backend/app/agent_workflow/coding/coding_graph.py
backend/app/agent_workflow/coding/planner.py
backend/app/agent_workflow/coding/result.py
backend/app/agent_workflow/coding/state.py
backend/app/agent_workflow/coding/worker_payloads.py
backend/app/agent_workflow/contracts/__init__.py
backend/app/agent_workflow/contracts/workflow_nodes.py
backend/app/agent_workflow/contracts/workflow_results.py
backend/app/agent_workflow/diagnostics/failure.py
backend/app/agent_workflow/diagnostics/runtime.py
backend/app/agent_workflow/diagnostics/support.py
backend/app/agent_workflow/file/context.py
backend/app/agent_workflow/file/file_graph.py
backend/app/agent_workflow/file/result.py
backend/app/agent_workflow/file/state.py
backend/app/agent_workflow/layers/roleplay_output.py
backend/app/agent_workflow/layers/routing_guard.py
backend/app/agent_workflow/layers/work_engine.py
backend/app/agent_workflow/loop/action_plan.py
backend/app/agent_workflow/loop/agent_loop_graph.py
backend/app/agent_workflow/loop/file_followups.py
backend/app/agent_workflow/loop/planning.py
backend/app/agent_workflow/memory/hermes_memory.py
backend/app/agent_workflow/output/action_events.py
backend/app/agent_workflow/output/completion_events.py
backend/app/agent_workflow/output/node_events.py
backend/app/agent_workflow/output/roleplay_agent.py
backend/app/agent_workflow/output/text.py
backend/app/agent_workflow/repair/__init__.py
backend/app/agent_workflow/repair/repair_decision_graph.py
backend/app/agent_workflow/repair/retry_guidance.py
backend/app/agent_workflow/repair/support.py
backend/app/agent_workflow/runtime/models.py
backend/app/agent_workflow/state/display_state.py
backend/app/agent_workflow/state/engineering_state.py
backend/app/agent_workflow/state/run_state.py
backend/app/agent_workflow/state/run_support.py
backend/app/agent_workflow/state/runtime_state.py
backend/app/agent_workflow/state/state_support.py
backend/app/agent_workflow/summary/__init__.py
backend/app/agent_workflow/summary/attempt_summary_graph.py
backend/app/agent_workflow/summary/run_summary_graph.py
backend/app/agent_workflow/summary/support.py
backend/app/agent_workflow/trace/messages.py
backend/app/agent_workflow/trace/runtime.py
backend/app/agent_workflow/utils/__init__.py
backend/app/agent_workflow/utils/shared.py
backend/app/api/error_handlers.py
backend/app/api/error_responses.py
backend/app/api/health_routes.py
backend/app/api/message_routes.py
backend/app/api/query_params.py
backend/app/api/route_support.py
backend/app/core/config.py
backend/app/core/logging_config.py
backend/app/core/text_utils.py
backend/app/llm/client.py
backend/app/messaging/__init__.py
backend/app/messaging/message_sender.py
backend/app/messaging/runtime_events.py
backend/app/services/character_interface.py
backend/app/services/chat_action/intent.py
backend/app/services/chat_action/types.py
backend/app/services/chat_interface.py
backend/app/services/run_action/codegen.py
backend/app/services/run_action/control.py
backend/app/services/run_action/formatters.py
backend/app/services/run_action/lifecycle.py
backend/app/services/run_action/queries.py
backend/app/services/run_action/recovery.py
backend/app/services/run_action/types.py
backend/app/services/run_interface.py
backend/app/storage/conversation_store.py
backend/app/storage/file_context_store.py
backend/app/storage/run_store.py
backend/app/tools/safe_execute_command.py
backend/app/tools/safe_fs.py
backend/app/tools/workspace/constants.py
backend/app/tools/workspace/file_ops.py
backend/app/tools/workspace/utils.py
backend/app/tools/workspace_tool_models.py
backend/app/tools/workspace_tools.py
```

</details>

**修复脚本**:

```python
import re
from pathlib import Path

backend_dir = Path("backend/app")

for py_file in backend_dir.rglob("*.py"):
    content = py_file.read_text(encoding="utf-8")

    # 检测需要修复的语法
    has_union = bool(re.search(r':\s*\w+\s*\|\s*None', content))
    has_dict_list = bool(re.search(r':\s*(dict|list|tuple)\s*\[', content))

    if not (has_union or has_dict_list):
        continue

    if "from __future__ import annotations" in content:
        continue

    lines = content.split('\n')
    insert_pos = 0

    # 跳过 shebang、编码声明和模块 docstring
    in_docstring = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and stripped.startswith('#!'):
            insert_pos = i + 1
            continue
        if stripped.startswith('# -*-') or stripped.startswith('# coding:'):
            insert_pos = i + 1
            continue
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count(stripped[:3]) >= 2:
                    insert_pos = i + 1
                    continue
                in_docstring = True
                insert_pos = i + 1
                continue
            elif stripped == '' or stripped.startswith('#'):
                insert_pos = i + 1
                continue
            else:
                break
        else:
            insert_pos = i + 1
            if '"""' in line or "'''" in line:
                break
            continue

    lines.insert(insert_pos, "from __future__ import annotations")
    py_file.write_text('\n'.join(lines), encoding="utf-8")
    print(f"Fixed: {py_file}")
```

### 步骤 3: 移除 `@dataclass(slots=True)`

**影响的文件** (25 个):

```python
import re
from pathlib import Path

backend_dir = Path("backend")

for py_file in backend_dir.rglob("*.py"):
    content = py_file.read_text(encoding="utf-8")

    # 替换各种 slots=True 模式
    content = re.sub(r'@dataclass\(slots=True\)', '@dataclass', content)
    content = re.sub(r'@dataclass\(frozen=True,\s*slots=True\)', '@dataclass(frozen=True)', content)
    content = re.sub(r'@dataclass\(slots=True,\s*frozen=True\)', '@dataclass(frozen=True)', content)

    py_file.write_text(content, encoding="utf-8")
```

### 步骤 4: 修复 TypedDict 类型注解

LangGraph 在运行时解析 TypedDict 类型，需要使用 `typing` 模块的类型。

**修复前**:
```python
from typing import TypedDict

class MyState(TypedDict, total=False):
    name: str | None
    items: list[dict[str, object]]
```

**修复后**:
```python
from typing import Dict, List, Optional, TypedDict

class MyState(TypedDict, total=False):
    name: Optional[str]
    items: List[Dict[str, object]]
```

**影响的关键文件**:
- `backend/app/agent_workflow/coding/state.py`
- `backend/app/agent_workflow/file/state.py`
- `backend/app/agent_workflow/loop/agent_loop_graph.py`
- `backend/app/agent_workflow/repair/repair_decision_graph.py`
- `backend/app/agent_workflow/summary/run_summary_graph.py`
- `backend/app/agent_workflow/summary/attempt_summary_graph.py`

### 步骤 5: 修复 isinstance 联合类型检查

**修复前**:
```python
if isinstance(value, list | tuple):
    ...

if isinstance(value, int | float | bool) or value is None:
    ...
```

**修复后**:
```python
if isinstance(value, (list, tuple)):
    ...

if isinstance(value, (int, float, bool)) or value is None:
    ...
```

**影响文件**:
- `backend/app/messaging/runtime_events.py`
- `backend/app/agent_workflow/utils/shared.py`
- `backend/app/agent_workflow/coding/planner.py`
- `backend/app/agent_workflow/output/action_events.py`

### 步骤 6: 修复类型别名定义

**修复前**:
```python
SessionResponseT = ConversationSessionMetadataResponse | ConversationSessionContextResponse
ConversationSessionMetadata = dict[str, str | int | bool | None]
```

**修复后**:
```python
from typing import Dict, Union

SessionResponseT = Union[ConversationSessionMetadataResponse, ConversationSessionContextResponse]
ConversationSessionMetadata = Dict[str, Union[str, int, bool, None]]
```

**影响文件**:
- `backend/app/api/route_support.py`
- `backend/app/storage/conversation_store.py`

### 步骤 7: 修复 Pydantic 模型

某些 Pydantic 模型使用 `Dict[str, Any]` 类型，需要：

1. 确保导入 `Dict`, `List` 等
2. 在文件末尾调用 `model_rebuild()`

**示例**:
```python
from typing import Any, Dict, List
from pydantic import BaseModel

class MessageEnvelope(BaseModel):
    metadata: Dict[str, Any] = None

# 文件末尾
MessageEnvelope.model_rebuild()
```

**影响文件**:
- `backend/app/schemas.py` (MessageEnvelope, 等)
- `backend/app/services/run_action/formatters.py` (RunDetailSection, 等)

### 步骤 8: 修复特殊类型定义

**JsonValue 定义** (`backend/app/agent_workflow/state/display_state.py`):

**修复前**:
```python
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
```

**修复后**:
```python
from typing import Union

JsonValue = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
```

### 步骤 9: 修复测试文件

测试文件也需要添加兼容性修复：

```python
# 添加到测试文件顶部
from __future__ import annotations
from typing import Optional
```

**影响的测试文件**:
- `backend/tests/acceptance/test_agent_loop_acceptance.py`
- `backend/tests/agent_workflow/test_coding_workflow_graph.py`
- `backend/tests/api/test_chat_loop_mode.py`
- `backend/tests/api/test_chat_sessions.py`
- `backend/tests/services/test_character_events.py`

---

## 测试验证

修复后运行测试：

```bash
cd backend
python -m pytest tests/ -v --ignore=tests/services/test_character_events.py
```

### 预期结果

| 指标 | 数量 |
|------|------|
| 总测试数 | 301 |
| 通过 | 183+ |
| 失败 | <120 |

---

## 替代方案

### 方案 A: 升级 Python 版本 (推荐)

将 Python 环境升级到 3.10+ 可以避免所有兼容性问题。

**优点**:
- 无需修改代码
- 获得更好的性能和特性
- 更好的类型提示支持

**缺点**:
- 需要重新配置环境
- 可能影响其他依赖 Python 3.9 的项目

### 方案 B: 保持代码修改

如果必须使用 Python 3.9，按照本文档进行修复。

---

## 注意事项

1. **BOM 编码问题**: 部分文件可能有 UTF-8 BOM，修复时需要处理
2. **文件编码**: 使用 `encoding="utf-8"` 读写文件
3. **批量操作**: 建议先备份或创建新分支再进行批量修改
4. **测试覆盖**: 修复后务必运行完整测试套件验证

---

## 附录: 完整修复脚本

```python
#!/usr/bin/env python3
"""
Python 3.9 兼容性修复脚本
运行此脚本将自动修复所有兼容性问题
"""

import re
from pathlib import Path

def fix_future_annotations(content: str) -> str:
    """添加 from __future__ import annotations"""
    if "from __future__ import annotations" in content:
        return content

    has_union = bool(re.search(r':\s*\w+\s*\|\s*None', content))
    has_dict_list = bool(re.search(r':\s*(dict|list|tuple)\s*\[', content))
    has_isinstance_union = bool(re.search(r'isinstance\([^)]+\|', content))

    if not (has_union or has_dict_list or has_isinstance_union):
        return content

    lines = content.split('\n')
    lines.insert(0, "from __future__ import annotations")
    return '\n'.join(lines)

def fix_dataclass_slots(content: str) -> str:
    """移除 slots=True 参数"""
    content = re.sub(r'@dataclass\(slots=True\)', '@dataclass', content)
    content = re.sub(r'@dataclass\(frozen=True,\s*slots=True\)', '@dataclass(frozen=True)', content)
    content = re.sub(r'@dataclass\(slots=True,\s*frozen=True\)', '@dataclass(frozen=True)', content)
    return content

def fix_typing_imports(content: str) -> str:
    """添加必要的 typing imports"""
    typing_imports = []
    if 'Optional' not in content and re.search(r':\s*\w+\s*\|\s*None', content):
        typing_imports.append('Optional')
    if 'Dict' not in content and re.search(r':\s*dict\[', content):
        typing_imports.append('Dict')
    if 'List' not in content and re.search(r':\s*list\[', content):
        typing_imports.append('List')
    if 'Union' not in content and re.search(r'\w+\s*\|\s*\w+', content):
        typing_imports.append('Union')

    if typing_imports and "from typing import" in content:
        match = re.search(r'from typing import ([^\n]+)', content)
        if match:
            existing = match.group(1)
            new_imports = existing.rstrip()
            for imp in typing_imports:
                if imp not in existing:
                    new_imports += f", {imp}"
            content = content.replace(match.group(0), f"from typing import {new_imports}")

    return content

def fix_isinstance_unions(content: str) -> str:
    """修复 isinstance 中的联合类型"""
    content = re.sub(
        r'isinstance\((\w+),\s*list\s*\|\s*tuple\)',
        r'isinstance(\1, (list, tuple))',
        content
    )
    content = re.sub(
        r'isinstance\((\w+),\s*int\s*\|\s*float\s*\|\s*bool\)',
        r'isinstance(\1, (int, float, bool))',
        content
    )
    return content

def fix_type_aliases(content: str) -> str:
    """修复类型别名定义"""
    # 模块级别的类型别名
    content = re.sub(
        r'^(\w+)\s*=\s*(\w+)\s*\|\s*(\w+)',
        r'\1 = Union[\2, \3]',
        content,
        flags=re.MULTILINE
    )
    return content

def fix_typeddict_types(content: str) -> str:
    """修复 TypedDict 中的类型注解"""
    # str | None -> Optional[str]
    content = re.sub(r':\s*str\s*\|\s*None', r': Optional[str]', content)
    content = re.sub(r':\s*int\s*\|\s*None', r': Optional[int]', content)
    content = re.sub(r':\s*bool\s*\|\s*None', r': Optional[bool]', content)

    # dict[str, object] -> Dict[str, object]
    content = re.sub(r':\s*dict\[', r': Dict[', content)
    content = re.sub(r':\s*list\[', r': List[', content)

    # 自定义类型 | None -> Optional[CustomType]
    content = re.sub(r':\s*(?!str\b|int\b|bool\b|float\b|None\b)([A-Z]\w*)\s*\|\s*None', r': Optional[\1]', content)

    return content

def main():
    backend_dir = Path("backend")

    for py_file in backend_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        original = content

        content = fix_future_annotations(content)
        content = fix_dataclass_slots(content)
        content = fix_typing_imports(content)
        content = fix_isinstance_unions(content)
        content = fix_type_aliases(content)
        content = fix_typeddict_types(content)

        if content != original:
            py_file.write_text(content, encoding="utf-8")
            print(f"Fixed: {py_file}")

    print("\nDone!")

if __name__ == "__main__":
    main()
```

---

## 参考链接

- [PEP 604 - Allow writing union types as X | Y](https://peps.python.org/pep-0604/)
- [PEP 585 - Type Hinting Generics In Standard Collections](https://peps.python.org/pep-0585/)
- [Python 3.10 Release Notes](https://docs.python.org/3/whatsnew/3.10.html)
- [Pydantic Documentation - model_rebuild()](https://docs.pydantic.dev/latest/api/main/#pydantic.BaseModel.model_rebuild)
