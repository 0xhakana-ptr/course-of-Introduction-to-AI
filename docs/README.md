# Docs Index / 文档索引

本文档用于说明 `docs/` 的组织方式。后续新增文档时，请优先按职责放入对应目录，避免重新把文件堆到 `docs/` 根目录。

## Directory Map / 目录结构

```text
docs/
  README.md
  ai-development/
  backend/
  design/
    main-guides/
  frontend/
  plans/
    2026-05/
```

## Stable Docs / 稳定文档

这些文档描述当前项目状态，应随代码同步维护：

- [Backend API Specification / 后端接口规范](./backend/api-specification.md)
- [Backend Module Map / 后端模块地图](./backend/module-map.md)
- [Backend Agent Acceptance Guide / 后端 Agent 验收手册](./backend/agent-acceptance.md)
- [Global Mouse Tracking / 全局鼠标追踪](./frontend/global-mouse-tracking.md)

## Design References / 设计依据

这些文档是小组方向和架构依据，后端 Agent 改动前应优先阅读：

- [AI Agent 开发框架与蓝图](./design/main-guides/AI%20Agent%20开发框架与蓝图%20-%20Google%20Docs.md)
- [AI Agent 架构优化 V2](./design/main-guides/AI%20Agent%20架构优化V2%20-%20Google%20Docs.md)
- [AI 桌宠全栈开发工作流程指南](./design/main-guides/AI桌宠全栈开发工作流程指南%20-%20Google%20Docs.md)

## AI Development Workflow / AI 开发流程

这些文档约束 AI 如何基于设计文档进行任务分解、代码生成、验证和迭代：

- [AI Backend Development Protocol](./ai-development/00-ai-backend-development-protocol.md)
- [Backend Development Workflow YAML](./ai-development/workflows/backend-development.yaml)
- [Backend Cleanup And Refactor Workflow YAML](./ai-development/workflows/backend-cleanup.yaml)
- [Task Brief Template](./ai-development/templates/task-brief.md)

## Plans / 计划归档

阶段性计划、历史执行记录和专项方案统一放在：

- [2026-05 Plans](./plans/README.md)

计划文件是过程资产，不一定代表当前代码最终状态。判断当前实现时，应优先看 `backend/` 下的稳定文档和当前代码。

## Placement Rules / 放置规则

新增文档按以下规则放置：

- 后端接口、模块、验收、运行说明：放入 `docs/backend/`。
- 前端交互、桌宠 UI、鼠标追踪、渲染说明：放入 `docs/frontend/`。
- 队长或小组设计依据：放入 `docs/design/main-guides/`。
- AI 自动开发协议、任务模板、workflow 配置：放入 `docs/ai-development/`。
- 阶段计划和历史方案：放入 `docs/plans/YYYY-MM/`。

不要在 `docs/` 根目录继续新增零散专题文档；根目录只保留总索引。
