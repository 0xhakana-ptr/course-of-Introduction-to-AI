# AI Agent Backend API Specification

本文档描述的是当前仓库中已经实现并验证过的后端接口与内部通信边界，基于 2026-05-07 当前代码状态整理。

## 1. 当前后端结构

后端主入口：

- `backend/app/main.py`

当前服务层已经整理为“接口层 + 动作层”结构：

- `backend/app/services/chat_interface.py`
- `backend/app/services/chat_action/`
- `backend/app/services/character_interface.py`
- `backend/app/services/character_action/`
- `backend/app/services/run_interface.py`
- `backend/app/services/run_action/`
- `backend/app/agent_workflow/`

相关基础模块：

- `backend/app/llm/client.py`
- `backend/app/message_queue.py`
- `backend/app/messaging/message_sender.py`
- `backend/app/storage/conversation_store.py`
- `backend/app/storage/run_store.py`
- `backend/app/tools/safe_fs.py`
- `backend/app/tools/safe_execute_command.py`

## 2. 当前能力边界

### 2.1 聊天链路

`/chat` 当前支持三类意图：

- `chat`
- `coding`
- `unknown`

其中：

- `chat` 会进入最小 LangGraph Agent Brain，由 Chat Node 调用 OpenAI-compatible LLM 接口，并复用后端会话记忆。
- `coding` 会进入最小 LangGraph Agent Brain，再由 Run Tool Node 创建 run。
- `unknown` 会返回引导性回复。

说明：

- 普通聊天和 coding 分支都已经不再绕开 `agent_workflow`，而是进入最小 LangGraph 图。
- 当前主路径分别是 `router -> chat_node -> roleplay_node` 与 `router -> coding_node -> run_tool_node -> roleplay_node`。
- `agent_workflow` 当前已经开始记录统一的 `workflow_trace`，用于后续 diagnostics/debug 观察节点路由、阶段状态与 run action 决策。
- `/chat` 命中 coding intent 时会返回 `run_id`，并通过 FastAPI 后台任务触发 `execute_run`。
- 当前实现是最小 LangGraph Agent Brain，不等同于完整的多 Agent 公司化协同系统。
- `agent_workflow` 通过 lazy import 暴露，缺少依赖时不会阻塞主服务启动。
- `/chat` 支持轻量会话记忆。请求可传 `session_id`，响应会返回 `session_id`。
- 后端会保存同一会话中的最近若干轮消息，并在下一次聊天时自动拼入上下文。
- 会话元信息当前可以通过 `GET /chat/sessions` 和 `GET /chat/sessions/{session_id}` 直接观察；其中会暴露 `has_summary_cache` 与 `context_strategy_version`，便于排查长会话压缩和摘要缓存是否生效。

### 2.2 任务执行链路

`/runs` 链路当前支持：

- 创建任务
- 后台执行
- 本地模板 fallback
- LLM 自动修复失败脚本
- 基于历史任务创建 `retry / rerun`
- 真实取消 `cancel`
- 查询尝试记录
- 查询脚本内容
- 分块读取 stdout / stderr / error
- 查询运行日志
- 启动恢复

### 2.3 角色事件链路

后端已经引入角色事件服务，用于统一桌宠表现消息。

当前入口：

- `backend/app/services/character_interface.py`

当前事件预设：

- `chat_started`
- `chat_done`
- `chat_failed`
- `task_queued`
- `task_started`
- `task_repairing`
- `task_done`
- `task_failed`
- `task_cancelled`

角色事件服务会把业务阶段转换为一组稳定消息：

- `quip`：字幕短句
- `expression`：表情标签
- `motion`：动作 ID，当前预留
- `status`：任务状态

当前已接入：

- `/chat` 普通聊天开始与结束
- `/runs` 排队、开始、修复、完成、失败、取消

### 2.4 消息队列链路

当前通过轮询接口提供消息：

- `GET /messages`
- `DELETE /messages`

当前同时提供正式 WebSocket 消息流入口：

- `WS /messages/ws`

消息队列特性：

- 自动生成 `_id`
- 自动生成 `_timestamp`
- 支持 `since_id` 增量拉取
- 线程安全
- 队列上限 `1000`
- 支持桌宠消息类型：`quip`、`expression`、`motion`、`chat`、`error`、`status`
- WebSocket 连接建立后会先发送一次当前快照，此后再持续推送增量消息批次

### 2.5 LLM 能力

当前 LLM 调用基于 OpenAI-compatible 接口实现，支持：

- 主 provider
- fallback provider
- 远程诊断
- 请求超时提示
- 不可重试 / 可重试错误区分

## 3. API 列表

### 3.1 `GET /health`

用途：

- 健康检查
- 返回启动恢复统计

返回示例：

```json
{
  "ok": true,
  "service": "backend",
  "version": "0.2.0",
  "startup_recovery": {
    "checked_at": "2026-05-06T08:00:00+00:00",
    "scanned_count": 0,
    "recovered_count": 0,
    "recovered_run_ids": []
  }
}
```

### 3.2 `GET /llm/diagnostics`

查询参数：

- `check_remote: bool = false`

用途：

- 检查本地 LLM 配置是否完整
- 可选远程探测主 / 备模型连通性

返回字段包括：

- `configured`
- `api_key_present`
- `base_url`
- `resolved_url`
- `model`
- `timeout_seconds`
- `fallback_configured`
- `fallback_model`
- `request_ok`
- `status_code`
- `response_preview`
- `error_message`
- `provider_used`
- `fallback_used`

### 3.2.1 `POST /agent/diagnostics/preview`

请求体：

```json
{
  "prompt": "请取消 run_id 123e4567-e89b-12d3-a456-426614174000",
  "context": null,
  "intent": null
}
```

用途：

- 以无副作用方式预览当前输入会如何进入 `agent_workflow`
- 观察当前会命中的 `intent`、`run_action`、`workspace tool` 规划结果与预期节点路径
- 调试为什么某条输入会被判定为 `chat / coding / unknown`

说明：

- 该接口不会真正创建 run，也不会真的执行 `retry / rerun / cancel`
- 该接口主要面向开发期调试与联调，不用于前端正式主链路

返回字段包括：

- `intent`
- `selected_route`
- `run_action`
- `target_run_id`
- `workspace_tool_name`
- `workspace_tool_reason`
- `workspace_tool_plan`
- `ui_status`
- `planned_nodes`
- `notes`
- `debug_summary`
- `workflow_trace`

补充说明：

- `workflow_trace` 中的每一项除了原始 `node / event / ui_status / details` 外，还会补充：
  - `node_label`：节点中文标签，便于直接阅读
  - `phase`：稳定的英文阶段标识，便于程序判断
  - `event_label`：事件中文短标签，便于快速扫描
  - `status_level`：节点日志级别，当前为 `info / warning / error`
  - `message`：面向开发调试的节点级中文摘要
- `debug_summary` 会进一步聚合 `*_node_label`、`*_phase` 以及失败时的 `failure_code / failure_domain`，用于快速定位“问题发生在哪个阶段、属于哪类故障”

返回体示例：

```json
{
  "ok": true,
  "prompt": "请取消 run_id 123e4567-e89b-12d3-a456-426614174000",
  "intent": "coding",
  "selected_route": "coding_node",
  "run_action": "cancel",
  "target_run_id": "123e4567-e89b-12d3-a456-426614174000",
  "workspace_tool_name": null,
  "workspace_tool_reason": null,
  "workspace_tool_plan": null,
  "ui_status": "coding_requested",
  "planned_nodes": [
    "router",
    "coding_node",
    "run_control_node",
    "roleplay_node"
  ],
  "notes": [
    "该输入会进入 coding_node，并对已有 run 执行 `cancel` 控制动作。"
  ],
  "workflow_trace": [
    {
      "step": 1,
      "node": "router",
      "node_label": "意图路由",
      "phase": "routing",
      "event": "intent_routed",
      "event_label": "意图已路由",
      "status_level": "info",
      "message": "意图路由已将输入路由到 `coding` 意图。",
      "ui_status": "routed",
      "details": {
        "intent": "coding"
      }
    },
    {
      "step": 2,
      "node": "coding_node",
      "node_label": "代码任务预处理",
      "phase": "coding",
      "event": "coding_request_prepared",
      "event_label": "代码任务请求已解析",
      "status_level": "info",
      "message": "代码任务预处理已解析 coding 请求，动作为 `cancel`，目标 run_id 为 `123e4567-e89b-12d3-a456-426614174000`。",
      "ui_status": "coding_requested",
      "details": {
        "run_action": "cancel",
        "target_run_id": "123e4567-e89b-12d3-a456-426614174000",
        "workspace_tool_name": null
      }
    }
  ],
  "debug_summary": {
    "trace_count": 3,
    "first_node": "router",
    "first_node_label": "意图路由",
    "last_node": "diagnostics_preview",
    "last_node_label": "诊断预览",
    "terminal_node": "diagnostics_preview",
    "terminal_node_label": "诊断预览",
    "last_event": "coding_path_selected",
    "last_ui_status": "coding_requested",
    "last_phase": "diagnostics",
    "failure_node": null,
    "failure_node_label": null,
    "failure_event": null,
    "failure_phase": null,
    "failure_code": null,
    "failure_domain": null,
    "blocked": false,
    "error_present": false
  },
  "error_context": null
}
```

### 3.2.2 `POST /agent/diagnostics/run`

请求体：

```json
{
  "prompt": "请查看 run_id 123e4567-e89b-12d3-a456-426614174000 的状态",
  "context": null,
  "intent": null
}
```

用途：

- 在更接近真实运行期的前提下执行一遍安全的 Agent workflow 分支
- 返回真实 `output / error / ui_status / workflow_trace`
- 用于排查某条输入在真实 `agent_workflow` 中到底如何收口

当前默认允许执行的分支：

- `chat`
- `unknown`
- `coding + inspect`

当前默认拦截的分支：

- `coding + create`
- `coding + retry`
- `coding + rerun`
- `coding + cancel`

说明：

- 拦截这些分支是为了避免 diagnostics 接口意外创建 run 或修改已有任务状态
- 对于被拦截的输入，仍会返回 preview 级别的 `planned_nodes` 和 `workflow_trace`，并给出 `blocked_reason`

返回字段包括：

- `ok`
- `executable`
- `executed`
- `blocked_reason`
- `output`
- `error`
- `run_id`
- `run_status`
- `ui_status`
- `planned_nodes`
- `notes`
- `debug_summary`
- `error_context`
- `workflow_trace`

补充说明：

- 无论是 `preview` 级 trace，还是实际运行期 diagnostics 返回的 trace，当前都会统一补充 `node_label` 与 `phase`。
- 当前 `workflow_trace` 已经可以直接作为“节点级日志”阅读：请求方可优先查看 `event_label / status_level / message`，只有需要更细字段时再回退到 `details`。
- 当运行失败，或 diagnostics 因安全原因被主动拦截时，`debug_summary` 与 `error_context` 会优先给出：
  - `failure_node`
  - `failure_node_label`
  - `failure_event`
  - `failure_phase`
  - `failure_code`
  - `failure_domain`
- `error_context` 当前还会返回：
  - `summary`：统一中文故障摘要
  - `error_code`：稳定英文错误码
  - `failure_domain`：稳定故障域，便于前端或调试端分类显示

返回体示例：

```json
{
  "ok": true,
  "prompt": "hello",
  "intent": "chat",
  "selected_route": "chat_node",
  "run_action": null,
  "executable": true,
  "executed": true,
  "blocked_reason": null,
  "run_id": null,
  "run_status": null,
  "output": "reply to hello",
  "error": null,
  "ui_status": "chat_done",
  "planned_nodes": [
    "router",
    "chat_node",
    "roleplay_node"
  ],
  "notes": [
    "该输入会进入 chat_node，并调用当前 LLM client 生成回复。"
  ],
  "debug_summary": {
    "trace_count": 3,
    "first_node": "router",
    "first_node_label": "意图路由",
    "last_node": "roleplay_node",
    "last_node_label": "角色收口",
    "terminal_node": "roleplay_node",
    "terminal_node_label": "角色收口",
    "last_event": "roleplay_emit",
    "last_ui_status": "chat_done",
    "last_phase": "roleplay",
    "failure_node": null,
    "failure_node_label": null,
    "failure_event": null,
    "failure_phase": null,
    "failure_code": null,
    "failure_domain": null,
    "blocked": false,
    "error_present": false
  },
  "error_context": null,
  "workflow_trace": [
    {
      "step": 1,
      "node": "router",
      "node_label": "意图路由",
      "phase": "routing",
      "event": "intent_routed",
      "event_label": "意图已路由",
      "status_level": "info",
      "message": "意图路由已将输入路由到 `chat` 意图。",
      "ui_status": "routed",
      "details": {
        "intent": "chat"
      }
    },
    {
      "step": 2,
      "node": "chat_node",
      "node_label": "聊天回复",
      "phase": "chat",
      "event": "llm_response_ready",
      "event_label": "聊天回复完成",
      "status_level": "info",
      "message": "聊天回复已完成 LLM 回复生成。",
      "ui_status": "chat_done",
      "details": {
        "has_error": false
      }
    },
    {
      "step": 3,
      "node": "roleplay_node",
      "node_label": "角色收口",
      "phase": "roleplay",
      "event": "roleplay_emit",
      "event_label": "角色收口已发送",
      "status_level": "info",
      "message": "角色收口已完成最终输出收口。",
      "ui_status": "chat_done",
      "details": {
        "node_name": "agent_roleplay"
      }
    }
  ]
}
```

说明补充：

- `debug_summary` 用于快速概览这次 diagnostics 最终走到了哪个节点、最后一个事件是什么、是否存在错误、是否属于被主动拦截的路径。
- `error_context` 用于在运行期 diagnostics 失败或被拦截时，直接给出失败节点、失败节点标签、失败事件、失败阶段、稳定错误码、故障域、统一摘要和下一步建议，避免只看原始 trace 才能定位。
- 当前 `agent_workflow` 主节点已经接入统一的 node exception guard：如果某个 node 直接抛异常，后端会将其收口为 `workflow_node_failed` 状态，并在 trace 中记录 `node_exception`，而不是让整条 LangGraph 链路直接静默中断。

### 3.3 `POST /chat`

请求体：

```json
{
  "prompt": "hello",
  "context": null,
  "session_id": null
}
```

返回体：

```json
{
  "ok": true,
  "intent": "chat",
  "output": "response text",
  "error": null,
  "session_id": "session id",
  "run_id": null
}
```

补充说明：

- `/test ...` 命令也通过 `/chat` 入口处理。
- 测试命令会向消息队列写入消息，不依赖真实 LLM。
- 如果请求不传 `session_id`，后端会自动创建新会话。
- 如果请求传入已有 `session_id`，后端会把该会话最近消息作为上下文传给 LLM。
- 请求中的 `context` 仍然保留，用于兼容当前前端传入的临时上下文。
- 当 `intent` 为 `coding` 时，`run_id` 会返回本次创建的任务 ID；普通聊天和 unknown intent 通常为 `null`。
- coding 任务的执行状态继续通过 `GET /runs/{run_id}`、`GET /runs/{run_id}/snapshot`、`GET /runs/{run_id}/attempts` 和 `GET /messages` 查询。
- 对于直接通过 `/chat` 返回的聊天正文，后端不会再额外向消息队列重复写入同一条 `agent:chat`，以避免聊天窗口重复显示。
- 如果 coding 请求中包含合法 `run_id` 且语义更接近“查看状态 / 快照 / 日志 / 进度”，LangGraph 会直接读取已有 run 的 snapshot 并返回，而不是再次创建新任务。

### 3.4.1 `GET /chat/sessions`

查询参数：

- `offset`
- `limit`

用途：

- 分页查看最近持久化的聊天会话元信息
- 观察哪些会话已经触发上下文压缩或生成摘要缓存

返回体示例：

```json
{
  "ok": true,
  "total": 2,
  "offset": 0,
  "limit": 20,
  "items": [
    {
      "session_id": "session id",
      "message_count": 4,
      "recent_message_count": 2,
      "compressed_message_count": 2,
      "has_compressed_context": true,
      "has_summary_cache": true,
      "summary_preview": "User: hello...",
      "context_strategy_version": 1,
      "last_message_at": "2026-05-08T08:00:00+00:00",
      "updated_at": "2026-05-08T08:00:00+00:00"
    }
  ]
}
```

### 3.4.2 `GET /chat/sessions/{session_id}`

用途：

- 查看单个会话的后端记忆元信息
- 确认当前会话是否已经触发长历史压缩或摘要缓存

返回体示例：

```json
{
  "ok": true,
  "session_id": "session id",
  "exists": true,
  "message_count": 6,
  "recent_message_count": 2,
  "compressed_message_count": 4,
  "has_compressed_context": true,
  "has_summary_cache": true,
  "summary_preview": "User: first hello...",
  "context_strategy_version": 1,
  "last_message_at": "2026-05-08T08:00:00+00:00",
  "updated_at": "2026-05-08T08:00:00+00:00"
}
```

### 3.4.3 `DELETE /chat/sessions/{session_id}`

用途：

- 清空指定聊天会话的后端记忆

返回体：

```json
{
  "ok": true,
  "session_id": "session id",
  "cleared": true,
  "message": "会话已清空。"
}
```

### 3.5 `POST /runs`

请求体：

```json
{
  "prompt": "build a calculator demo",
  "context": null
}
```

用途：

- 创建一个后台任务
- 立即返回 `RunResponse`
- 后续由后台任务执行 `execute_run`

### 3.6 `GET /runs`

用途：

- 返回完整任务列表

返回类型：

- `list[RunResponse]`

### 3.7 `GET /runs/summary`

查询参数：

- `offset`
- `limit`

用途：

- 返回轻量任务摘要

### 3.8 `GET /runs/{run_id}`

用途：

- 获取单个任务完整状态

### 3.9 `GET /runs/{run_id}/snapshot`

用途：

- 获取面向 Agent / 前端状态展示的结构化任务快照
- 用更轻量的方式观察任务当前是否仍在进行、最近一次 attempt 的摘要，以及推荐的下一步动作

返回体示例：

```json
{
  "run_id": "run_demo_1",
  "status": "running",
  "summary": "任务正在执行中。最近一次尝试：第 1 次尝试（本地模板）：正在执行。",
  "next_action": "继续轮询任务状态；如需定位问题，可查看最近一次尝试的输出或日志。",
  "terminal": false,
  "in_progress": true,
  "cancel_requested": false,
  "attempt_count": 1,
  "repair_count": 0,
  "latest_attempt_number": 1,
  "latest_attempt_status": "running",
  "latest_attempt_summary": "第 1 次尝试（本地模板）：正在执行。",
  "updated_at": "2026-05-08T08:00:00+00:00"
}
```

### 3.10 `GET /runs/{run_id}/attempts`

用途：

- 获取该任务的尝试列表

### 3.11 `GET /runs/{run_id}/attempts/{attempt_number}`

用途：

- 获取单次尝试详情

### 3.12 `GET /runs/{run_id}/attempts/{attempt_number}/script`

用途：

- 获取某次尝试生成的脚本内容

### 3.13 `GET /runs/{run_id}/attempts/{attempt_number}/output`

查询参数：

- `stream`: `stdout | stderr | error`
- `offset`
- `limit`

用途：

- 分块读取单次尝试输出

### 3.14 `GET /runs/{run_id}/logs`

用途：

- 获取单个任务的完整文本日志

### 3.14 `GET /messages`

查询参数：

- `since_id` 可选

返回体：

```json
{
  "ok": true,
  "messages": [
    {
      "_id": "msg_168xxxx",
      "_timestamp": "2026-05-06T08:00:00Z",
      "_channel": "agent:chat",
      "type": "chat",
      "content": "hello"
    }
  ],
  "count": 1
}
```

### 3.15 `WS /messages/ws`

查询参数：

- `since_id` 可选

用途：

- 建立正式的消息流订阅连接
- 连接建立后先返回一批当前快照消息
- 之后持续推送自上次消息 ID 之后产生的增量消息

首批返回体示例：

```json
{
  "ok": true,
  "messages": [
    {
      "_id": "msg_168xxxx",
      "_timestamp": "2026-05-08T08:00:00Z",
      "_channel": "agent:chat",
      "type": "chat",
      "content": "hello"
    }
  ],
  "count": 1
}
```

说明：

- 如果连接时消息队列为空，首批快照会返回空数组。
- 如果带上 `since_id`，首批快照只会返回该消息之后的增量内容。
- 当前 WebSocket 推送的数据结构与 `GET /messages` 保持一致，便于前端复用解析逻辑。

### 3.16 `DELETE /messages`

用途：

- 清空消息队列

返回体：

```json
{
  "ok": true,
  "message": "消息队列已清空"
}
```

### 3.17 `POST /runs/{run_id}/retry`

用途：

- 基于一个 `failed` 任务创建新的 follow-up run

行为说明：

- 只有源任务状态为 `failed` 时允许调用
- 返回新的 `RunResponse`
- 新 run 会保留原始 `prompt / context`
- 新 run 会记录 `source_run_id`
- 新 run 会记录 `trigger_mode=retry`

### 3.18 `POST /runs/{run_id}/rerun`

用途：

- 基于一个已完成或失败的任务重新创建新的 follow-up run

行为说明：

- 允许源任务状态为 `done` 或 `failed`
- 返回新的 `RunResponse`
- 新 run 会保留原始 `prompt / context`
- 新 run 会记录 `source_run_id`
- 新 run 会记录 `trigger_mode=rerun`

### 3.19 `POST /runs/{run_id}/cancel`

用途：

- 取消一个 `queued` 或 `running` 的任务

行为说明：

- 如果源任务状态为 `queued`，会直接标记为 `cancelled`
- 如果源任务状态为 `running`，会先登记 `cancel_requested=true`
- 后端会尝试终止当前本地 Python 子进程，避免“状态取消但进程仍在跑”的假取消
- 任务最终状态会落为 `cancelled`
- 如果任务已经是 `done`、`failed` 或 `cancelled`，会返回 `409`

## 4. 当前消息格式

当前 `/messages` 返回的每条消息都使用统一 envelope，对应 `MessageEnvelope`。

公共字段：

- `_id`：消息队列 ID，由后端自动生成
- `_timestamp`：入队时间，由后端自动生成
- `_channel`：前端分发通道
- `type`：消息语义类型
- `timestamp`：业务消息时间，可由发送方生成
- `node_name`：可选，用于标识触发消息的任务节点或后端阶段
- `metadata`：可选扩展字段

当前支持的 `_channel`：

- `agent:quip`
- `agent:expression`
- `agent:motion`
- `agent:chat`
- `agent:error`
- `agent:status`

当前支持的 `type`：

- `quip`：字幕窗口短句，适合轻量提示、吐槽、状态感知
- `expression`：Live2D 表情切换，优先传通用表情标签，例如 `开心`、`思考`
- `motion`：Live2D 动作播放，优先传前端 `list motions` 返回的 action id
- `chat`：聊天窗口专业回答或任务结果
- `error`：错误消息
- `status`：任务状态消息

### 4.1 `chat`

```json
{
  "_id": "msg_168xxxx",
  "_timestamp": "2026-05-06T08:00:00Z",
  "_channel": "agent:chat",
  "type": "chat",
  "timestamp": "2026-05-06T08:00:00Z",
  "node_name": "done",
  "metadata": {},
  "content": "text"
}
```

字段说明：

- `role`：`user | assistant | system`
- `content`：聊天文本
- `metadata.is_partial`：是否为分段消息
- `metadata.sequence_id` / `metadata.total_parts`：分段消息顺序信息

### 4.2 `quip`

```json
{
  "_channel": "agent:quip",
  "type": "quip",
  "content": "正在思考...",
  "node_name": "planning",
  "metadata": {
    "priority": "medium",
    "duration": 3000
  }
}
```

字段说明：

- `content`：字幕窗口显示文本
- `metadata.priority`：建议值 `low | medium | high`
- `metadata.duration`：建议显示时长，单位毫秒

### 4.3 `expression`

```json
{
  "_channel": "agent:expression",
  "type": "expression",
  "expression": "开心",
  "mode": "set",
  "intensity": 0.8,
  "node_name": "done",
  "metadata": {
    "duration": 5000,
    "transition": "smooth"
  }
}
```

字段说明：

- `expression`：推荐传通用表情标签，由前端映射到真实 Live2D 表情
- `mode`：`set | add`，默认建议为 `set`
- `intensity`：可选强度，范围建议 `0.0` 到 `1.0`
- `metadata.transition`：建议值 `smooth | instant`

### 4.4 `motion`

```json
{
  "_channel": "agent:motion",
  "type": "motion",
  "motion": "motion/@group/Idle/0",
  "node_name": "idle",
  "metadata": {
    "loop": false,
    "duration": 3000
  }
}
```

字段说明：

- `motion`：推荐传前端 `list motions` 返回的 action id
- `metadata.loop`：是否循环播放
- `metadata.duration`：动作语义建议时长，单位毫秒

说明：

- `motion` 当前作为正式后端消息协议保留，用于后续桌宠行为联调
- 如果前端暂未接入 `agent:motion` 分发，后端仍可先生成该协议消息并通过测试验证结构

### 4.5 `status`

```json
{
  "_channel": "agent:status",
  "type": "status",
  "status": "running",
  "progress": 30,
  "node_name": "coding"
}
```

字段说明：

- `status`：`idle | running | paused | done | error | cancelled`
- `progress`：可选进度，建议范围 `0` 到 `100`

### 4.6 `error`

```json
{
  "_channel": "agent:error",
  "type": "error",
  "code": "EXECUTION_FAILED",
  "message": "任务执行失败",
  "details": null,
  "node_name": "error"
}
```

字段说明：

- `code`：稳定错误码，供前端判断错误类型
- `message`：用户可见错误文案
- `details`：可选调试信息

## 5. 当前运行结果模型

### 5.1 `RunResponse`

核心字段：

- `run_id`
- `status`
- `output`
- `source_run_id`
- `trigger_mode`
- `cancel_requested`
- `generator`
- `attempt_count`
- `repair_attempted`
- `repair_count`
- `command`
- `returncode`
- `stdout`
- `stderr`
- `log_path`
- `artifacts`
- `attempts`

### 5.2 `RunAttemptResponse`

核心字段：

- `attempt_number`
- `generator`
- `repair_round`
- `status`
- `summary`
- `script_rel_path`
- `command`
- `cwd`
- `returncode`
- `stdout`
- `stderr`
- `error`
- `stdout_length`
- `stderr_length`
- `error_length`
- `stdout_truncated`
- `stderr_truncated`
- `error_truncated`

## 6. 安全工具边界

`safe_fs.py` 与 `safe_execute_command.py` 是后端内部工具，不是对外 HTTP API，但它们决定了 `runs` 链路的安全边界。

### 6.1 `safe_fs.py`

提供：

- `resolve_workspace_path`
- `safe_write_file`
- `safe_read_file`
- `safe_list_files`

当前安全约束：

- 所有路径必须落在 `settings.workspace_dir` 内
- 路径逃逸会抛出 `PermissionError`

### 6.2 `safe_execute_command.py`

提供：

- `normalize_command`
- `is_blocked_command`
- `safe_execute_command`

当前安全约束：

- 明确拦截 shell 类可执行文件：
  - `cmd`
  - `powershell`
  - `pwsh`
  - `sh`
  - `bash`
- 明确拦截危险参数 token：
  - `rm`
  - `rmdir`
  - `del`
  - `format`
  - `shutdown`
  - `taskkill`
  - `remove-item`
  - `/c`
  - `-c`
  - `-command`
  - `--command`
- 命令超时时返回结构化错误结果，而不是直接让进程崩掉

## 7. 当前自动化测试覆盖

当前后端已覆盖以下方向：

- `chat intent`
- `llm client` 主备链路
- `logging config`
- `message queue`
- `run` 成功 / 失败 / 修复 / 启动恢复
- `run cancel`
- `text utils`
- `safe tools`

## 8. 当前已知定位

### 8.1 稳定主线

当前稳定主线是：

- `/health`
- `/llm/diagnostics`
- `/chat`
- `/runs`
- `/messages`
- 最小 LangGraph coding intent 链路

### 8.2 实验性部分

以下能力目前仍更适合视作实验性或桥接态：

- 完整多 Agent 协同编排

它不会阻塞主服务启动，但也不应被文档表述为“已经完整稳定交付”。

### 8.3 当前 runs 执行控制说明

当前 `cancel` 已经作为正式 HTTP 接口接入，并具备真实执行控制：

- 执行中的 run 会登记到进程控制表
- `cancel` 会设置取消请求，并尝试终止对应的本地子进程
- 运行中的取消会先表现为 `cancel_requested=true`
- 最终任务状态会落为 `cancelled`

当前仍存在的边界是：

- 取消主要覆盖本地脚本执行阶段
- 如果任务正处于同步的 LLM 请求阶段，取消会在该阶段结束后尽快生效，而不是强制中断远程 HTTP 请求

## 9. 建议

后续如果继续扩展本文档，建议优先同步：

- `safe tools` 的更细测试结果
- `runs` 生命周期进一步扩展，例如更细粒度的 LLM 阶段取消
- 最小 LangGraph coding 链路继续扩展为 QA / Repair / Summary 节点后的契约变化
