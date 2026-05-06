# 后端通信接口与消息结构规范

## 1. 目的

本规范面向后端开发者，描述当前分支中后端与前端的通信接口、消息类型、数据格式，以及 `quip`/`expression` 与真正的 AI agent 聊天窗口消息的区分规则。

目标是：

- 封装后端未来通信接口，形成统一、可扩展的消息格式
- 优化后端对前端发送数据的表达方式
- 明确区分“节点装饰性消息”与“真实聊天消息”
- 保证 AI agent 工作流节点通知不会误导聊天窗口展示

---

## 2. 当前后端改动总结

### 2.1 接口层改动

- 新增 `GET /llm/diagnostics`：用于检查本地 LLM 配置并可选远程连通性测试
- 新增 `GET /runs/summary`：轻量级任务摘要列表接口，适合前端轮询
- `GET /health` 返回新增 `startup_recovery` 字段，记录启动时对遗留 `queued` / `running` 任务的恢复处理
- `POST /chat` 返回结构增加 `ok` 和 `error` 字段
- 新增消息队列接口：
  - `GET /messages`：读取后端待发送消息
  - `DELETE /messages`：清空消息队列

### 2.2 数据模型改动

- 新增 `RunSummaryResponse` / `RunSummaryListResponse`，用于前端列表页避免拉取完整 `RunResponse`
- `RunResponse` 结构更完整，新增 `generator`、`attempt_count`、`repair_attempted`、`repair_count`、`started_at`、`finished_at`、`duration_ms` 等字段
- `RunAttemptResponse` 结构更规范，包含 `stdout_length`/`stderr_length`/`error_length` 以及裁剪标志
- 新增 `ChatResponse.error`，用于上游 LLM 调用失败时返回详细错误信息

### 2.3 运行与存储改动

- 后端启动时会扫描 `runs/` 目录并将遗留 `queued` / `running` 任务统一标记为 `failed`
- 任务存储增加线程锁和原子写入，防止并发写入损坏
- 安全命令执行改为接收 `Sequence[str]`，并避免 `shell=True` 形式执行

### 2.4 消息系统改动

- 新增统一消息发送层 `backend/app/messaging/message_sender.py`
- 当前已支持消息类型：`quip`、`expression`、`chat`、`error`、`status`
- 每条消息会写入全局 `message_queue`，并附带 `_channel` 字段用于路由

---

## 3. 后端消息接口总体设计

后端消息通信分成两类：

1. **UI 装饰性事件**：`quip`、`expression`、`status`，用于表示 LangGraph 节点进入、状态变化、表情/表情动画等
2. **真实聊天消息**：`chat`，用于填充 AI agent 聊天窗口的文本内容

> 设计原则：
> - `quip` / `expression` 属于“Agent 过程性通知”，前端可在动画、节点气泡、状态栏展示
> - `chat` 属于“Agent 真实对话内容”，仅在聊天窗口中显示
> - 该区分确保当后端进入不同节点时，导航、表情、副文本不会直接出现在用户的聊天流中

---

## 4. 统一消息包格式

建议后端和前端约定一个统一的 envelope：

```json
{
  "_id": "msg_168xxxx",
  "_timestamp": "2026-05-06T08:00:00Z",
  "_channel": "agent:quip",
  "type": "quip",
  "node_name": "planning",
  "timestamp": "2026-05-06T08:00:00Z",
  "metadata": { ... },
  ...
}
```

当前代码实现方式为：

- `message_sender._send_to_frontend(channel, message)`
- `message_queue.add_message(message)`
- `message` 中带上 `_channel`

该设计既能让前端根据 `_channel` 快速路由，也能通过 `type` 统一区分消息语义。

### 4.1 核心字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | string | 唯一消息 ID，前端用于增量拉取|
| `_timestamp` | string | 消息入队时间|
| `_channel` | string | 路由通道，当前实现为 `agent:quip` / `agent:expression` / `agent:chat` / `agent:error` / `agent:status` |
| `type` | string | 业务类型：`quip` / `expression` / `chat` / `error` / `status` |
| `node_name` | string | 当前 LangGraph 节点名|
| `timestamp` | string | 事件发生时间|
| `metadata` | object | 类型相关辅助字段|

### 4.2 推荐扩展字段

虽然当前实现没有强制，但建议未来统一增加：

- `display_target`: `agent_chat` / `agent_overlay` / `agent_status` / `system`
- `event_id`: 可用于同一次长输出分片的连续性追踪
- `sequence_id`, `total_parts`: 用于长输出分片排序

---

## 5. 各类型消息说明

### 5.1 `quip`

用于节点切换时发送一句简短提示。

示例：

```json
{
  "type": "quip",
  "content": "进入 planning 节点，开始分析需求。",
  "node_name": "planning",
  "timestamp": "...",
  "metadata": {
    "priority": "medium",
    "duration": 3000
  },
  "_channel": "agent:quip"
}
```

- 仅用于流程提示
- 不应显示在 AI agent 聊天窗口里
- 前端可在状态栏、节点气泡、历史事件流中展示

### 5.2 `expression`

用于表情/动画状态变化。

示例：

```json
{
  "type": "expression",
  "expression": "thinking",
  "intensity": 0.8,
  "node_name": "planning",
  "timestamp": "...",
  "metadata": {
    "duration": 5000,
    "transition": "smooth"
  },
  "_channel": "agent:expression"
}
```

- 表情消息仅用于 UI 动画与角色表现
- 也不应进入聊天窗口文本流

### 5.3 `chat`

真实聊天窗口消息，才是 AI agent 的对话内容。

示例：

```json
{
  "type": "chat",
  "role": "assistant",
  "content": "这是最终输出内容。",
  "timestamp": "...",
  "metadata": {
    "is_partial": false,
    "sequence_id": 1,
    "total_parts": 1,
    "node_name": "done"
  },
  "_channel": "agent:chat"
}
```

- `is_partial=true` 表示当前为长输出分片
- `chat` 只有在“任务已完成”或“需要向用户展示实际文本输出时”才推送
- `quip` / `expression` 不应替代 `chat`

### 5.4 `status`

用于后台进度或状态更新。

示例：

```json
{
  "type": "status",
  "status": "running",
  "progress": 60,
  "node_name": "coding",
  "timestamp": "...",
  "_channel": "agent:status"
}
```

- 可用于进度条、状态标签、运行中提示
- 不属于聊天窗口内容

### 5.5 `error`

用于后端错误通知。

示例：

```json
{
  "type": "error",
  "code": "LLM_TIMEOUT",
  "message": "LLM 请求超时",
  "details": "...",
  "node_name": "coding",
  "timestamp": "...",
  "_channel": "agent:error"
}
```

- `error` 事件不应作为聊天消息直接显示为对话内容
- 应展示为系统/异常提示

---

## 6. 当前后端通信接口清单

### 6.1 Health / 状态检查

- `GET /health`
  - 返回 `ok`, `service`, `version`, `startup_recovery`
  - `startup_recovery` 表示启动时对遗留任务的恢复处理结果

### 6.2 LLM 诊断

- `GET /llm/diagnostics?check_remote=false`
  - 只检查本地配置读取情况
- `GET /llm/diagnostics?check_remote=true`
  - 执行一次最小远程 LLM 请求

返回字段包括：

- `configured`
- `api_key_present`
- `base_url`
- `resolved_url`
- `model`
- `timeout_seconds`
- `checked_remote`
- `request_ok`
- `status_code`
- `response_preview`
- `error_message`

### 6.3 Chat API

- `POST /chat`
  - 请求体：`{ "prompt": "...", "context": "..." }`
  - 响应体：`ChatResponse`
  - 结果包含：`ok`, `intent`, `output`, `error`

### 6.4 Run / 任务执行 API

- `POST /runs`
  - 创建任务，并在 `background_tasks` 中执行
- `GET /runs`
  - 返回完整任务列表，兼容现有前端流程
- `GET /runs/summary?offset=0&limit=20`
  - 返回轻量任务摘要列表，推荐前端列表页使用
- `GET /runs/{run_id}`
  - 返回单条任务完整信息
- `GET /runs/{run_id}/attempts`
  - 返回某个 run 的 attempt 列表
- `GET /runs/{run_id}/attempts/{attempt_number}`
  - 返回单次 attempt 详情
- `GET /runs/{run_id}/attempts/{attempt_number}/script`
  - 读取 attempt 对应脚本内容
- `GET /runs/{run_id}/attempts/{attempt_number}/output?stream=stdout&offset=0&limit=4000`
  - 分页读取输出内容
- `GET /runs/{run_id}/logs`
  - 读取任务日志

### 6.5 消息队列 API

- `GET /messages?since_id=<last_id>`
  - 拉取从 `since_id` 之后的新消息
- `DELETE /messages`
  - 清空消息队列

> 前端建议使用 `since_id` 增量拉取，避免重复消费。

---

## 7. 前后端通信方法

当前实现方式为：

1. 后端所有事件先写入后端全局 `message_queue`
2. 前端定期调用 `GET /messages?since_id=...` 轮询获取新事件
3. 前端根据 `_channel` / `type` 做路由与展示

### 7.1 现有后端实现文件

- `backend/app/message_queue.py`
  - 全局消息队列存储实现
- `backend/app/messaging/message_sender.py`
  - 消息发送抽象层，负责构造统一消息并写入队列
- `backend/app/main.py`
  - 暴露消息接口 `GET /messages` 和 `DELETE /messages`
- `backend/app/services/chat_service.py`
  - 在 LangGraph 节点运行时调用 `send_quip` / `send_expression` / `send_chat_message`
- `backend/app/mock_backend.py`
  - 本地测试脚本，用于验证消息队列和 WebSocket 广播行为

### 7.2 前端推荐实现方式

- `quip` 与 `expression`：
  - 前端只做 UI 装饰、节点提示、角色表情变化
  - 不应把它们直接当成聊天窗口消息展示
- `chat`：
  - 作为 AI agent 聊天窗口最终输出
  - 若 `metadata.is_partial=true`，需要支持分片拼接与实时增量展示
- `status`：
  - 仅用于状态条、进度条、运行状态提示
- `error`：
  - 用于系统异常提示，不直接写入对话历史

### 7.3 消息消费建议

- 每条消息必须包含 `_channel`，前端要基于 `_channel` 做首选路由
- 也可同时检查 `type` 进行语义判断，避免同一 channel 多态
- 推荐前端对 `chat` 做二次过滤：
  - 仅将 `type === 'chat'` 的消息写入聊天窗口
  - `content` 为空或只包含控制符时忽略

---

## 8. 未来扩展建议

### 8.1 追加 `display_target`

为了更明确区分展示目标，建议后续统一添加：

```json
"display_target": "agent_chat" | "agent_overlay" | "agent_status" | "system"
```

这样可以更清晰地区分消息用途，而不是只依赖 `type`。

### 8.2 统一事件包

建议后端未来对所有消息都使用同一个 `EventEnvelope`：

```json
{
  "_id": "...",
  "_channel": "agent:chat",
  "type": "chat",
  "node_name": "done",
  "timestamp": "...",
  "display_target": "agent_chat",
  "payload": { ... }
}
```

这个方案便于前端统一处理、记录日志、做审计。

### 8.3 长输出与分片

对于长输出，后端应明确约定：

- `metadata.is_partial=true`
- `metadata.sequence_id`
- `metadata.total_parts`
- 最后一条消息 `is_partial=false`

---

## 9. 结论

当前分支已经完成了后端对消息系统的初步封装：

- 增加了可诊断的 LLM 接口
- 增加了轻量任务摘要接口
- 增加了启动恢复能力
- 增加了统一消息队列与消息类型分离
- 明确支持 `quip` / `expression` / `chat` / `status` / `error`

接下来建议继续把 `message_sender` 的消息包规范化为统一 `EventEnvelope`，并在前端严格区分：

- `quip` / `expression` → UI 装饰/节点提示
- `chat` → AI agent 聊天窗口
- `status` / `error` → 系统状态／异常提示

这样就能满足“LangGraph 节点变化实时发出 quip 和表情，但 AI agent 聊天窗口只在真正有输出或长输出时才收到消息”的需求。