# 2026-05-11 Route Legacy Cleanup Assessment

## 1. 当前结论

旧 route graph 已具备移除条件，并已按 R6 执行清理。

当前 `/chat` 只保留 Agent Loop 主路径：

```text
/chat
-> agent_workflow/loop/agent_loop_graph.py
-> Action Registry
-> workspace / run / message / character service
```

不再保留：

```text
AGENT_RUNTIME_MODE
AGENT_RUNTIME_MODE=route
agent_workflow/graph/
/agent/diagnostics/legacy-route/*
legacy route-only tests
```

## 2. 已完成阶段

```text
R1 测试默认权交给 Loop
R2 非法 runtime 配置回退 Loop
R3 Loop Diagnostics 主路径
R4 旧 route 能力测试迁移（第一轮）
R5 /chat route fallback 收口
R6 删除旧 route graph
```

## 3. R6 清理范围

代码层：

- 删除旧 route graph 运行代码：`backend/app/agent_workflow/graph/`
- 删除旧 route helper facade：`backend/app/agent_workflow/agent_support.py`
- 删除旧 route 选择器：`backend/app/agent_workflow/state/routing.py`
- 删除配置入口：`AGENT_RUNTIME_MODE`
- `/chat` 入口固定进入 Agent Loop
- diagnostics 只保留 Agent Loop 诊断
- 删除 legacy route diagnostics API：`/agent/diagnostics/legacy-route/preview`
- 删除 legacy route diagnostics API：`/agent/diagnostics/legacy-route/run`

测试层：

- 删除 legacy route-only 测试文件：`backend/tests/test_agent_workflow.py`
- 删除 `AGENT_RUNTIME_MODE` 配置测试
- 删除 `/chat` 显式 route fallback 测试
- 删除 legacy route diagnostics 测试
- 保留 loop/action/workspace/run/diagnostics 主路径测试

文档层：

- README 不再说明 `AGENT_RUNTIME_MODE`
- `.env.example` 不再暴露 `AGENT_RUNTIME_MODE`
- API 文档不再记录 legacy route diagnostics URL
- 模块地图不再记录 `agent_workflow/graph/`

## 4. 保留项说明

`/chat` 响应仍保留 `runtime_mode=loop` 和 `route_scope=primary_loop`，用于前后端联调时确认当前运行路径。

`/agent/diagnostics/*` 仍保留 `selected_route=agent_loop`，用于兼容当前诊断响应结构；该字段现在只表示固定的 Agent Loop 诊断入口，不再表示旧 route graph。

后续如果要进一步精简 API，可以单独评估是否把 `selected_route` 改名为 `workflow_entry`，或直接从 diagnostics response 中删除。

## 5. 剩余工作

当前 R1-R6 已全部完成。

后续不再围绕旧 route fallback 展开，新的优化重点应转向：

- 强化 Agent Loop 多步循环能力
- 完善动作确认与风险控制
- 优化 workspace 文件写入、读取和桌面导出体验
- 减少 LLM token 消耗
- 做真实桌宠功能验收
