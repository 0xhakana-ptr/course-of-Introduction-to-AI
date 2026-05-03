# 后端快速开始

本项目推荐使用 `uv` 管理 Python、虚拟环境和后端依赖。

当前最小后端入口文件是 `backend/app/main.py`。

**下面所有命令都默认在项目根目录执行**。

`Python 3.10+` 即可运行；为了后续继续扩展 Agent 相关能力，推荐优先使用 **Python 3.11**。

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

如果你已经有可用的 `Python 3.10+`，`uv` 也会自动复用它。

## 3. 创建虚拟环境

在项目根目录执行：

```bash
uv venv

# 可指定 Python 版本，例如：
uv venv --python 3.11

# 或:
uv venv --python 3.11 .venv
```

如果已经提前装好了其他的不低于 `3.10` 的版本也可使用。

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

补充可选项：

```text
LLM_TIMEOUT_SECONDS=30
LLM_SYSTEM_PROMPT=You are a helpful AI assistant for an educational desktop AI project.
RUN_REPAIR_MAX_ATTEMPTS=1
```

如果没有配置这些变量，`/chat` 会自动回退为占位回复，不会直接崩溃。

安全提醒：

- 真实密钥只应放在 `backend/.env`
- `backend/.env.example` 只保留占位模板
- 项目已默认忽略 `backend/.env*`，但会保留 `backend/.env.example` 供提交

## 6.1 当前后端已提供的接口

当前后端除了 `/health` 和 `/chat` 之外，还提供了最小任务流接口：

- `POST /runs`：创建一个任务，并在后台执行 coding task
- `GET /runs`：列出历史任务
- `GET /runs/{run_id}`：查询单个任务状态和结果
- `GET /runs/{run_id}/attempts`：读取该任务的结构化执行尝试列表
- `GET /runs/{run_id}/attempts/{attempt_number}`：读取某一次具体执行尝试的详情
- `GET /runs/{run_id}/attempts/{attempt_number}/script`：读取该次尝试生成的脚本内容
- `GET /runs/{run_id}/attempts/{attempt_number}/output`：按分页参数读取该次尝试的 `stdout` / `stderr` / `error`
- `GET /runs/{run_id}/logs`：读取该任务的日志

其中 `POST /runs` 的返回通常会先是 `queued`，随后你可以通过 `GET /runs/{run_id}` 轮询它是否变成 `done` 或 `failed`。

如果你已经配置了真实大模型，`/runs` 会优先尝试让模型生成 Python 脚本；如果没有配置，或模型返回内容无法解析为可执行 Python 代码，则会自动回退到本地 demo 模板。

如果脚本首次执行失败，后端会在已配置 LLM 的前提下自动把原始脚本、执行命令、`stdout`、`stderr` 和错误信息发给模型进行修复，并按 `RUN_REPAIR_MAX_ATTEMPTS` 的设置继续重试。当前默认值是 `1`，也就是“失败后自动修一次”。

`GET /runs/{run_id}` 的返回里现在还会包含这些字段，便于你在后端调试阶段观察任务行为：

- `attempt_count`：总执行次数
- `repair_attempted`：是否触发过自动修复
- `repair_count`：自动修复次数
- `attempts`：结构化的执行尝试列表，适合直接给前端轮询使用

`attempts` 中的每一项会记录一次独立执行尝试，当前包含这些核心字段：

- `attempt_number`：第几次执行
- `generator`：本次脚本来源，例如 `template`、`llm`、`llm_repair`
- `repair_round`：第几轮自动修复后产生的脚本，初次执行为 `0`
- `status`：本次尝试的状态，可能为 `running`、`done`、`failed`
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
- 如果执行 `python` 时跳转到 Microsoft Store，也不必先纠结系统 `PATH`，可以直接用 `uv python install 3.11` 安装并管理 Python。这里的 Python 版本只要不低于 `3.10` 即可。
- 如果你只想确认当前最小后端是否可用，最直接的检查方式就是访问 `http://127.0.0.1:8000/docs`。
