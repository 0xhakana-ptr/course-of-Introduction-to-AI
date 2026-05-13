# 后端说明

后端当前基于 `FastAPI + LangGraph + OpenAI-compatible LLM`，负责 4 条主链路：

- `chat`：聊天入口、意图识别、会话记忆
- `runs`：代码任务创建、执行、修复、取消、查询
- `messages`：轮询与 WebSocket 消息推送
- `agent_workflow`：LangGraph 图编排与诊断

这个文件只保留上手所需信息。更细的接口和模块说明已经拆到独立文档。

## 1. 环境要求

- 推荐使用 `uv` 管理 Python、虚拟环境和依赖
- 推荐 `Python 3.11`
- `Python 3.12` 可以使用
- 当前不建议使用 `Python 3.14`
- 下文命令默认都在项目根目录执行

## 2. 快速启动

### 2.1 安装 Python 与虚拟环境

```powershell
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r backend/requirements.txt
```

如果你当前的 `.venv` 是用不推荐版本创建的，直接重建更干净：

```powershell
if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
uv venv --python 3.11 .venv
uv pip install -r backend/requirements.txt
```

### 2.2 配置环境变量

```powershell
Copy-Item backend/.env.example backend/.env
```

至少补齐这 3 项：

```text
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

如果你使用 LongCat 的 OpenAI-compatible 接口，示例是：

```text
LLM_BASE_URL=https://api.longcat.chat/openai/v1
LLM_PROVIDER_PROFILE=openai
LLM_MODEL=LongCat-Flash-Thinking-2601
```

如果你使用 MiniMax，建议显式指定 provider profile：

```text
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_PROVIDER_PROFILE=minimax
LLM_MODEL=MiniMax-M2.7
```

如果某个 provider 的聊天端点不是标准的 `base_url + /chat/completions`，可以额外设置：

```text
LLM_CHAT_COMPLETIONS_URL=
```

说明：

- 后端只要求“OpenAI-compatible 接口”，并不限定必须是 OpenAI 官方
- `LLM_BASE_URL` 通常填写供应商文档里的 API root，例如 `https://api.minimaxi.com/v1`；后端会自动拼成 `.../chat/completions`
- URL 中是否包含 `/openai/` 取决于供应商自己的文档，不是后端强制要求；例如 LongCat 示例包含 `/openai/v1`，MiniMax 示例不包含
- 当前优先稳定支持 `openai` 与 `minimax` 两类 profile；如果是其他供应商，优先先验证其 `/chat/completions` 兼容程度
- 未配置 LLM 时，服务仍可启动，但聊天会退回占位回复，`runs` 会优先走本地模板逻辑

### 2.3 Agent Runtime

当前 `/chat` 只使用 Agent Loop 主路径，旧 route graph 和 `AGENT_RUNTIME_MODE` 灰度开关已经移除。

现阶段约定：

- 新功能接入 `agent_workflow/loop/`、`agent_workflow/actions/` 和共享 service/tool 层
- 不再维护旧 route graph fallback
- `/agent/diagnostics/*` 默认诊断 Agent Loop 主路径
- `/chat` 响应会返回 `runtime_mode=loop` 和 `route_scope=primary_loop`，用于确认当前运行路径

### 2.4 启动后端

```powershell
uv run uvicorn backend.app.main:app --reload --port 8000
```

启动后优先检查：

- Swagger 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 3. 常用命令

### 3.0 可选：桌面导出

默认情况下，后端不会直接写入桌面或任意系统路径。简单文本文件任务会优先写入 `backend/workspace`；如果用户要求写到桌面，默认会返回安全提示。

如果确实需要让后端把文本文件导出到桌面附近的指定目录，需要在 `backend/.env` 中显式开启：

```text
DESKTOP_EXPORT_ENABLED=true
DESKTOP_EXPORT_DIR=C:\Users\<you>\Desktop\AI-Agent-Exports
```

说明：

- `DESKTOP_EXPORT_ENABLED=false` 是默认值
- `DESKTOP_EXPORT_DIR` 必须是明确的本地目录
- 后端只会导出到该目录下，并会清洗文件名
- 默认不覆盖同名文件
- 不建议直接把整个真实桌面作为随意写入目录

### 3.0.1 可选：真实项目访问

默认情况下，文件工具仍只访问 `backend/workspace/`。如果需要让桌宠读取真实项目代码，可以在 `backend/.env` 中配置项目根目录：

```text
PROJECT_ROOT=D:\Code\your-project
PROJECT_WRITE_ENABLED=false
```

说明：

- `PROJECT_ROOT` 为空时使用默认 `backend/workspace/`
- `PROJECT_WRITE_ENABLED=false` 是默认值，真实项目目录只读
- 只有设置 `PROJECT_WRITE_ENABLED=true` 后，文件工具才允许写入真实项目目录
- `.git`、`.env*`、`node_modules`、`__pycache__`、`.venv`、`dist`、`build` 等敏感或生成路径会被安全层拒绝访问
- 即使开启真实项目写入，Agent 层仍应保留高风险文件操作确认，不应绕过 `app/tools/safe_fs.py`

### 3.1 运行测试

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

### 3.2 功能层 smoke 验证

不启动真实服务时，可以用 `TestClient` 快速验证核心接口能否被应用正确挂载：

```powershell
@'
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

print(client.get("/health").json())
diagnostics = client.post("/agent/diagnostics/preview", json={"prompt": "hello", "context": None}).json()
print(diagnostics["selected_route"], diagnostics["action_name"])
print(client.post("/chat", json={"prompt": "/test chat smoke", "context": None}).json()["intent"])
'@ | uv run --python 3.11 --with-requirements backend/requirements.txt python -
```

这个 smoke 示例使用 `/test chat`，不会依赖真实 LLM。要验证真实模型连通性，请继续使用 `/llm/diagnostics?check_remote=true`。

### 3.3 检查 LLM 配置

只检查本地配置是否被后端正确读取：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/llm/diagnostics
```

连同上游模型连通性一起检查：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/llm/diagnostics?check_remote=true"
```

### 3.4 与 Electron 联调

```powershell
$env:AI_AGENT_ENDPOINT="http://127.0.0.1:8000/chat"
$env:AI_AGENT_BASE_URL="http://127.0.0.1:8000"
pnpm dev
```

如果消息接口不在同一基地址下，可以额外设置：

```powershell
$env:AI_AGENT_MESSAGES_ENDPOINT="http://127.0.0.1:8000/messages"
```

视觉联调时按这个清单检查：

- Chat 窗口是否显示节点过程提示和中文节点名
- 字幕窗口是否显示后端 `agent:quip`
- 简单 read/write 工具任务是否不创建 run
- “刚才创建的文件”“刚才搜索到的文件”等同会话文件指代是否能继续执行
- Markdown、代码块、LaTeX 是否通过 `content_type=markdown`、`render_mode=rich_text` 正常渲染
- 桌面文本导出请求是否先弹出确认框
- `/runs/{run_id}` 是否返回 `detail_sections`

更完整的验收步骤见 [`docs/backend/agent-acceptance.md`](../docs/backend/agent-acceptance.md)。

## 4. 后端目录概览

```text
backend/
  app/
    api/
    agent_workflow/
    core/
    llm/
    messaging/
    services/
    storage/
    tools/
    main.py
    message_queue.py
    schemas.py
  dev/
  tests/
  workspace/
  .env.example
  requirements.txt
```

各目录职责：

- `app/api/`：HTTP / WebSocket 路由层
- `app/services/`：业务入口与领域动作
- `app/agent_workflow/`：LangGraph 编排、诊断、摘要、修复决策
- `app/storage/`：会话、文件上下文与 run 持久化
- `app/tools/`：受限文件系统、文件任务解析与命令执行工具
- `app/llm/`：OpenAI-compatible LLM 客户端
- `app/messaging/` 与 `app/message_queue.py`：统一消息投递
- `backend/dev/`：开发期手动调试脚本，不属于正式后端入口
- `backend/workspace/`：运行时数据目录，不是源码目录

开发入口速查：

- 改接口：先看 `app/api/*_routes.py`，复杂逻辑下沉到 `app/services/*_interface.py`
- 改聊天 Agent 主线：先看 `app/agent_workflow/loop/`，不要恢复旧 route graph
- 改文件/命令工具：先看 `app/tools/`，不要绕过 workspace 安全限制
- 改前端消息协议：先看 `app/messaging/`，不要让前端靠文本猜测状态或富文本
- 改持久化：先看 `app/storage/`，涉及格式变化时需要单独计划

## 5. 详细文档

- 接口说明：[`docs/backend/api-specification.md`](../docs/backend/api-specification.md)
- 目录与模块地图：[`docs/backend/module-map.md`](../docs/backend/module-map.md)
- 功能验收与排障：[`docs/backend/agent-acceptance.md`](../docs/backend/agent-acceptance.md)

如果你要继续开发后端，优先看“模块地图”；如果你要联调接口，优先看“API 说明”。
