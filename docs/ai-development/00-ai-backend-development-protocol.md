# AI 辅助后端开发协议 / AI-Assisted Backend Development Protocol

## 0. 文档目的 / Purpose

本文档用于约束 AI 在本项目中进行后端开发时的工作方式。它不是一次性优化计划，而是长期执行协议。

核心流程：

```text
设计文档
-> 任务分解
-> 代码生成
-> 测试验证
-> 迭代优化
```

项目落地版：

```text
Read Design Docs
-> Check Architecture Direction
-> Decompose Task
-> Apply Risk Gate
-> Generate Code Incrementally
-> Run Verification
-> Self Review And Repair
-> Sync Documentation
-> Report Remaining Work
```

使用目标：

1. 减少用户反复手动确认低风险事项。
2. 防止 AI 偏离小组设计文档和 LangGraph Agent 方向。
3. 让每次开发都有明确任务边界、验收标准和剩余项计数。
4. 让 AI 可以按文档自我生成、自我纠错、自我完善。

## 1. 项目方向 / Project Direction

本项目不是普通聊天机器人，而是：

```text
AI 桌宠
+ Live2D/Electron/Vue 前端表现层
+ WebSocket/Bridge JSON 通信层
+ LangGraph 后端 Agent 工作流
+ 安全受控工具调用
+ 文件/代码/任务执行能力
+ 可观察状态反馈
```

后端方向必须符合：

1. LLM 只是“思考引擎”或“脑子”，不是完整 Agent 本体。
2. LangGraph/workflow 负责 Agent 的状态流转、工具调用和多步执行。
3. 桌宠前台角色和后台工程任务必须隔离，避免上下文腐化。
4. 工具执行必须受 workspace、安全确认和输出过滤约束。
5. 前端应接收结构化 Bridge JSON，而不是猜测后端文本含义。

禁止偏移方向：

1. 不要把项目退化成单轮 LLM 聊天壳。
2. 不要长期依赖零散关键词规则替代 workflow。
3. 不要让顶层 Turn Controller 继续膨胀成完整 coding/debug brain。
4. 不要把 raw error、完整 stdout/stderr、完整代码 diff 暴露给 roleplay/front-end。
5. 不要绕过 workspace 边界直接访问任意系统路径。

## 2. 必读设计文档 / Required Design References

每次开始重要后端开发前，AI 应优先参考：

```text
docs/design/main-guides/AI Agent 开发框架与蓝图 - Google Docs.md
docs/design/main-guides/AI Agent 架构优化V2 - Google Docs.md
docs/design/main-guides/AI桌宠全栈开发工作流程指南 - Google Docs.md
docs/backend/module-map.md
docs/backend/agent-acceptance.md
docs/backend/api-specification.md
```

当前阶段重要计划：

```text
docs/plans/2026-05/20260512-1.md
docs/plans/2026-05/20260512-2.md
```

读取方式：

1. 不需要每次全文重读所有文档。
2. 必须读取与当前任务相关的章节。
3. 如果任务涉及架构方向、LangGraph、工具调用、文件能力、前后端协议或安全确认，应重新核对主设计文档。

## 3. 后端架构约束 / Backend Architecture Contract

当前后端主路径：

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

职责边界：

```text
backend/app/api/
  HTTP/WebSocket 路由层，只做请求/响应适配。

backend/app/services/
  稳定业务入口，避免 API 直接深入内部实现。

backend/app/agent_workflow/
  Agent 图、状态、动作、诊断、子工作流。

backend/app/tools/
  安全受控工具，如 workspace 文件操作和命令执行。

backend/app/messaging/
  Bridge JSON、消息队列、前后端事件协议。

backend/app/llm/
  LLM 客户端、诊断、Provider URL 兼容。

backend/app/storage/
  会话、run、持久化数据。
```

关键约束：

1. `agent_workflow/loop/agent_loop_graph.py` 是顶层 Turn Controller，不是完整 coding/debug Agent brain。
2. PM/Coder/Executor/QA/Debugger 等工程流水线应下沉到 `agent_workflow/coding/` 或后续子图。
3. 文件任务如果继续复杂化，应新增 file workflow，而不是无限扩张 `workspace_tools.py` 的规则。
4. 前端可见事件必须通过 `messaging/` 和 Bridge JSON 结构化输出。
5. 高风险动作必须经过确认或明确安全策略。

## 4. AI 开发执行循环 / AI Development Loop

每次用户要求“按计划继续”“继续完善”“优化后端”时，AI 默认执行：

```text
1. Read
2. Plan
3. Implement
4. Verify
5. Review
6. Document
7. Report
```

### 4.1 Read

AI 应先读取：

1. 当前任务相关代码。
2. 当前计划文件或协议。
3. 相关测试。
4. 必要时读取主设计文档。

不得仅凭记忆修改复杂模块。

### 4.2 Plan

如果任务较小，可以内化计划并直接执行。

如果任务涉及架构、协议、安全、跨模块改动，应先形成明确任务分解：

```text
目标
影响范围
不做什么
任务列表
风险点
验收方式
```

### 4.3 Implement

代码生成原则：

1. 小步修改。
2. 每次只解决明确问题。
3. 尽量补测试或同步更新已有测试。
4. 不做无关重构。
5. 不改 `backend/.env`。
6. 不删除用户或组员可能依赖的行为，除非已有兼容层清理评估和用户确认。

### 4.4 Verify

根据影响范围运行测试。

后端默认：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

前端涉及 UI、类型、依赖或构建：

```powershell
pnpm build
```

消息协议相关：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests/messaging/test_message_protocol.py backend/tests/api/test_message_websocket.py -q
```

文件工具相关：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests/tools/test_workspace_tools.py backend/tests/acceptance/test_agent_loop_acceptance.py -q
```

### 4.5 Review

AI 必须自检：

1. 是否符合主设计文档方向。
2. 是否破坏 API/Bridge JSON 协议。
3. 是否引入上下文污染。
4. 是否暴露 raw error/stdout/stderr/full code。
5. 是否绕过 workspace 或安全边界。
6. 是否只是继续堆关键词，而不是修 workflow。
7. 是否缺少失败场景测试。
8. 是否需要更新 README、module map、acceptance guide 或 plan。

### 4.6 Document

以下情况必须更新文档：

1. 新增/移除模块。
2. 改变架构职责边界。
3. 改变前后端消息协议。
4. 新增重要工具能力。
5. 新增环境变量。
6. 完成计划中的阶段。

### 4.7 Report

最终回复必须包含：

1. 做了什么。
2. 验证结果。
3. 还有多少没弄。
4. 如果有风险或未验证项，明确说明。

## 5. 任务分解模板 / Task Decomposition Template

复杂任务必须使用以下模板写入计划或开发记录：

```markdown
# 标题 / English Title

## Goal

本次要解决的问题。

## Design References

本次遵守的设计文档。

## Scope

会改哪些模块。

## Non-goals

明确不做什么。

## Current Problems

当前问题和证据。

## Task Breakdown

P0: ...
P1: ...
P2: ...

## Risk Gate

哪些操作需要用户确认。

## Verification

需要跑哪些测试。

## Remaining Work

当前还剩 N 项。
```

## 6. 风险确认策略 / Risk And Confirmation Policy

AI 可以自动执行的低风险事项：

1. 补测试。
2. 修明显 bug。
3. 小范围重构。
4. 文档同步。
5. 补类型。
6. 补错误提示。
7. 补状态事件。
8. 补验收用例。

必须暂停并请求用户确认的高风险事项：

1. 删除大量代码。
2. 移除兼容层。
3. 改变公开 API 或 Bridge JSON 协议。
4. 改变存储格式。
5. 修改 `backend/.env`。
6. 引入大型依赖。
7. 改变整体架构方向。
8. 执行真实危险文件操作。
9. 绕过安全确认。
10. 可能影响组员接口规范的改动。

确认原则：

1. 如果只是实现既定计划中的低风险步骤，不需要反复询问用户。
2. 如果有多个合理方向且后果不同，必须说明选项并暂停。
3. 如果当前代码和设计文档冲突，必须优先指出冲突，再继续修正。

## 7. 自检纠错清单 / Self-Repair Checklist

每次测试失败后，AI 应按以下顺序处理：

```text
1. 读取失败信息
2. 判断失败类型
3. 定位最小影响范围
4. 小范围修复
5. 重跑相关测试
6. 必要时跑全量测试
7. 更新文档或剩余项
```

失败类型：

1. 语法/类型错误。
2. 测试断言错误。
3. 接口协议不一致。
4. 工作流状态错误。
5. 前端展示错误。
6. 安全边界问题。
7. 架构方向偏移。
8. 文档与实现不同步。

禁止行为：

1. 不得为了通过测试删除关键断言。
2. 不得隐藏错误。
3. 不得用更宽泛的规则掩盖 workflow 问题。
4. 不得把危险动作默认放行。

## 8. 当前后端优先级 / Backend Priority Roadmap

当前已完成：

1. Turn Controller 主路径。
2. coding subgraph 初步隔离。
3. workspace 文件工具基础能力。
4. Bridge JSON 状态事件。
5. 文件动作结构化前端展示。

后续优先级：

```text
P0: 建立文件 workflow 子图，替代继续堆 workspace parser 规则。
P1: 建立文件上下文记忆，如 last_created_file、last_read_file、last_search_results。
P2: 重做多行内容提取，支持 Markdown、代码块、LaTeX、JSON。
P3: 统一 content_type/render_mode 协议，稳定富文本渲染。
P4: 强化多步文件任务：write -> read -> run/test -> observe -> repair。
P5: 继续完善前端文件结果卡片、路径复制、搜索结果展开。
```

## 9. 富文本与文件任务原则 / Rich Text And File Task Rules

富文本问题分两类：

```text
富文本渲染器：展示 AI 输出中的 Markdown、代码块、LaTeX。
富文本编辑器：让用户输入复杂格式内容。
```

当前优先级：

```text
AI 输出稳定富文本渲染
-> 文件结果结构化展示
-> 用户输入富文本编辑器
```

后端应逐步输出明确协议字段：

```json
{
  "content_type": "markdown",
  "render_mode": "rich_text"
}
```

避免前端仅靠文本内容猜测是否需要富文本。

文件任务原则：

1. 简单文件动作可以走 workspace tools。
2. 复杂文件任务应进入 file workflow。
3. 多步文件任务必须有执行、观察、纠错、总结。
4. 文件内容提取必须支持代码块和多行文本。
5. 涉及删除、覆盖、桌面导出、命令执行必须有安全确认。

## 10. 使用方式 / How To Use

用户可以直接说：

```text
按 AI 后端开发协议继续
```

AI 应执行：

```text
读取相关文档
-> 拆任务
-> 判断风险
-> 实现低风险步骤
-> 测试验证
-> 自检修复
-> 更新文档
-> 报告剩余项
```

如果用户说：

```text
按计划进行，并告诉我还有多少没弄
```

AI 必须：

1. 找到当前最相关计划或协议。
2. 推进一个或多个低风险任务。
3. 更新 Remaining Work。
4. 明确回复剩余数量。

## 11. 当前协议状态 / Protocol Status

状态：

```text
active
```

首次建立日期：

```text
2026-05-12
```

后续如果项目架构发生变化，应先更新本文档，再继续进行大规模后端开发。
