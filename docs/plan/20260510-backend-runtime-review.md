# 2026-05-10 后端整体复查与运行时完善计划

## 1. 背景

本计划用于记录 2026-05-10 对后端当前状态的整体复查结论，并把下一阶段需要处理的问题重新排优先级。

这次复查重点来自 3 个具体问题：

1. 当前后端哪些问题已经解决，哪些问题仍然存在，是否出现新问题。
2. 桌宠在收到“在桌面创建一个 txt 文件”这类请求后长时间没有明显动静的原因。
3. 队长提出的“LangGraph 不同节点开头发送 JSON，动作控制也在节点开头发送 JSON”是否已经落地。

本计划继续坚持项目主方向：

1. `LongCat` 或其他模型只作为 LLM provider，提供推理和生成能力。
2. `LangGraph` 是 Agent Brain，负责节点编排、状态流转和工具调用。
3. `tools/`、`run_interface`、`character_interface`、`message_queue` 是能力层和表现层。
4. 后端目标不是泛化成通用代码执行平台，而是支撑本地 Live2D AI 桌宠稳定对话、行动、反馈和安全执行。

## 2. 当前已经解决的问题

### 2.1 后端主流程仍然可用

当前后端测试通过：

```bash
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

结果：

```text
203 passed, 1 warning
```

这说明当前 `chat`、`runs`、`llm`、`message queue`、`safe_fs`、`workspace tools`、`agent workflow` 等主干模块没有明显断裂。

### 2.2 `agent_workflow` 结构清理基本完成

当前 `backend/app/agent_workflow/` 已经从根目录堆文件，整理成更清晰的子包结构：

1. `contracts/`
2. `diagnostics/`
3. `graph/`
4. `output/`
5. `repair/`
6. `state/`
7. `summary/`
8. `trace/`

旧的纯兼容层文件已经移除，当前扫描没有发现后端继续引用这些旧路径。

需要注意的是，这属于破坏性结构清理。后续组员拉取代码后，如果仍使用旧 import 路径，需要同步改到新的子包路径。

### 2.3 内部 workflow trace 已经具备诊断价值

当前 LangGraph 节点已经会通过 `workflow_trace` 记录内部运行状态。

这部分能力已经可以支持：

1. diagnostics 查询。
2. 节点路径排查。
3. `ui_status`、`event_type`、`event_source`、`event_stage` 追踪。
4. 失败节点定位。

但需要明确：这只是内部 trace，不等同于前端实时 JSON 事件。

### 2.4 Run 生命周期事件已经具备基础表现

当前 run 链路已经可以发送粗粒度角色事件：

1. `run.queued`
2. `run.started`
3. `run.repair_started`
4. `run.finished`
5. `run.failed`
6. `run.cancelled`

这些事件可以支撑“任务开始、任务完成、任务失败”这类基础反馈。

## 3. 当前仍然存在的问题

### 3.1 LangGraph 节点入口 JSON 尚未真正落地

队长提出的目标是：

> 在 LangGraph 不同节点开头发一个 JSON，动作控制也可以直接在节点开头发 JSON。

当前后端还没有完成这件事。

现状是：

1. `graph/agent_graph.py` 中的节点函数只负责返回 state。
2. `builder_support.py` 会追加 `workflow_trace`，但这是内部诊断数据。
3. `message_sender` 可以发送 `quip`、`status`、`expression`、`motion`，但 LangGraph 节点入口没有统一调用它。
4. 当前生产链路主要只在 chat/run 粗粒度生命周期上发消息。
5. `event_types.py` 中还没有稳定的 `workflow.node_entered` 或类似事件类型。

因此当前前端能看到“任务已开始、任务已完成”，但不能稳定看到：

1. “开始理解请求。”
2. “开始查看工作区。”
3. “开始创建任务。”
4. “开始读取任务状态。”
5. “开始尝试修复。”

这会直接造成用户感觉“桌宠没反应”。

### 3.2 文件创建能力缺失

当前 workspace tools 只支持：

1. `build_workspace_overview`
2. `list_workspace_entries`
3. `read_workspace_text`
4. `run_workspace_tests`

它们都是读、列目录、运行测试、概览工具，没有“创建文件”或“写文本文件”工具。

所以当用户说“帮我创建一个 txt 文件”时，后端没有一个明确、受控、可追踪的工具节点可以处理它。

### 3.3 桌面写文件不应默认放开

当前 `safe_fs` 明确限制路径必须在 `backend/workspace` 内。

这个限制是正确的，因为桌面属于 workspace 外部路径。如果默认允许模型写桌面，会产生几个风险：

1. 模型可能误写用户真实桌面文件。
2. 文件覆盖、路径注入、异常字符文件名难以控制。
3. 执行结果难以通过 run artifact 统一追踪。
4. 用户很难知道模型到底写了什么、写到了哪里。

但是当前 run 链路通过 Python 脚本执行任务，而 `safe_execute_command` 主要限制命令本身和执行目录，并没有提供 OS 级沙箱。

这意味着：如果模型生成的 Python 脚本主动写桌面，当前后端缺少足够清晰的策略来保证“拒绝、允许、提示、追踪”这几件事。

这个问题不能用简单放开权限解决。

### 3.4 Coding 任务仍然过度依赖 Python codegen

当前“创建文件”这类任务会被识别为 coding intent，并进入创建 run、生成 Python 脚本、执行脚本的链路。

这对复杂代码任务是合理的，但对“创建一个 txt 文件”这类简单工具任务过重。

更合理的方向是：

1. 简单文件任务走 LangGraph tool node。
2. 复杂代码任务才走 run/codegen 链路。
3. 工具任务要有明确的输入、输出、安全边界和前端反馈。

### 3.5 用户可见反馈仍然偏工程化

当前后端在一些路径中仍然会输出：

1. `run_id`
2. `/runs/{run_id}`
3. `/snapshot`
4. `/attempts`
5. 原始报错或接口信息

这些对开发调试有价值，但对桌宠体验来说过于工程化。

后续应保留 diagnostics 能力，但用户主路径输出应更像桌宠在解释自己做了什么，而不是让用户自己读 API。

## 4. 关于“桌面创建 txt 文件没动静”的判断

这不是单点 bug，而是 3 个问题叠加：

1. 当前没有受控的写文件工具。
2. 桌面路径位于 workspace 外部，按安全策略不应直接写。
3. coding run 生成脚本和执行期间缺少节点级实时反馈，导致用户感知上像“卡住”。

因此该问题应拆成两步解决：

1. 先补“节点入口 JSON + quip/status”，让用户知道桌宠当前在做什么。
2. 再补“受控文件写入工具”，让简单文件创建任务不再依赖 Python codegen。

暂时不建议直接支持任意桌面写入。

## 5. 下一阶段落地计划

### P0：补 LangGraph 节点入口事件

目标：在每个关键节点开头发送前端可消费的 JSON。

建议新增事件类型：

1. `workflow.node_entered`

建议节点入口事件至少包含：

1. `type`
2. `event_type`
3. `event_source`
4. `event_stage`
5. `node_name`
6. `status`
7. `progress`
8. `content` 或 `quip`
9. `metadata`

建议先覆盖这些节点：

1. `router`
2. `chat_node`
3. `coding_node`
4. `workspace_tool_node`
5. `run_tool_node`
6. `run_snapshot_node`
7. `run_control_node`
8. `unknown_node`
9. `roleplay_node`

示例 quip：

1. `router`: “我先判断一下该怎么处理。”
2. `chat_node`: “我正在组织回复。”
3. `coding_node`: “我在分析这个任务。”
4. `workspace_tool_node`: “我先查看一下项目上下文。”
5. `run_tool_node`: “我准备创建并执行任务。”
6. `run_snapshot_node`: “我在读取任务状态。”
7. `run_control_node`: “我在处理任务控制请求。”
8. `roleplay_node`: “我整理一下结果再告诉你。”

实现位置建议：

1. 新增 `backend/app/agent_workflow/output/node_events.py`。
2. 在其中定义节点事件配置和 `emit_workflow_node_entered()`。
3. 在 `graph/agent_graph.py` 的各节点函数入口调用。
4. 通过 `message_sender.send_quip()` 和 `message_sender.send_status()` 输出 JSON。
5. 使用 `emit_chat_message` 或新增 `emit_node_events` 控制是否在 diagnostics 中静默。

### P1：补受控 workspace 写文件工具

目标：让“创建 txt 文件”这类简单任务走工具节点，而不是默认走 Python codegen。

建议新增 workspace tool：

1. `write_workspace_text`

能力范围：

1. 只能写 `backend/workspace` 内路径。
2. 默认不覆盖已有文件。
3. 文件名需要清洗。
4. 内容需要限制长度。
5. 返回写入路径、是否覆盖、字符数和摘要。

暂时不支持直接写桌面。

如果用户要求写桌面，应返回明确提示：

```text
我不能直接写桌面路径。可以先把文件创建到项目 workspace 中，再由你确认是否导出。
```

### P2：区分简单工具任务和复杂代码任务

目标：减少不必要的 LLM codegen 和 Python 脚本执行。

建议新增轻量任务识别：

1. 创建文本文件。
2. 读取文件。
3. 列目录。
4. 查看 run 状态。
5. 运行测试。

这些任务应优先走工具节点。

只有当任务需要生成或修改代码、运行脚本、自动修复时，才进入 `/runs` codegen 链路。

### P3：为桌面导出设计显式权限模型

目标：如果后续确实要支持“写到桌面”，必须通过显式工具而不是模型自由写脚本。

建议后置新增：

1. `DESKTOP_EXPORT_ENABLED=false`
2. `DESKTOP_EXPORT_DIR`
3. 文件名清洗。
4. 覆盖保护。
5. 导出日志。
6. 用户确认或前端确认。

默认策略仍应是不允许直接写桌面。

### P4：优化用户可见输出

目标：减少工程化口径，让桌宠更自然地解释执行过程。

调整方向：

1. 主聊天结果中少暴露 API URL。
2. 保留 `run_id`，但用自然语言解释它是什么。
3. 详细日志放 diagnostics 或 run detail，不默认推给用户。
4. 失败时输出“发生了什么 + 下一步建议”，而不是直接倾倒原始错误。

## 6. 验收标准

### 6.1 节点事件验收

1. 发送普通聊天时，前端能收到 `router -> chat_node -> roleplay_node` 的节点入口消息。
2. 发送 coding 任务时，前端能收到 `router -> coding_node -> workspace_tool_node -> run_tool_node` 的节点入口消息。
3. 每个节点入口消息都是结构化 JSON。
4. 每个节点入口消息可以驱动至少一种桌宠表现：quip、status、expression 或 motion。

### 6.2 文件工具验收

1. 请求“创建一个 txt 文件”时，不应长时间无反馈。
2. 如果目标是 workspace，后端能安全创建文件。
3. 如果目标是桌面，后端应明确拒绝或提示需要导出权限。
4. 创建结果应能被 run/tool trace 追踪。

### 6.3 安全验收

1. `safe_fs` 仍然默认限制 workspace。
2. 不允许模型通过普通工具直接写任意系统路径。
3. 如果后续做桌面导出，必须显式开启，不应默认开启。
4. 自动化测试需要覆盖 workspace 写文件、拒绝越界路径、节点入口事件。

## 7. 当前优先级结论

当前最优先处理的不是继续拆 support 文件，也不是继续堆 diagnostics 字段，而是补齐运行中的前端表现层。

推荐顺序：

1. P0：LangGraph 节点入口 JSON。
2. P1：受控 workspace 写文件工具。
3. P2：简单工具任务和复杂代码任务分流。
4. P3：桌面导出权限模型。
5. P4：用户可见输出优化。

这样可以直接解决“桌宠没动静”的体验问题，也能让后端更贴合“LangGraph 是 Agent，LLM 只是脑子”的项目方向。
