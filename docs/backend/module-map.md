# 后端目录与模块地图

本文档只解释“代码应该去哪里找、以后应该往哪里放”，不重复接口字段细节。接口契约请看 [`docs/backend/api-specification.md`](./api-specification.md)。

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
  dev/
  tests/
  workspace/
  .env.example
  requirements.txt
  README.md
```

说明：

- `backend/app/`：后端源码主目录
- `backend/dev/`：开发期手动调试脚本，不属于正式后端入口
- `backend/tests/`：后端自动化测试
- `backend/workspace/`：运行时文件，当前主要包含 `runs/` 与 `conversations/`
- `backend/.env.example`：环境变量模板
- `backend/requirements.txt`：Python 依赖

非源码与生成物：

- `backend/workspace/` 是运行时数据目录，不应放源码、测试或文档。
- `backend/**/__pycache__/`、`backend/**/*.pyc`、`backend/.pytest_cache/` 是本地生成缓存，不应提交，也不应被模块地图当作代码结构。
- `backend/.env` 是本地密钥与模型配置文件，不应在整理目录或重构时修改。

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

P4 评估结论：

- 当前暂不拆分 `schemas.py`。
- 该文件是 API 契约聚合入口，被 `api/`、`services/`、`messaging/`、`tools/` 和测试共同导入。
- 现阶段强行拆分会带来大量 re-export 和导入路径迁移，收益低于接口 churn 风险。
- 后续如果模型继续增长，可以按 `chat / run / messaging / diagnostics / workspace` 做内部文件拆分，但必须保留 `backend.app.schemas` 作为稳定 re-export 入口。

### 3.3 `message_queue.py`

用途：

- 保存后端统一消息队列
- 支持轮询增量拉取
- 支持 WebSocket 推送的基础消息源

### 3.4 稳定入口与内部实现

后端新增代码时，先判断自己是在改“入口契约”还是“内部实现”：

稳定入口：

- `backend.app.main:app`：后端应用启动入口。
- `api/*_routes.py`：HTTP / WebSocket 接口入口。
- `services/*_interface.py`：业务层给 API 调用的稳定门面。
- `agent_workflow/loop/__init__.py` 与 `loop/agent_loop_graph.py`：当前 `/chat` Agent Loop 主入口。
- `tools/workspace_tools.py`：当前 workspace 工具对外 facade，后续拆分也应保持 public 函数稳定。
- `llm/client.py`：模型调用统一入口。
- `messaging/message_sender.py` 与 `messaging/runtime_events.py`：前端消息与 Bridge JSON 统一出口。
- `storage/*_store.py`：持久化读写入口。

内部实现：

- `services/*_action/`：对应业务门面的内部动作拆分。
- `agent_workflow/actions/`、`coding/`、`file/`、`repair/`、`summary/`、`diagnostics/`、`state/`、`runtime/`、`trace/`：Agent 子流程、状态、事件和诊断实现细节。
- `api/route_support.py`、`api/query_params.py`、`api/run_dependencies.py`：路由层 helper。
- `core/*`：配置、日志、文本等通用 helper。

整理规则：

- 能在内部实现中完成的改动，不要扩大到稳定入口。
- 拆分大文件时优先保留原入口作为 facade，再把 helper 下沉到子模块。
- 只有接口契约、Bridge JSON、存储格式或团队导入路径确实需要变化时，才修改稳定入口。

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

### 6.1 顶层 Turn Controller 与动作层

```text
agent_workflow/
  coding/
    coding_graph.py
    planner.py
    result.py
    state.py
    worker_payloads.py
  loop/
    action_plan.py
    agent_loop_graph.py
    file_followups.py
    planning.py
  file/
    file_graph.py
    context.py
    result.py
    state.py
  actions/
    core.py
    models.py
    registry.py
    run.py
    workspace.py
  runtime/
    graph_nodes.py
```

职责：

- `coding/`：coding/debug 内部循环的子图包；当前已接入 `/chat` 主线中的简单 workspace action 与 `run.create`
- `coding/coding_graph.py`：定义 `coding_start_node -> pm_node -> coder_node -> executor_node -> qa_node -> debugger_node -> coding_finish_node / coding_failure_node`；A4 阶段已接入简单 `workspace.write/read/list`，A5 阶段已接入 `run.create`，A6 阶段已加入失败摘要过滤，A7 阶段已加入受限局部修复，A9 阶段已允许 `coder_node` 在规则计划不足时调用受控 LLM planner
- `coding/planner.py`：把 LLM 输出解析为严格 `CodingTaskPlan`，只允许 `workspace.write/read/list` 与 `run.create`，并拒绝 shell/command/env/token/raw log 等本地执行或敏感字段
- `coding/result.py`：定义 `CodingWorkflowResult`，收口 coding 子图输出，避免 raw error/stdout/stderr 进入结果 payload
- `coding/artifacts.py`：保存 coding 子图内部 raw error artifact，并只向 active state 暴露 artifact ref
- `coding/state.py`：定义 LangGraph 运行用的 `CodingGraphState`
- `coding/worker_payloads.py`：定义 PM/Coder/Executor/QA/Debugger 的局部 worker payload，只把允许字段送入节点；同时提供 `to_send()` 适配 LangGraph `Send`，但当前线性子图不强依赖 Send API
- `loop/agent_loop_graph.py`：当前默认 `/chat` 主路径，文件名暂不改动，但架构定位是顶层 Turn Controller；它负责接收一轮用户输入、选择 action 或内部 workflow、发出过程事件，并保证最终进入 `workflow.completed` 或 `workflow.failed`
- `loop/action_plan.py`：定义顶层 loop 的 action plan 数据结构与计划归一化 helper，避免把计划字段散落在 Turn Controller 中
- `loop/file_followups.py`：收口“写完再读”“刚才那个文件”“搜索第一个结果后继续复制/删除/读取”等文件后续动作逻辑
- `loop/planning.py`：收口风险确认、覆盖确认、可恢复失败判断和 ActionPlan 构造 helper
- `file/`：文件任务子工作流与文件上下文逻辑；`file_graph.py` 包装受控 workspace file actions，`context.py` 负责最近文件状态、搜索结果指代和“刚才那个文件”等路径引用解析
- `actions/`：Action Registry、Action 模型与 run/workspace 等可执行动作
- `runtime/graph_nodes.py`：LangGraph 节点注册和异常保护 helper

边界约束：

- 新 Agent 能力优先接入 `loop/` 与 `actions/`
- 旧 route graph 已移除，不再维护 `AGENT_RUNTIME_MODE=route` fallback
- 节点事件和节点 metadata 只维护当前 Agent Loop 节点，不再保留旧 route graph 的 `router/chat_node/coding_node`
- 需要新增工具时，优先注册 action，而不是新增固定路由分支
- 顶层 Turn Controller 不应继续堆叠 PM、Coder、QA、Debugger 的内部逻辑；这些 coding/debug 能力应进入后续 `agent_workflow/coding/` 子图
- 顶层 Turn Controller 可以调度简单文件 action，并在 observe 阶段维护文件上下文；复杂文件任务应继续下沉到 `agent_workflow/file/` 或 `loop/file_followups.py`，不要把文件大脑继续堆进 `loop/agent_loop_graph.py`
- 节点、动作和终态事件仍统一由 `agent_workflow/output/` 负责，不在 `loop/` 下重复新增事件层
- Roleplay / 前端状态只能接收简短状态、quip、确认请求和终态信息，不应接触 raw error、完整 stdout/stderr 或长代码上下文
- `coding/` 子图在 A5 阶段接管简单 `workspace.write/read/list` 与 `run.create`；`workspace.test`、桌面导出、`run.inspect/retry/rerun/cancel` 仍留在顶层 action 路径或后续阶段处理
- `coder_node` 当前优先使用规则把 PM 任务转成受控 executor action；规则计划不足且 LLM 已配置时，可调用 `coding/planner.py` 生成 `CodingTaskPlan`，但 planner 只产出计划，不直接执行工具
- `qa_node` 只处理失败路径：读取 raw error artifact，输出短 `error_summary`，并清理 active state 中的 `raw_error_ref`
- `debugger_node` 只读取 `current_task`、`error_summary`、`coder_plan` 和受控 action 输入；当前只支持明确允许的缺失路径探测修复，并受 `max_debug_steps` 限制
- PM/Coder/Executor/QA/Debugger 节点都应通过 `coding/worker_payloads.py` 构造局部输入，不应直接读取完整全局 state。
- LangGraph `Send` 当前作为适配能力保留；只有在后续需要并行 worker/map-reduce 或明确 reducer 策略时，才把现有线性边改为实际 Send 调度。

### 6.2 共享契约与节点映射

```text
agent_workflow/
  contracts/
    workflow_nodes.py
    workflow_results.py
    node_mappings.py
```

职责：

- `contracts/workflow_nodes.py`：保存当前 Agent Loop 节点元信息、run/summary/repair 终态节点常量和终态节点映射
- `contracts/workflow_results.py`：保存 Agent / Summary / Repair workflow 的结构化结果模型与 graph invoke 收口 helper
- `contracts/node_mappings.py`：保存节点到 quip / expression 的映射和是否发送 chat message 的规则

### 6.3 状态与基础常量

```text
agent_workflow/
  state/
    constants.py
    display_state.py
    engineering_state.py
    run_state.py
    run_support.py
    runtime_state.py
    state_support.py
```

职责：

- `state/constants.py`：保存 Agent workflow 内部 action/status 常量
- `state/display_state.py`：定义 `FrontendState`，只保存前端/Roleplay 可见状态，并提供 raw error、stdout/stderr、长代码等脏上下文过滤规则
- `state/engineering_state.py`：定义 `EngineeringState`，保存 coding/debug 所需任务、目标文件、artifact refs、`raw_error_ref` 和 `error_summary`
- `state/run_state.py`：封装 run 相关状态字段快照与更新
- `state/run_support.py`：封装 run_id 解析、snapshot 读取和 run control 调度
- `state/runtime_state.py`：定义 `TurnState`、`RuntimeState`、`ToolState`、`ConversationState` 和 `CodingWorkflowState`，用于后续 coding 子图的分区状态边界
- `state/state_support.py`：封装 Agent state merge、trace 追加、初始 state 和 graph invoke

边界约束：

- `FrontendState` 不允许包含 `raw_error`、`raw_error_ref`、完整 `stdout/stderr`、完整 `workflow_trace`、长代码或工具内部 stack trace
- `EngineeringState` 只保存 `raw_error_ref`，不保存 raw error 正文；QA 节点后应转为 `error_summary` 并清理 raw error 引用
- `CodingWorkflowState` 是后续 `agent_workflow/coding/` 子图的状态契约，不应被顶层 Turn Controller 扩成万能全局状态

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
    action_events.py
    completion_events.py
    node_events.py
    roleplay.py
    text.py
```

职责：

- `output/node_events.py`：节点入口 `workflow.node_entered` 事件，负责 quip、status、节点进度和节点元信息
- `output/action_events.py`：动作开始、完成、失败事件，负责 `workflow.action_started / completed / failed`
- `output/completion_events.py`：Agent Loop 终态事件，负责 `workflow.completed / workflow.failed`
- `output/roleplay.py`：把工作流结果发送为用户可见聊天消息
- `output/text.py`：收口 run 创建、查询、控制、未知意图等用户可见文案

边界约束：

- 前端 loading 解除应依赖 `workflow.completed / workflow.failed`，不要依赖单个 action 事件
- 新增节点级可见反馈，优先改 `output/node_events.py`
- 新增动作级可见反馈，优先改 `output/action_events.py`

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
- `file_context_store.py`
- `run_store.py`

职责：

- 会话持久化
- 按 `session_id` 保存最近文件上下文，用于解析“刚才创建的文件”“刚才搜索到的文件”等指代
- run 记录持久化
- 供 `services/` 查询与更新

`conversation_store.py` 当前边界：

- 负责会话 ID 创建、消息追加、会话列表、上下文构建、摘要缓存、元数据兼容和磁盘持久化。
- 当前被 `main.py`、`api/chat_routes.py`、`services/chat_interface.py` 和会话相关测试直接使用。
- 由于它同时涉及内存状态、JSON 持久化格式、TTL 清理和长历史摘要，现阶段不在 cleanup 流程里拆分。

后续如需专门做 storage refactor，建议保持 `conversation_store.py` 作为 facade，并把内部能力拆到：

- `storage/conversation/types.py`：常量、类型别名和 payload 结构说明。
- `storage/conversation/context.py`：上下文拼接、截断和摘要缓存 helper。
- `storage/conversation/persistence.py`：路径解析、JSON 读写、TTL 与最大会话数清理。
- 持久化 JSON 形状必须保持兼容：`session_id`、`messages`、`updated_at`、`metadata`。

### 7.3 `tools/`

当前文件：

- `safe_fs.py`
- `safe_execute_command.py`
- `workspace_tools.py`
- `workspace_tool_models.py`
- `workspace/`
  - `constants.py`
  - `utils.py`
  - `file_ops.py`
  - `formatters.py`

职责：

- 管理 workspace / 真实项目访问边界
- 阻止危险命令
- 为 Agent 或 run 提供受限本地工具
- 解析受控文件任务，包括 read/write/list/move/copy/delete/search/test 和多行内容写入

所有涉及本地文件和命令的高风险能力，应优先落在这里统一约束。

真实项目访问边界：

- 默认只使用 `backend/workspace/`，不会访问用户真实项目。
- `PROJECT_ROOT` 配置后，`safe_fs.py` 会把文件工具根目录切到该真实项目目录。
- `PROJECT_WRITE_ENABLED=false` 时真实项目为只读；写入必须显式设置 `PROJECT_WRITE_ENABLED=true`。
- `.git`、`.env*`、`node_modules`、`__pycache__`、`.venv`、`dist`、`build` 等路径由 `safe_fs.py` 统一拒绝。
- 新增文件工具或 Agent 文件动作时，必须继续走 `resolve_workspace_path()`、`safe_read_file()`、`safe_write_file()` 等安全入口，不要直接使用 `Path(...).read_text()` 或 `write_text()` 访问用户项目。

文件写入约束：

- 多行 Markdown、LaTeX block 和 fenced code block 的内容提取在 `workspace_tools.py` 中统一处理。
- “然后读出来确认”等后续动作不应写入文件正文。
- `.py/.js/.cpp/.sh/.json/.yaml` 等代码文件如果只收到一个最外层 fenced code block，应剥离外层围栏后写入代码正文。

当前拆分边界：

- `workspace_tools.py`：对外 facade，保留 public 函数、工具规划、registry 和执行结果收口。
- `workspace/constants.py`：工具名、默认限制、关键词集合、输出类型常量。
- `workspace/utils.py`：路径、文本、布尔值和长度限制的通用归一化 helper。
- `workspace/file_ops.py`：workspace list/read/write/move/copy/delete/search/test 与桌面导出执行逻辑。
- `workspace/formatters.py`：工具上下文摘要、用户可见文本和文件操作摘要格式化。
- `safe_fs.py`：仍是 workspace 边界与路径安全的唯一基础层，不额外包一层假 safety 模块。
- `workspace_tool_models.py`：仍是 workspace tool 的 Pydantic 模型定义处。

### 7.4 `messaging/`

当前文件：

- `message_sender.py`
- `event_types.py`
- `runtime_events.py`

职责：

- 统一包装并发送业务消息
- 避免各业务模块自己拼消息结构
- 维护 runtime event 的稳定枚举和字段构造规则
- 为 `/messages` 和 `/messages/ws` 统一补齐 Bridge JSON 字段：
  `bridge_event_type`、`bridge_event_version`、`bridge_payload`
- 为 assistant 文本消息显式标记 `content_type` 与 `render_mode`，前端根据协议渲染 Markdown、代码块和 LaTeX

当前 Bridge 事件类型：

- `Status_Update`：状态、节点进入、动作开始/完成/失败、终态事件
- `Roleplay_Dialogue`：chat、quip、expression、motion 等前台表现事件
- `Auth_Request`：`ask_user_confirmation` 等需要用户确认的授权事件

约束：

- 新增前端可见消息必须经过 `runtime_events.normalize_frontend_message_payload(...)`。
- 不要在 `bridge_payload` 中放 raw error、stdout/stderr、完整代码、token 或密钥。
- 不要让前端靠消息来源猜测富文本；assistant 回复默认走 `content_type=markdown`、`render_mode=rich_text`，状态消息仍保持轻量文本。
- 前端 loading 仍应以 `workflow.completed` / `workflow.failed` 判断整轮结束。

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
