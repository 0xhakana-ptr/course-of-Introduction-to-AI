# Backend Test Layout

后端测试按被验证的边界分类。新增测试时优先放到对应子目录，根目录只保留全局 fixture。

```text
backend/tests/
  conftest.py
  acceptance/
  agent_workflow/
  api/
  core/
  llm/
  messaging/
  services/
  smoke/
  storage/
  tools/
```

分类规则：

- `acceptance/`：跨 `/chat`、`/messages`、Agent Loop 的端到端验收测试。
- `agent_workflow/`：LangGraph、Agent Loop、actions、diagnostics、summary、repair、workflow contracts。
- `api/`：FastAPI 路由、HTTP 错误结构、WebSocket、会话 API。
- `core/`：通用配置、日志、文本工具等基础 helper。
- `llm/`：LLM client、provider profile、fallback、URL 和 payload 构造。
- `messaging/`：消息队列、公共消息协议、message sender。
- `services/`：chat/run/character 业务入口和领域服务。
- `smoke/`：应用启动、核心接口挂载和低成本连通性检查。
- `storage/`：conversation/run 等持久化存储行为。
- `tools/`：safe fs、safe command、workspace tools。

常用命令：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

只跑某一类：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests/agent_workflow -q
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests/tools -q
```
