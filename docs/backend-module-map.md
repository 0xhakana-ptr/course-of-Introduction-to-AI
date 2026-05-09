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

### 6.1 图构建与主流程

- `agent_graph.py`
- `workflow_nodes.py`
- `workflow_results.py`
- `agent_builder_support.py`
- `agent_graph_support.py`

职责：

- 搭 LangGraph 图
- 定义节点之间如何衔接
- 统一工作流结果结构

### 6.2 路由、状态与基础常量

- `agent_support.py`
- `agent_routing_support.py`
- `agent_state_support.py`
- `agent_constants.py`
- `node_mappings.py`

职责：

- 统一工作流状态
- 管理节点名、状态名、映射关系
- 处理路由与节点级辅助逻辑

### 6.3 run 相关工作流

- `agent_run_support.py`
- `run_summary_graph.py`
- `attempt_summary_graph.py`
- `repair_decision_graph.py`
- `repair_support.py`
- `summary_support.py`
- `retry_guidance.py`

职责：

- 生成 run 摘要
- 生成 attempt 摘要
- 决定失败后是否修复、如何修复
- 提供 retry / repair 辅助信息

### 6.4 输出与文案收口

- `roleplay.py`
- `agent_text_support.py`

职责：

- 把工作流结果整理为最终对话输出
- 做面向用户的文案收口

### 6.5 诊断

- `diagnostics.py`
- `diagnostics_support.py`

职责：

- 提供 Agent 调试入口
- 产出 `workflow_trace`
- 支持预览、受限执行和错误定位

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

职责：

- 管理 workspace 边界
- 阻止危险命令
- 为 Agent 或 run 提供受限本地工具

所有涉及本地文件和命令的高风险能力，应优先落在这里统一约束。

### 7.4 `messaging/`

当前文件：

- `message_sender.py`

职责：

- 统一包装并发送业务消息
- 避免各业务模块自己拼消息结构

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
