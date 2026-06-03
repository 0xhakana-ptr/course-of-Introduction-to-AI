# 后端说明
后端基于 `FastAPI + LangGraph + OpenAI-compatible LLM`，负责聊天、代码任务执行、消息推送和 Agent 工作流编排。

详细接口与模块文档见 [`docs/backend/`](../docs/backend/)。

## 1. 环境要求

- 推荐 `uv` 管理 Python 和依赖
- 推荐 Python 3.11（3.12 可用）
- 以下命令在项目根目录执行

## 2. 快速启动

### 2.1 安装

```powershell
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install -r backend/requirements.txt
```

如果 `.venv` 是用其他版本创建的，先删掉重建：

```powershell
if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
uv venv --python 3.11 .venv
uv pip install -r backend/requirements.txt
```

### 2.2 配置

```powershell
Copy-Item backend/.env.example backend/.env
```

编辑 `backend/.env`，至少填入：

```text
LLM_BASE_URL=https://your-base-url/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model
```

后端只要求 OpenAI-compatible 接口，不限定供应商。更多配置项说明见 `.env.example` 内注释。

未配置 LLM 时服务仍可启动，但聊天会退回占位回复。

### 2.3 启动

```powershell
uv run uvicorn backend.app.main:app --reload --port 8000
```

验证：

- Swagger 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

## 3. 运行测试

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

## 4. 检查 LLM 配置

```powershell
# 本地配置
Invoke-RestMethod http://127.0.0.1:8000/llm/diagnostics

# 含上游连通性
Invoke-RestMethod "http://127.0.0.1:8000/llm/diagnostics?check_remote=true"
```

## 5. 性能提示

视觉截图识别功能默认开启，运行时可能偶尔卡顿。如果不需要，可以临时关闭：

```powershell
$env:VISION_ENABLED="false"
```

后端侧同样支持：在 `backend/.env` 中设置 `VISION_ENABLED=false` 即可完全禁用。

## 6. 目录概览

```text
backend/
  app/
    api/             HTTP / WebSocket 路由
    agent_workflow/  LangGraph 编排、诊断、修复决策
    core/            配置、日志、文本工具
    llm/             OpenAI-compatible 客户端
    messaging/       统一消息投递
    services/        业务入口与领域动作
    storage/         会话、文件上下文与 run 持久化
    tools/           安全文件系统与命令执行工具
    vision/          屏幕截图与 ONNX 视觉推理
    main.py          应用入口
  tests/             测试
  workspace/         运行时数据（不要提交）
  .env.example       环境变量模板
  requirements.txt   Python 依赖
```

入口：

- 接口 → `app/api/*_routes.py`，复杂逻辑下沉到 `app/services/`
- 聊天主线 → `app/agent_workflow/loop/`
- 文件/命令工具 → `app/tools/`，不要绕过 workspace 安全限制
- 前端消息协议 → `app/messaging/`
- 持久化 → `app/storage/`

## 7. 与 Electron 前端联调

启动后端后，在另一个终端设置以下环境变量再运行 `pnpm dev`：

```powershell
$env:AI_AGENT_ENDPOINT=”http://127.0.0.1:8000/chat”
$env:AI_AGENT_BASE_URL=”http://127.0.0.1:8000”
pnpm dev
```

如果消息轮询地址不同：

```powershell
$env:AI_AGENT_MESSAGES_ENDPOINT=”http://127.0.0.1:8000/messages”
```

视觉联调时如果卡顿，先关闭截图功能（见第 5 节）。

更完整的验收步骤见 [`docs/backend/agent-acceptance.md`](../docs/backend/agent-acceptance.md)。

## 8. 详细文档

- 接口说明：[`docs/backend/api-specification.md`](../docs/backend/api-specification.md)
- 目录与模块地图：[`docs/backend/module-map.md`](../docs/backend/module-map.md)
- 功能验收与排障：[`docs/backend/agent-acceptance.md`](../docs/backend/agent-acceptance.md)
