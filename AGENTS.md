# Project Agent Instructions

This repository uses an AI-assisted development workflow. Before making backend or agent-related changes, read and follow:

```text
docs/ai-development/00-ai-backend-development-protocol.md
docs/backend/module-map.md
docs/backend/agent-acceptance.md
docs/backend/api-specification.md
docs/design/main-guides/
```

Core loop:

```text
Design Docs
-> Task Decomposition
-> Code Generation
-> Test Verification
-> Iterative Optimization
```

Project-specific loop:

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

Hard rules:

1. Do not edit `backend/.env`.
2. Do not bypass workspace path safety.
3. Do not expose raw `stdout`, `stderr`, raw errors, stack traces, full code, or long diffs to roleplay/frontend messages.
4. Do not grow `backend/app/agent_workflow/loop/agent_loop_graph.py` into a full coding/debugging brain. Keep it as the top-level Turn Controller.
5. Complex coding, debugging, file, and tool workflows should move into dedicated LangGraph subgraphs.
6. Prefer structured Bridge JSON over frontend text guessing.
7. Keep frontend roleplay state isolated from backend engineering state.
8. Add or update tests for behavior changes.
9. Update docs when architecture, protocol, modules, environment variables, or major workflow behavior changes.
10. Always report remaining work count when continuing a plan.

Risk gate:

Ask for user confirmation before:

1. Deleting large amounts of code.
2. Removing compatibility layers.
3. Changing public API or Bridge JSON protocol.
4. Changing storage format.
5. Editing `.env` or secrets.
6. Adding large dependencies.
7. Changing the overall architecture direction.
8. Running dangerous file operations.
9. Making changes that may break teammate-facing interface contracts.

Default verification commands:

```powershell
scripts/ai/verify-backend.ps1
scripts/ai/verify-frontend.ps1
scripts/ai/verify-file-workflow.ps1
```

If scripts cannot be used, run the equivalent commands documented in `docs/ai-development/00-ai-backend-development-protocol.md`.
