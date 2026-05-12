# Backend Agent Acceptance Guide

副标题：桌宠 Agent 后端功能验收与排障手册 / Desktop Pet Agent Backend Acceptance and Troubleshooting Guide

本文档用于开发期联调和提交前验收。目标不是覆盖所有 API 字段，而是快速判断当前后端是否符合“顶层 Turn Controller + 内部子工作流”的项目方向。

## 1. 当前验收目标

后端主路径应固定为：

```text
/chat
-> Turn Controller
-> perceive
-> plan
-> act
-> observe
-> decide
-> finalize / failure
```

验收重点：

- `/chat` 每次请求必须返回 HTTP 响应。
- `/messages` 中每轮 Turn Controller 必须出现 `workflow.completed` 或 `workflow.failed` 终态事件。
- 普通聊天、workspace 文件工具、run 控制、桌面导出确认都应进入同一套 Turn Controller/action/message 协议。
- 前端不应依赖旧 route graph，也不应把 `workflow.action_completed` 当作整轮对话结束。

架构验收边界：

- `agent_loop_graph.py` 当前保留文件名，但定位是顶层 Turn Controller，不是完整 coding/debug agent brain。
- 后续 PM、Coder、Tool Executor、QA、Debugger 不应继续堆在顶层 Turn Controller 中，应进入 `agent_workflow/coding/` 等内部子工作流。
- Roleplay 和前端状态不允许包含 raw error、完整 stdout/stderr、长代码 diff 或工具内部 stack trace。
- coding/debug 子工作流只能向前端输出简短状态、确认请求、用户可读摘要和终态事件。
- 每轮调用无论成功、失败、等待确认，都必须有明确终态或可被前端识别的暂停状态，不能让输入框永久锁住。

## 2. 启动前检查

推荐命令：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

启动后端：

```powershell
uv run uvicorn backend.app.main:app --reload --port 8000
```

检查健康状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

检查 LLM 配置读取：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/llm/diagnostics
```

如果要检查远程模型连通性：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/llm/diagnostics?check_remote=true"
```

## 3. 消息流验收

每轮手工验收前建议先清空消息队列：

```powershell
Invoke-RestMethod -Method Delete http://127.0.0.1:8000/messages
```

发送普通聊天：

```powershell
$body = @{ prompt = "1+1等于几"; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body $body
```

读取消息：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/messages
```

合格标准：

- `/chat` 返回 `runtime_mode=loop`。
- `/chat` 返回 `route_scope=primary_loop`。
- `/messages` 至少能看到 `workflow.node_entered`。
- `/messages` 最终能看到 `workflow.completed` 或 `workflow.failed`。
- `agent:quip` 可以显示节点短句，例如“我先理解你的目标。”。
- `agent:status` 可以显示节点状态、动作状态和最终状态。

## 4. Workspace 文件验收

创建并读取文件：

```powershell
Invoke-RestMethod -Method Delete http://127.0.0.1:8000/messages
$body = @{ prompt = '请创建 notes/acceptance.txt，内容是hello acceptance，然后读出来确认'; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body $body
Invoke-RestMethod http://127.0.0.1:8000/messages
```

合格标准：

- 创建动作应规划为 `workspace.write`。
- 多步任务应继续执行后续 `workspace.read`。
- 最终回复应包含读取到的内容或明确失败原因。
- 消息流中应出现 `workflow.action_started` 与 `workflow.action_completed`。
- 最终仍应出现 `workflow.completed`。

读取不存在的文件：

```powershell
$body = @{ prompt = '请读取 notes/not-exists.txt'; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body $body
```

合格标准：

- 后端不能退回普通聊天假装回答。
- 应返回明确的文件不存在说明。
- 消息流最终应出现 `workflow.failed` 或带清晰错误说明的终态。

## 5. 桌面导出验收

默认配置下，桌面导出应被禁止或要求确认：

```powershell
$body = @{ prompt = '请在桌面创建一个 acceptance.txt，内容是hello'; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body $body
```

合格标准：

- `DESKTOP_EXPORT_ENABLED=false` 时不能直接写入桌面。
- 响应应给出禁止原因、确认请求或安全替代路径。
- 不能卡在 loading。
- 消息流必须有 `workflow.completed` 或 `workflow.failed`。

如需开启导出，应在 `backend/.env` 显式配置：

```text
DESKTOP_EXPORT_ENABLED=true
DESKTOP_EXPORT_DIR=C:\Users\<you>\Desktop\AI-Agent-Exports
```

## 6. Run 控制验收

创建 run：

```powershell
$body = @{ prompt = '写一个 Python 程序打印 hello agent'; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body $body
```

合格标准：

- 如果规划为 `run.create`，响应应包含 `run_id`。
- 后续状态通过 `/runs/{run_id}`、`/runs/{run_id}/snapshot` 和 `/messages` 查询。
- run 创建后仍应出现 Agent Loop 终态事件，不能让前端输入框一直锁住。

查看 run 状态：

```powershell
$runId = "<replace-with-run-id>"
Invoke-RestMethod "http://127.0.0.1:8000/runs/$runId"
```

高风险控制动作：

- `run.cancel` 需要明确确认。
- `workspace.test` 需要明确确认。
- 已启用桌面导出的 `workspace.export_desktop` 需要明确确认。
- 已存在文件默认不覆盖；只有用户明确写出“覆盖 / 替换 / overwrite / replace”时，`workspace.write` 或 `workspace.export_desktop` 才允许覆盖。

确认类动作合格标准：

- 未确认时返回 `ask_user_confirmation`。
- 用户明确输入“确认执行”或 `confirm/proceed` 后才继续。
- 文件覆盖确认必须使用覆盖类表达，不应把普通“确认执行”误当作覆盖授权。
- 缺少 `run_id` 时优先提示补充参数，不应进入假确认。

## 7. Diagnostics 验收

无副作用预览：

```powershell
$body = @{ prompt = '请创建 notes/diag.txt，内容是hello'; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/agent/diagnostics/preview -ContentType "application/json" -Body $body
```

运行期诊断：

```powershell
$body = @{ prompt = '请读取 notes/diag.txt'; context = $null } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/agent/diagnostics/run -ContentType "application/json" -Body $body
```

合格标准：

- `diagnostics_mode=loop`。
- `route_scope=primary_loop`。
- `selected_route=agent_loop`。
- `workflow_trace` 中有 `node_label`、`phase`、`event_label`、`status_level`、`message`。
- 失败时 `error_context` 应给出稳定 `error_code`、`failure_domain` 和中文摘要。

## 8. Electron 联调验收

启动前端前设置：

```powershell
$env:AI_AGENT_ENDPOINT="http://127.0.0.1:8000/chat"
$env:AI_AGENT_BASE_URL="http://127.0.0.1:8000"
pnpm dev
```

合格标准：

- Chat 窗口能显示用户输入和后端回复。
- Chat 窗口能显示节点过程提示或动作过程提示。
- 字幕窗口能显示 `agent:quip`。
- 文件创建、读取、失败、确认请求都不会让输入框永久不可用。
- 如果使用 WebSocket，`WS /messages/ws` 的消息结构应与 `GET /messages` 一致。
- 每条前端消息应包含 Bridge JSON 字段：`bridge_event_type`、`bridge_event_version`、`bridge_payload`。
- 前端可通过 `bridge_event_type=Status_Update` 识别节点/动作/终态状态，通过 `Roleplay_Dialogue` 识别角色台词和动作，通过 `Auth_Request` 识别确认请求。
- coding 子图的 `pm_node`、`coder_node`、`executor_node`、`qa_node`、`debugger_node` 应在节点开头发出 `workflow.node_entered`，并在 `bridge_payload.phase` 中标明 `coding` 或 `tools`。

## 9. 常见问题排查

### 9.1 前端输入框一直不能输入

优先检查：

- `/messages` 是否出现 `workflow.completed` 或 `workflow.failed`。
- Electron 是否设置了 `AI_AGENT_BASE_URL`，否则只能调用 `/chat`，无法轮询 `/messages`。
- 后端日志是否有 LangGraph 节点异常。
- 用 `/agent/diagnostics/run` 复现同一条 prompt，查看 `error_context`。

### 9.2 字幕窗口没有 quip

优先检查：

- `/messages` 中是否存在 `_channel=agent:quip`。
- 消息 `event_type` 是否为 `workflow.node_entered`。
- Electron bridge 是否把 `agent:quip` 转发到 quip window。
- 前端是否仍只监听旧 `quip:text`。

### 9.3 LLM 调用失败

优先检查：

- `/llm/diagnostics` 中 `configured` 是否为 `true`。
- `LLM_BASE_URL` 是否为 provider 的 API root。
- 如果 provider 不符合标准 `base_url + /chat/completions`，设置 `LLM_CHAT_COMPLETIONS_URL`。
- LongCat 的 `/openai/v1` 是供应商路径，不是所有 provider 必须包含 `/openai/`。
- MiniMax 示例应使用 `LLM_BASE_URL=https://api.minimaxi.com/v1` 和 `LLM_PROVIDER_PROFILE=minimax`。

### 9.4 文件任务没有执行

优先检查：

- diagnostics preview 的 `action_name` 是否是 `workspace.write`、`workspace.read`、`workspace.list` 或 `workspace.export_desktop`。
- 路径是否被正确解析，中文路径和带空格路径建议用反引号或引号包起来。
- 读取不存在文件时，期望结果是明确失败，不是退回普通聊天。

### 9.5 LLM planner 没有执行工具

这是预期边界：LLM planner 只负责输出严格 JSON 计划，不能直接执行工具。

优先检查：

- `coder_plan.planner_source` 是否为 `llm`。
- `coder_plan.planner_result.error_kind` 是否为 `invalid_json`、`unsupported_action` 或 `invalid_action_input`。
- `executor_action_name` 是否属于允许范围：`workspace.write`、`workspace.read`、`workspace.list`、`run.create`。
- 如果 LLM 返回 shell、command、env、token、raw log 等字段，后端应拒绝该计划，而不是尝试执行。

### 9.6 coding worker 接触了过多状态

优先检查：

- PM/Coder/Executor/QA/Debugger 是否通过 `coding/worker_payloads.py` 构造局部 payload。
- Debugger payload 不应包含 `raw_error_ref`、`raw_error`、`stdout/stderr`、`workflow_trace` 或完整 `action_result`。
- QA 可以接收 `raw_error_ref`，但不能接收 raw artifact 正文。
- 当前 LangGraph `Send` 只作为 `CodingWorkerPayload.to_send()` 适配点保留；如果后续真正改成 Send 调度，必须先定义 state reducer，避免覆盖主 trace。

### 9.7 token 消耗异常

优先检查：

- `CHAT_CONTEXT_MAX_CHARS`
- `CHAT_EXTERNAL_CONTEXT_MAX_CHARS`
- `CONVERSATION_CONTEXT_RECENT_MESSAGES`
- `CONVERSATION_RECENT_MESSAGE_MAX_CHARS`
- `CONVERSATION_SUMMARY_MAX_CHARS`

简单聊天不应携带完整工程日志、完整 run output 或完整 diagnostics trace。

## 10. 自动化验收入口

当前核心自动化测试：

- `backend/tests/test_agent_loop_acceptance.py`
- `backend/tests/test_agent_loop_graph.py`
- `backend/tests/test_agent_actions.py`
- `backend/tests/test_workspace_tools.py`
- `backend/tests/test_conversation_store.py`
- `backend/tests/test_llm_client.py`

推荐提交前执行：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```
