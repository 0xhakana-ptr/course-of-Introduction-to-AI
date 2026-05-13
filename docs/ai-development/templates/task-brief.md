# Task Brief / 任务分解说明

## Goal / 目标

Describe the concrete problem this task solves.

## Design References / 设计依据

List the design docs, plans, or module docs that must constrain this task.

```text
docs/ai-development/00-ai-backend-development-protocol.md
docs/backend/module-map.md
docs/backend/agent-acceptance.md
```

## Scope / 范围

List files, modules, or behavior areas that may be changed.

## Non-goals / 不做什么

State what this task explicitly will not change.

## Current Problems / 当前问题

List observed problems, failing examples, test gaps, or user-facing symptoms.

## Task Breakdown / 任务拆分

P0:

P1:

P2:

P3:

## Risk Gate / 风险门

Does this task require user confirmation?

```text
yes/no:
reason:
```

Must ask for confirmation before:

```text
delete large code
remove compatibility layer
change public API
change Bridge JSON protocol
change storage format
edit backend/.env
add large dependency
change architecture direction
run dangerous file operation
change teammate-facing interface contract
```

## Implementation Plan / 实现步骤

1. Read relevant files.
2. Apply the smallest useful change.
3. Add or update tests.
4. Run focused verification.
5. Run broader verification if needed.
6. Update documentation.

## Verification / 验证方式

Backend:

```powershell
scripts/ai/verify-backend.ps1
```

Frontend:

```powershell
scripts/ai/verify-frontend.ps1
```

File workflow:

```powershell
scripts/ai/verify-file-workflow.ps1
```

## Self-check / 自检

Before final report, check:

1. Architecture direction is still aligned with main guide docs.
2. Turn Controller did not absorb subgraph responsibilities.
3. Workspace safety was not bypassed.
4. Bridge JSON/API compatibility was not broken.
5. Roleplay/frontend does not receive raw engineering artifacts.
6. Tests cover both success and failure paths.
7. Related docs and remaining work counts are updated.

## Remaining Work / 剩余项

Current remaining work count:

```text
N
```

Remaining items:

```text
1.
2.
3.
```
