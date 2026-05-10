# 后端目录与模块地图

本文档只解释“代码应该去哪里找、以后应该往哪里放”，不重复接口字段细节。接口契约请看 [`docs/backend-api-specification.md`](./backend-api-specification.md)。

## 1. 总体分层

当前后端可以按下面的层次理解：

1. `main.py`
2. `api/`
3. `services/`
4. `agent_workflow/`、`llm/`、`storage/`、`tools/`、`messaging/`
5. `workspace/`

职责边界：

- `main.py` 负责启动应用、注册路由、挂载 lifespan
- `api/` 负责把 HTTP / WebSocket 请求翻译成后端调用
- `services/` 负责稳定的业务入口，避免路由直接深入内部细节
- `agent_workflow/` 负责 Agent 图编排与诊断逻辑
- `llm/`、`storage/`、`tools/`、`messaging/` 提供基础能力
- `workspace/` 只保存运行时产物，不放源码

## 2. 顶层目录

```text
backend/
  app/
  tests/
  workspace/
  .env.example
  requirements.txt
  README.md
```

说明：

- `backend/app/`：后端源码主目录
- `backend/tests/`：后端自动化测试
- `backend/workspace/`：运行时文件，当前主要包含 `runs/` 与 `conversations/`
- `backend/.env.example`：环境变量模板
- `backend/requirements.txt`：Python 依赖

## 3. `app/` 目录结构

```text
backend/app/
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
```

### 3.1 `main.py`

用途：

- 创建 FastAPI app
- 注册异常处理器
- 挂载各类路由
- 在启动阶段做会话清理与 run 恢复

不应该放在这里的内容：

- 具体业务逻辑
- 文件系统读写细节
- LLM 调用细节

### 3.2 `schemas.py`

用途：

- 定义 API 请求 / 响应模型
- 为路由层、服务层、测试提供统一契约

适合放这里的内容：

- Pydantic 模型
- 结构化返回对象

不适合放这里的内容：

- 业务流程
- 持久化逻辑

### 3.3 `message_queue.py`

用途：

- 保存后端统一消息队列
- 支持轮询增量拉取
- 支持 WebSocket 推送的基础消息源

## 4. `api/` 路由层

当前文件：

- `health_routes.py`
- `llm_routes.py`
- `chat_routes.py`
- `run_routes.py`
- `message_routes.py`
- `agent_routes.py`
- `run_dependencies.py`
- `query_params.py`
- `route_support.py`
- `error_handlers.py`
- `error_responses.py`

职责：

- 接收请求
- 参数校验
- 调用 `services/`
- 统一返回 HTTP / WebSocket 响应

建议：

- 新增接口时，优先在这里加路由
- 路由内部不要直接操作 `storage/`、`tools/`、`llm/`
- 复杂分支逻辑应下沉到 `services/`

## 5. `services/` 业务入口层

当前结构：

```text
backend/app/services/
  chat_interface.py
  run_interface.py
  character_interface.py
  chat_action/
  run_action/
  character_action/
```

设计意图：

- `*_interface.py` 作为稳定入口
- `*_action/` 负责该领域内部的细分逻辑

### 5.1 `chat_interface.py`

职责：

- 提供聊天主入口
- 协调测试命令、意图判断、会话记忆、聊天消息发送、coding 任务调度

它更像“聊天业务门面”，而不是单一算法文件。

### 5.2 `chat_action/`

当前文件：

- `intent.py`：判断 `chat / coding / unknown`
- `agent.py`：对接 Agent workflow 或 LLM 回复
- `test_commands.py`：处理 `/test ...` 类开发命令
- `types.py`：聊天领域结果模型

适合继续放这里的内容：

- 聊天意图预处理
- 聊天输出组装
- 与聊天链路强相关的辅助类型

### 5.3 `run_interface.py`

职责：

- 提供 run 的创建、执行、取消、重试、重跑、查询、恢复等稳定入口
- 向 API 层暴露相对平整的调用面

### 5.4 `run_action/`

当前文件：

- `lifecycle.py`：run 生命周期推进
- `execution.py`：脚本执行
- `codegen.py`：代码生成相关逻辑
- `control.py`：取消与执行控制
- `queries.py`：查询与读取逻辑
- `recovery.py`：启动恢复
- `formatters.py`：run 结果格式化
- `types.py`：run 领域类型

适合继续放这里的内容：

- 新的执行阶段
- 新的 run 状态转换逻辑
- 新的 run 查询视图

### 5.5 `character_interface.py` 与 `character_action/`

职责：

- 把业务阶段转换成桌宠消息
- 统一发送 `quip`、`expression`、`motion`、`status`

当前 `character_action/events.py` 保存的是角色事件预设。

## 6. `agent_workflow/` Agent 编排层

这是当前后端最复杂的目录，建议按“职责簇”理解，而不是按单文件硬记。

当前 `agent_workflow/` 根目录只保留包入口和必要 facade，真实实现已经下沉到各职责子包。新代码应直接使用子包路径，不再依赖旧根目录模块名。

### 6.1 图构建与主流程

```text
agent_workflow/
  graph/
    agent_graph.py
    builder_support.py
    graph_support.py
```

职责：

- `graph/agent_graph.py`：搭建主 LangGraph Agent Brain，包含 router、chat、coding、tool、run 和 roleplay 主节点
- `graph/builder_support.py`：组装 coding/run/tool 节点所需的 state 更新
- `graph/graph_support.py`：注册节点、保护节点异常、配置图边

### 6.2 共享契约与节点映射

```text
agent_workflow/
  contracts/
    workflow_nodes.py
    workflow_results.py
    node_mappings.py
```

职责：

- `contracts/workflow_nodes.py`：保存 workflow 节点常量、终态节点映射和节点元信息
- `contracts/workflow_results.py`：保存 Agent / Summary / Repair workflow 的结构化结果模型与 graph invoke 收口 helper
- `contracts/node_mappings.py`：保存节点到 quip / expression 的映射和是否发送 chat message 的规则

### 6.3 路由、状态与基础常量

```text
agent_workflow/
  state/
    constants.py
    routing.py
    run_state.py
    run_support.py
    state_support.py
  agent_support.py
```

职责：

- `state/constants.py`：保存 Agent workflow 内部 action/status 常量
- `state/routing.py`：根据 intent、run action 和 ui_status 选择下一个节点
- `state/run_state.py`：封装 run 相关状态字段快照与更新
- `state/run_support.py`：封装 run_id 解析、snapshot 读取和 run control 调度
- `state/state_support.py`：封装 Agent state merge、trace 追加、初始 state 和 graph invoke
- `agent_support.py`：主 Agent helper facade，聚合 graph / state / output 中仍需要统一暴露的内部 helper

### 6.4 summary 工作流

```text
agent_workflow/
  summary/
    run_summary_graph.py
    attempt_summary_graph.py
    support.py
```

职责：

- `summary/run_summary_graph.py`：读取终态 run record，生成用户可读 run 总结
- `summary/attempt_summary_graph.py`：整理 repair retry attempt 的结果和下一步建议
- `summary/support.py`：收口 summary prompt、文本解析、roleplay 节点和 fallback 发消息逻辑

边界约束：

- 新增 summary 类子图，优先放入 `summary/`
- 修改 run / attempt summary 行为，优先改 `summary/run_summary_graph.py` 或 `summary/attempt_summary_graph.py`
- 修改通用 summary helper，优先改 `summary/support.py`

### 6.5 repair 工作流

```text
agent_workflow/
  repair/
    repair_decision_graph.py
    support.py
    retry_guidance.py
```

职责：

- `repair/repair_decision_graph.py`：分析执行失败，决定是否进入自动修复，并在执行模式下生成修复脚本
- `repair/support.py`：收口 repair state、eligibility、feedback、invoke 和 graph next-step 逻辑
- `repair/retry_guidance.py`：根据 retry / repair 节点生成下一步指导

边界约束：

- 修改失败分析与修复决策，优先改 `repair/repair_decision_graph.py`
- 修改 repair state 或 graph 控制流 helper，优先改 `repair/support.py`
- 修改 retry 节点下一步文案，优先改 `repair/retry_guidance.py`

### 6.6 输出与文案收口

```text
agent_workflow/
  output/
    roleplay.py
    text.py
```

职责：

- `output/roleplay.py`：把工作流结果发送为用户可见聊天消息
- `output/text.py`：收口 run 创建、查询、控制、未知意图等用户可见文案

### 6.7 诊断

```text
agent_workflow/
  diagnostics/
    runtime.py
    failure.py
    support.py
  trace/
    runtime.py
    messages.py
```

职责：

- `diagnostics/runtime.py`：提供 Agent 诊断入口，负责 preview / runtime diagnostics 的流程编排
- `diagnostics/failure.py`：把失败事件转换成稳定 `error_code`、`failure_domain` 和中文摘要
- `diagnostics/support.py`：负责 workspace tool 诊断快照，以及 workspace tool 相关响应字段组装
- `trace/runtime.py`：负责 `workflow_trace` 的 runtime metadata、entry 构造、归一化、失败 trace 查找和事件聚合
- `trace/messages.py`：负责 trace 的中文标签、严重级别和可读节点日志文案
- `diagnostics.py` 已由 `diagnostics/` 包替代，`from agent_workflow.diagnostics import ...` 会进入新包

边界约束：

- 新增 trace 事件元信息，优先改 `trace/runtime.py`
- 新增 trace 展示文案，优先改 `trace/messages.py`
- 新增 diagnostics 失败类型，优先改 `diagnostics/failure.py`
- 新增 workspace tool 诊断字段，优先改 `diagnostics/support.py`
- `diagnostics/runtime.py` 应尽量保持为流程编排，不再堆叠字段组装和文案分支

## 7. `llm/`、`storage/`、`tools/`、`messaging/`

### 7.1 `llm/client.py`

职责：

- 对接 OpenAI-compatible `/chat/completions`
- 管理主模型与 fallback 模型
- 提供连接诊断与错误分类

这里应该只处理“如何调用模型”，不处理业务路由。

### 7.2 `storage/`

当前文件：

- `conversation_store.py`
- `run_store.py`

职责：

- 会话持久化
- run 记录持久化
- 供 `services/` 查询与更新

### 7.3 `tools/`

当前文件：

- `safe_fs.py`
- `safe_execute_command.py`
- `workspace_tools.py`
- `workspace_tool_models.py`

职责：

- 管理 workspace 边界
- 阻止危险命令
- 为 Agent 或 run 提供受限本地工具

所有涉及本地文件和命令的高风险能力，应优先落在这里统一约束。

### 7.4 `messaging/`

当前文件：

- `message_sender.py`
- `event_types.py`
- `runtime_events.py`

职责：

- 统一包装并发送业务消息
- 避免各业务模块自己拼消息结构
- 维护 runtime event 的稳定枚举和字段构造规则

## 8. 两条主调用链

### 8.1 聊天链路

```text
/chat
  -> api/chat_routes.py
  -> services/chat_interface.py
  -> services/chat_action/*
  -> agent_workflow/* 或 llm/client.py
  -> messaging/message_sender.py
  -> /messages 或 /messages/ws
```

### 8.2 代码任务链路

```text
/runs
  -> api/run_routes.py
  -> services/run_interface.py
  -> services/run_action/*
  -> storage/run_store.py
  -> tools/safe_fs.py + tools/safe_execute_command.py
  -> messaging/message_sender.py
```

## 9. 新代码应该放哪里

可以按下面的规则判断：

- 新增 HTTP 接口：放 `app/api/`
- 复用现有聊天主线：先看 `chat_interface.py` 与 `chat_action/`
- 复用现有 run 主线：先看 `run_interface.py` 与 `run_action/`
- 新增 Agent 节点、图分支、诊断：放 `agent_workflow/`
- 新增持久化能力：放 `storage/`
- 新增本地命令或文件工具：放 `tools/`
- 新增桌宠行为消息：放 `character_interface.py` 与 `character_action/`
- 新增消息结构化发送：放 `messaging/`

## 10. 当前结构下的几个约束

- 不要把业务逻辑重新塞回 `main.py`
- 不要让 `api/` 直接调用 `safe_fs.py` 或 `run_store.py`
- 不要在 `workspace/` 里放源码
- 不要绕过 `message_sender.py` 到处手写消息结构
- 不要在业务层直接拼 OpenAI 请求，统一走 `llm/client.py`

如果后续还要继续拆分目录，优先保持“路由层 -> 接口层 -> 动作层 -> 基础能力层”这个结构不变。
