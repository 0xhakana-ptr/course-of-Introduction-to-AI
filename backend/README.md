# 后端快速开始

本项目推荐使用 `uv` 管理 Python、虚拟环境和后端依赖。

当前后端入口文件仍然是 `backend/app/main.py`，但它现在只负责创建 FastAPI app、注册 lifespan 和挂载路由。

**下面所有命令都默认在项目根目录执行**。

当前后端**推荐使用 `Python 3.11`**；`Python 3.12` 也可以。

暂时**不建议使用 `Python 3.14`** 作为这个项目的后端运行环境，因为当前 `LangGraph` 相关依赖链在更高版本 Python 下可能出现兼容性问题。

## 0. 当前状态速览

当前后端已经不是单一演示入口，而是具备以下主线能力：

- `chat` 链路：支持普通聊天、测试命令，并通过最小 LangGraph Agent Brain 统一 chat / coding intent
- `runs` 链路：支持创建、执行、自动修复、日志查询、尝试记录查询
- `messages` 链路：支持统一消息格式与增量轮询
- `llm` 链路：支持 OpenAI-compatible 主模型和 fallback 模型
- `agent_workflow` 链路：提供最小 LangGraph Agent Brain，用于组织 coding intent 和工具调用
- `safe tools`：对文件读写和命令执行做了 workspace 边界与危险命令拦截

当前服务结构已经整理为“接口层 + 动作层”：

- `backend/app/api/`
- `backend/app/services/chat_interface.py`
- `backend/app/services/chat_action/`
- `backend/app/services/run_interface.py`
- `backend/app/services/run_action/`
- `backend/app/agent_workflow/`

当前后端已具备自动化测试护栏，覆盖方向包括：

- `chat intent`
- `llm client`
- `logging config`
- `message queue`
- `run lifecycle`
- `safe_fs / safe_execute_command`

## 1. 安装 uv

uv 官方提供不同平台的安装方式，详情请参考 [uv 官方文档](https://astral.sh/uv/getting-started/installation)。

```bash
# Windows PowerShell 管理员权限：
# （推荐）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# 或：
winget install --id=astral-sh.uv -e

# Linux / macOS bash：
curl -Ls https://astral.sh/uv/install.sh | sh
```

安装完成后，建议先确认：

```bash
uv --version
```

若返回版本号，则说明安装成功。

## 2. 用 uv 安装 Python

可以通过以下命令查看 `uv` 支持安装的 Python 版本：

```bash
uv python list
```

如果你本机还没有合适的 Python，直接让 `uv` 安装即可。例如：

```bash
uv python install 3.11
```

如果你更想使用 `3.12`，也可以：

```bash
uv python install 3.12
```

如果你已经有可用的 `Python 3.11` 或 `3.12`，`uv` 也会自动复用它。

## 3. 创建虚拟环境

在项目根目录执行：

```bash
uv venv

# 可指定 Python 版本，例如：
uv venv --python 3.11

# 或:
uv venv --python 3.11 .venv
```

如果你想用 `3.12`，把上面的 `3.11` 改成 `3.12` 即可。

### 3.1 从当前环境切换到 Python 3.11

如果你当前项目的 `.venv` 是用 `Python 3.14` 或其他不推荐版本创建的，建议直接重建这个项目的虚拟环境。

如果你当前终端已经激活了 `.venv`，先关闭这个终端，重新开一个新的 PowerShell，再执行：

```powershell
uv python install 3.11
if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
uv venv --python 3.11 .venv
uv pip install -r backend/requirements.txt
```

如果你想改成 `Python 3.12`，把上面的 `3.11` 替换成 `3.12` 即可。

如果你只是想**先验证**后端在推荐版本下是否正常，而不立刻重建 `.venv`，可以先直接运行：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

## 4. 安装后端依赖

```bash
uv pip install -r backend/requirements.txt
```

说明：`uv` 会自动识别并使用项目根目录下的 `.venv`。

如果你准备接入真实大模型，建议顺手复制一份环境变量模板：

```bash
copy backend\.env.example backend\.env
```

然后按你的模型服务实际情况填写 `backend/.env`。

## 5. 启动后端

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

保持这个终端窗口不要关闭，后面的 Electron 前端会通过它访问后端接口。

## 6. 验证后端是否启动成功

启动后，如果终端里看到 `Uvicorn running on http://127.0.0.1:8000` 一类提示，说明服务已经起来了。

你还可以直接在浏览器里打开：

```text
http://127.0.0.1:8000/docs
```

如果能看到 FastAPI 的接口文档页面，就说明后端已经正常运行。

如果你想直接跑后端自动化测试，可以使用：

```bash
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

说明：当前项目推荐 Python 3.11。若本机 `.venv` 使用了 `Python 3.14` 或其他更高版本，优先用上面的命令临时指定 Python 3.11 验证后端；确认无误后，再按上面的步骤重建 `.venv`。

## 6.0 配置真实大模型

当前后端的 `/chat` 使用 OpenAI-compatible `/chat/completions` 接口格式。

你需要在 `backend/.env` 或系统环境变量中至少配置：

```text
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

常见示例：

```text
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

或：

```text
LLM_BASE_URL=https://your-provider.example.com/v1
LLM_MODEL=your-model-name
```

如果你使用 LongCat 的 OpenAI-compatible 入口，可以写成：

```text
LLM_BASE_URL=https://api.longcat.chat/openai/v1
LLM_MODEL=LongCat-Flash-Thinking-2601
```

如果你使用的是响应较慢的 thinking 类模型，更稳妥的做法通常不是一味把超时拉很大，而是：

1. 主模型保留 thinking 模型
2. 给主模型设置一个相对克制的超时时间
3. 再配置一个更快的备用 chat 模型

例如：

```text
LLM_TIMEOUT_SECONDS=20
LLM_FALLBACK_MODEL=LongCat-Flash-Chat
LLM_FALLBACK_TIMEOUT_SECONDS=30
```

如果你的备用模型和主模型使用同一个 provider、同一个 key，通常不需要重复设置：

```text
LLM_FALLBACK_BASE_URL=
LLM_FALLBACK_API_KEY=
```

此时后端会自动继承 `LLM_BASE_URL` 和 `LLM_API_KEY`。

补充可选项：

```text
LOG_LEVEL=INFO
LLM_TIMEOUT_SECONDS=30
LLM_SYSTEM_PROMPT=你是一个运行在 Live2D 桌宠中的 AI 伙伴。请优先使用自然、清楚、友好的中文回答。
RUN_REPAIR_MAX_ATTEMPTS=1
CONVERSATION_HISTORY_MAX_MESSAGES=20
CONVERSATION_CONTEXT_RECENT_MESSAGES=8
CONVERSATION_SUMMARY_MAX_CHARS=1200
CHAT_CONTEXT_MAX_CHARS=6000
```

如果没有配置这些变量，`/chat` 会自动回退为占位回复，不会直接崩溃。

聊天记忆相关配置：

- `CONVERSATION_HISTORY_MAX_MESSAGES`：每个会话最多保留多少条历史消息，默认 `20`
- `CONVERSATION_CONTEXT_RECENT_MESSAGES`：构建聊天上下文时，最近多少条消息保持原样，默认 `8`
- `CONVERSATION_SUMMARY_MAX_CHARS`：对更早历史做压缩摘要时，摘要文本最多保留多少字符，默认 `1200`
- `CHAT_CONTEXT_MAX_CHARS`：拼给 LLM 的上下文最大字符数，默认 `6000`
- `CONVERSATION_SESSION_TTL_SECONDS`：会话持久化文件的最长保留秒数，默认 `604800`（7 天）
- `CONVERSATION_MAX_PERSISTED_SESSIONS`：workspace 中最多保留多少个持久化会话文件，默认 `200`
- `CONVERSATION_CLEANUP_INTERVAL_SECONDS`：后端自动清理会话文件的最小间隔秒数，默认 `60`
- 会话历史会持久化到 `backend/workspace/conversations/`，服务重启后仍可继续读取同一个 `session_id` 的最近消息
- 当会话历史较长时，后端会自动把更早的消息压缩成一段确定性摘要，并优先保留最近若干条消息的原始内容，以减少上下文膨胀
- 长会话压缩后生成的摘要会写入会话 `metadata` 作为 summary cache；当 `CONVERSATION_CONTEXT_RECENT_MESSAGES`、`CONVERSATION_SUMMARY_MAX_CHARS` 等上下文策略配置未变化时，服务重启后会优先复用这份缓存，配置变化时则自动重建

安全提醒：

- 真实密钥只应放在 `backend/.env`
- `backend/.env.example` 只保留占位模板
- 项目已默认忽略 `backend/.env*`，但会保留 `backend/.env.example` 供提交

## 6.0.1 诊断 LLM 连接状态

当前后端提供了一个开发期排错接口：

```text
GET /llm/diagnostics
```

默认只检查本地配置是否被后端正确读取，不会主动请求上游模型服务。你可以这样调用：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/llm/diagnostics
```

返回里重点看这些字段：

- `configured`：后端是否认为 LLM 配置完整
- `api_key_present`：是否检测到 API Key
- `base_url`：当前读取到的基础地址
- `resolved_url`：后端真正会请求的 `/chat/completions` 地址
- `model`：当前模型名

如果你想进一步确认“后端是否真的能打通上游模型接口”，可以显式加上远程检查参数：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/llm/diagnostics?check_remote=true"
```

此时后端会向上游模型发送一次最小测试请求，并额外返回：

- `checked_remote`：是否真的执行了远程检查
- `request_ok`：远程检查是否成功
- `status_code`：上游接口返回状态码
- `response_preview`：成功时返回的响应摘要
- `error_message`：失败时的错误摘要

推荐排查顺序：

1. 先看 `configured` 是否为 `true`
2. 再看 `resolved_url` 是否符合你的 provider 规范
3. 最后用 `check_remote=true` 看真实连通结果

## 6.1 当前后端已提供的接口

当前后端除了 `/health` 和 `/chat` 之外，还提供了最小任务流接口：

- `GET /llm/diagnostics`：检查当前 LLM 配置和可选的远程连通性
- `GET /chat/sessions`：分页查看最近持久化的聊天会话元信息，适合后端调试或后续管理面板
- `GET /chat/sessions/{session_id}`：查看指定会话的后端记忆元信息，例如消息数量和是否触发上下文压缩
- 该接口当前还会返回 `has_summary_cache` 和 `context_strategy_version`，方便确认持久化摘要缓存是否已生成，以及当前会话使用的是哪一版上下文压缩策略
- `DELETE /chat/sessions/{session_id}`：清空指定聊天会话的后端记忆
- `POST /runs`：创建一个任务，并在后台执行 coding task
- `GET /runs/summary`：读取轻量的 run 摘要列表，适合前端列表页或轮询
- `GET /runs`：列出历史任务
- `GET /runs/{run_id}`：查询单个任务状态和结果
- `GET /runs/{run_id}/attempts`：读取该任务的结构化执行尝试列表
- `GET /runs/{run_id}/attempts/{attempt_number}`：读取某一次具体执行尝试的详情
- `GET /runs/{run_id}/attempts/{attempt_number}/script`：读取该次尝试生成的脚本内容
- `GET /runs/{run_id}/attempts/{attempt_number}/output`：按分页参数读取该次尝试的 `stdout` / `stderr` / `error`
- `GET /runs/{run_id}/logs`：读取该任务的日志
- `POST /runs/{run_id}/retry`：基于失败任务创建一个新的重试任务
- `POST /runs/{run_id}/rerun`：基于已完成或已失败任务创建一个新的重新运行任务
- `POST /runs/{run_id}/cancel`：取消一个排队中或执行中的任务

其中 `POST /runs` 的返回通常会先是 `queued`，随后你可以通过 `GET /runs/{run_id}` 轮询它是否变成 `running`、`done`、`failed` 或 `cancelled`。

`retry` 和 `rerun` 的区别是：

- `retry`：只允许对 `failed` 任务触发，语义上表示“沿着失败上下文再试一次”
- `rerun`：允许对 `done` 或 `failed` 任务触发，语义上表示“重新跑一遍同样输入”
- `cancel`：允许对 `queued` 或 `running` 任务触发；如果任务尚未开始，会直接标记为 `cancelled`，如果正在执行，会先把 `cancel_requested` 设为 `true`，然后尽快终止本地命令执行

当前后端会在 follow-up run 中保留：

- `source_run_id`
- `trigger_mode`，可能为 `create`、`retry`、`rerun`

如果你只需要展示任务列表，推荐优先使用：

```text
GET /runs/summary?offset=0&limit=20
```

这个接口只返回轻量摘要字段，例如：

- `run_id`
- `status`
- `summary`
- `prompt_preview`
- `output_preview`
- `attempt_count`
- `repair_count`
- `latest_attempt_summary`

当前保留原来的 `GET /runs`，是为了兼容现有联调流程；后续如果前端切换到摘要接口，列表轮询的压力会更小。

当前 `/chat` 已经支持轻量会话记忆：

- 请求体可以传 `session_id`
- 如果不传，后端会自动创建新会话
- 响应体会返回 `session_id`
- 后端会保存同一会话最近若干轮消息，并在下一轮聊天时自动拼入上下文
- 可以通过 `GET /chat/sessions/{session_id}` 查看当前会话的消息数量、最近保留数量、压缩摘要预览、是否已生成摘要缓存，以及当前上下文策略版本
- 如果需要清空记忆，可以调用 `DELETE /chat/sessions/{session_id}`

当前 `/chat` 的普通聊天和 coding intent 都已经接入最小 LangGraph Agent Brain：

- `LongCat` 等大模型仍然只是 LLM provider，负责生成和判断
- `LangGraph` 负责 `router -> chat_node -> roleplay_node` 和 `router -> coding_node -> run_tool_node -> roleplay_node` 的状态流转
- `run_tool_node` 会复用现有 `/runs` 能力创建任务
- `/chat` 响应体会在 coding intent 下返回 `run_id`
- 创建出的 run 会继续通过后台任务执行，状态仍然通过 `/runs` 和 `/messages` 查询
- 对于直接通过 `/chat` 返回的聊天正文，后端不会再额外向消息队列重复写入同一条 `agent:chat`，以避免聊天窗口重复显示

当前 `cancel` 已经接入真实执行控制，而不是“只改状态”的假取消。后端会为每个运行中的 run 跟踪活跃进程和取消请求：

- 如果任务还在 `queued`，调用 `cancel` 会直接结束该任务
- 如果任务已经 `running`，调用 `cancel` 会先登记取消请求，再终止当前本地 Python 子进程
- 任务最终会落为 `cancelled`
- 对已经 `done`、`failed` 或 `cancelled` 的任务再次调用 `cancel`，会返回 `409`

如果你已经配置了真实大模型，`/runs` 会优先尝试让模型生成 Python 脚本；如果没有配置，或模型返回内容无法解析为可执行 Python 代码，则会自动回退到本地 demo 模板。

如果脚本首次执行失败，后端会在已配置 LLM 的前提下自动把原始脚本、执行命令、`stdout`、`stderr` 和错误信息发给模型进行修复，并按 `RUN_REPAIR_MAX_ATTEMPTS` 的设置继续重试。当前默认值是 `1`，也就是“失败后自动修一次”。

后端每次启动时，还会自动扫描历史 `runs/` 目录。如果发现有遗留的 `queued` 或 `running` 任务，说明这些任务大概率在上一次服务退出或重启时被中断了，后端会在启动阶段将它们统一标记为 `failed`，并写入日志与错误说明，避免它们长期卡在假运行中状态。

你也可以通过 `GET /health` 返回中的 `startup_recovery` 字段，查看本次启动时扫描了多少历史任务、实际恢复了多少条中断任务。

`GET /runs/{run_id}` 的返回里现在还会包含这些字段，便于你在后端调试阶段观察任务行为：

- `source_run_id`：如果该任务由 `retry` 或 `rerun` 产生，这里会记录原始任务 ID
- `trigger_mode`：当前任务来源，可能为 `create`、`retry`、`rerun`
- `cancel_requested`：是否已经收到取消请求；对于运行中的取消，这个字段会先变成 `true`，随后任务状态再落为 `cancelled`
- `attempt_count`：总执行次数
- `repair_attempted`：是否触发过自动修复
- `repair_count`：自动修复次数
- `attempts`：结构化的执行尝试列表，适合直接给前端轮询使用

`attempts` 中的每一项会记录一次独立执行尝试，当前包含这些核心字段：

- `attempt_number`：第几次执行
- `generator`：本次脚本来源，例如 `template`、`llm`、`llm_repair`
- `repair_round`：第几轮自动修复后产生的脚本，初次执行为 `0`
- `status`：本次尝试的状态，可能为 `running`、`done`、`failed`、`cancelled`
- `summary`：面向展示层的简短中文摘要，前端可以直接显示
- `source_file_name`：生成阶段原始脚本名
- `attempt_file_name`：真正落盘并执行的文件名
- `script_rel_path`：工作区内相对路径
- `command`、`cwd`：执行命令和工作目录
- `returncode`：执行返回码
- `stdout`、`stderr`、`error`：默认只返回预览文本，用于避免大输出撑爆普通轮询接口
- `stdout_length`、`stderr_length`、`error_length`：原始完整文本长度
- `stdout_truncated`、`stderr_truncated`、`error_truncated`：是否发生了裁剪
- `script_available`：该次尝试对应的脚本文件是否可读取
- `started_at`、`finished_at`、`duration_ms`：本次尝试的时间信息

如果你需要读取完整输出，不建议直接依赖 `attempts` 里的预览字段，而应该调用专门的分页接口：

```text
GET /runs/{run_id}/attempts/{attempt_number}/output?stream=stdout&offset=0&limit=4000
```

参数说明：

- `stream`：只能是 `stdout`、`stderr`、`error`
- `offset`：从第几个字符开始读取，默认 `0`
- `limit`：本次最多返回多少字符，默认 `4000`，最大 `20000`

如果你需要读取该次尝试真正生成并执行的 Python 脚本，可以调用：

```text
GET /runs/{run_id}/attempts/{attempt_number}/script
```

## 6.2 用 PowerShell 快速测试接口

先测试 LLM 配置是否被后端读到：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/llm/diagnostics
```

查看本次启动是否恢复过中断任务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

需要时再测试真实上游连通性：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/llm/diagnostics?check_remote=true"
```

发送一条聊天消息，并让后端自动创建会话：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"prompt":"你好","context":null,"session_id":null}'
```

发送一条 coding intent 消息，让后端通过 LangGraph 创建并执行 run：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"prompt":"write a calculator script","context":null,"session_id":null}'
```

返回体中的 `run_id` 就是后续查询 `/runs/{run_id}`、`/runs/{run_id}/attempts` 和 `/messages` 的任务 ID。

继续同一个会话时，把上一步返回的 `session_id` 填进去：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"prompt":"还记得我刚才说了什么吗？","context":null,"session_id":"<session_id>"}'
```

清空指定会话记忆：

```powershell
Invoke-RestMethod `
  -Method DELETE `
  -Uri http://127.0.0.1:8000/chat/sessions/<session_id>
```

查看指定会话的元信息：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/chat/sessions/<session_id>
```

分页查看最近会话列表：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/chat/sessions?offset=0&limit=20"
```

创建一个 run：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/runs `
  -ContentType "application/json" `
  -Body '{"prompt":"write a calculator script","context":null}'
```

列出所有 run：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/runs
```

读取轻量摘要列表：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/runs/summary?offset=0&limit=20"
```

查询单个 run，其中 `<run_id>` 是你要查询的 run 的 ID，可在 `http://127.0.0.1:8000/runs` 的响应中找到，下述同理：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/runs/<run_id>
```

查询一个 run 的所有 attempts：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/runs/<run_id>/attempts
```

查询单个 attempt：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/runs/<run_id>/attempts/1
```

读取该 attempt 生成的脚本：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/runs/<run_id>/attempts/1/script
```

按分页读取该 attempt 的 stdout：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/runs/<run_id>/attempts/1/output?stream=stdout&offset=0&limit=4000"
```

查看 run 日志：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/runs/<run_id>/logs
```

对失败任务创建 retry：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/runs/<run_id>/retry
```

对已完成或失败任务创建 rerun：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/runs/<run_id>/rerun
```

取消一个排队中或运行中的任务：

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri http://127.0.0.1:8000/runs/<run_id>/cancel
```

## 7. 让 Electron 连接后端

在项目根目录**另外打开一个新的终端窗口**，执行：

```bash
$env:AI_AGENT_ENDPOINT="http://127.0.0.1:8000/chat"
pnpm dev
```

如果你使用的是 `cmd.exe` 而不是 PowerShell，可以改成：

```bat
set AI_AGENT_ENDPOINT=http://127.0.0.1:8000/chat
pnpm dev
```

补充说明：

- 执行这一步之前，请先确保你已经在项目根目录完成过一次 `pnpm install`。
- 执行 `pnpm dev` 时，不要关闭前一个正在运行后端的终端窗口。
- 设置 `AI_AGENT_ENDPOINT` 后，Electron 主进程会自动从同一后端轮询 `GET /messages`，用于接收角色提示、表情、聊天、状态和错误消息。
- 如果消息接口地址不和 `/chat` 在同一个基地址下，可以额外设置 `AI_AGENT_MESSAGES_ENDPOINT`，例如：`http://127.0.0.1:8000/messages`。

## 可选：激活虚拟环境

如果你希望在当前终端会话中直接使用 `.venv` 里的 Python，也可以手动激活：

```bash
# Windows PowerShell
./.venv/Scripts/Activate.ps1

# Linux / macOS bash:
source .venv/bin/activate
```

对于 Windows，如果 Powershell 阻止脚本执行，可以先运行：

```bash
Set-ExecutionPolicy -Scope Process Bypass
./.venv/Scripts/Activate.ps1
```

## 说明

- 本项目推荐优先使用 `uv run` 和 `uv pip`，而不是直接使用 `pip` 或全局 `uvicorn`。
- 如果执行 `python` 时跳转到 Microsoft Store，也不必先纠结系统 `PATH`，可以直接用 `uv python install 3.11` 安装并管理 Python。对当前项目来说，优先推荐 `3.11`，其次是 `3.12`。
- 如果你只想确认当前最小后端是否可用，最直接的检查方式就是访问 `http://127.0.0.1:8000/docs`。
