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
