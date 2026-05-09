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
LLM_MODEL=LongCat-Flash-Thinking-2601
```

说明：

- 后端只要求“OpenAI-compatible 接口”，并不限定必须是 OpenAI 官方
- 未配置 LLM 时，服务仍可启动，但聊天会退回占位回复，`runs` 会优先走本地模板逻辑

### 2.3 启动后端

```powershell
uv run uvicorn backend.app.main:app --reload --port 8000
```

启动后优先检查：

- Swagger 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 3. 常用命令

### 3.1 运行测试

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

### 3.2 检查 LLM 配置

只检查本地配置是否被后端正确读取：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/llm/diagnostics
```

连同上游模型连通性一起检查：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/llm/diagnostics?check_remote=true"
```

### 3.3 与 Electron 联调

```powershell
$env:AI_AGENT_ENDPOINT="http://127.0.0.1:8000/chat"
pnpm dev
```

如果消息接口不在同一基地址下，可以额外设置：

```powershell
$env:AI_AGENT_MESSAGES_ENDPOINT="http://127.0.0.1:8000/messages"
```

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
  tests/
  workspace/
  .env.example
  requirements.txt
```

各目录职责：

- `app/api/`：HTTP / WebSocket 路由层
- `app/services/`：业务入口与领域动作
- `app/agent_workflow/`：LangGraph 编排、诊断、摘要、修复决策
- `app/storage/`：会话与 run 持久化
- `app/tools/`：受限文件系统与命令执行工具
- `app/llm/`：OpenAI-compatible LLM 客户端
- `app/messaging/` 与 `app/message_queue.py`：统一消息投递
- `backend/workspace/`：运行时数据目录，不是源码目录

## 5. 详细文档

- 接口说明：[`docs/backend-api-specification.md`](../docs/backend-api-specification.md)
- 目录与模块地图：[`docs/backend-module-map.md`](../docs/backend-module-map.md)

如果你要继续开发后端，优先看“模块地图”；如果你要联调接口，优先看“API 说明”。
