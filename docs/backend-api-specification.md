# AI Agent Backend API Specification

本文档描述的是当前仓库中已经实现并验证过的后端接口与内部通信边界，基于 2026-05-06 当前代码状态整理。

## 1. 当前后端结构

后端主入口：

- `backend/app/main.py`

当前服务层已经整理为“接口层 + 动作层”结构：

- `backend/app/services/chat_interface.py`
- `backend/app/services/chat_action/`
- `backend/app/services/run_interface.py`
- `backend/app/services/run_action/`

相关基础模块：

- `backend/app/llm/client.py`
- `backend/app/message_queue.py`
- `backend/app/messaging/message_sender.py`
- `backend/app/storage/run_store.py`
- `backend/app/tools/safe_fs.py`
- `backend/app/tools/safe_execute_command.py`

## 2. 当前能力边界

### 2.1 聊天链路

`/chat` 当前支持三类意图：

- `chat`
- `coding`
- `unknown`

其中：

- `chat` 会调用 OpenAI-compatible LLM 接口。
- `coding` 会尝试桥接到 `agent_workflow`。
- `unknown` 会返回引导性回复。

说明：

- `coding` 分支当前仍属于实验性桥接能力，不等同于完整的多 Agent 协同系统。
- `agent_workflow` 通过 lazy import 暴露，缺少依赖时不会阻塞主服务启动。

### 2.2 任务执行链路

`/runs` 链路当前支持：

- 创建任务
- 后台执行
- 本地模板 fallback
- LLM 自动修复失败脚本
- 基于历史任务创建 `retry / rerun`
- 真实取消 `cancel`
- 查询尝试记录
- 查询脚本内容
- 分块读取 stdout / stderr / error
- 查询运行日志
- 启动恢复

### 2.3 消息队列链路

当前通过轮询接口提供消息：

- `GET /messages`
- `DELETE /messages`

消息队列特性：

- 自动生成 `_id`
- 自动生成 `_timestamp`
- 支持 `since_id` 增量拉取
- 线程安全
- 队列上限 `1000`

### 2.4 LLM 能力

当前 LLM 调用基于 OpenAI-compatible 接口实现，支持：

- 主 provider
- fallback provider
- 远程诊断
- 请求超时提示
- 不可重试 / 可重试错误区分

## 3. API 列表

### 3.1 `GET /health`

用途：

- 健康检查
- 返回启动恢复统计

返回示例：

```json
{
  "ok": true,
  "service": "backend",
  "version": "0.2.0",
  "startup_recovery": {
    "checked_at": "2026-05-06T08:00:00+00:00",
    "scanned_count": 0,
    "recovered_count": 0,
    "recovered_run_ids": []
  }
}
```

### 3.2 `GET /llm/diagnostics`

查询参数：

- `check_remote: bool = false`

用途：

- 检查本地 LLM 配置是否完整
- 可选远程探测主 / 备模型连通性

返回字段包括：

- `configured`
- `api_key_present`
- `base_url`
- `resolved_url`
- `model`
- `timeout_seconds`
- `fallback_configured`
- `fallback_model`
- `request_ok`
- `status_code`
- `response_preview`
- `error_message`
- `provider_used`
- `fallback_used`

### 3.3 `POST /chat`

请求体：

```json
{
  "prompt": "hello",
  "context": null
}
```

返回体：

```json
{
  "ok": true,
  "intent": "chat",
  "output": "response text",
  "error": null
}
```

补充说明：

- `/test ...` 命令也通过 `/chat` 入口处理。
- 测试命令会向消息队列写入消息，不依赖真实 LLM。

### 3.4 `POST /runs`

请求体：

```json
{
  "prompt": "build a calculator demo",
  "context": null
}
```

用途：

- 创建一个后台任务
- 立即返回 `RunResponse`
- 后续由后台任务执行 `execute_run`

### 3.5 `GET /runs`

用途：

- 返回完整任务列表

返回类型：

- `list[RunResponse]`

### 3.6 `GET /runs/summary`

查询参数：

- `offset`
- `limit`

用途：

- 返回轻量任务摘要

### 3.7 `GET /runs/{run_id}`

用途：

- 获取单个任务完整状态

### 3.8 `GET /runs/{run_id}/attempts`

用途：

- 获取该任务的尝试列表

### 3.9 `GET /runs/{run_id}/attempts/{attempt_number}`

用途：

- 获取单次尝试详情

### 3.10 `GET /runs/{run_id}/attempts/{attempt_number}/script`

用途：

- 获取某次尝试生成的脚本内容

### 3.11 `GET /runs/{run_id}/attempts/{attempt_number}/output`

查询参数：

- `stream`: `stdout | stderr | error`
- `offset`
- `limit`

用途：

- 分块读取单次尝试输出

### 3.12 `GET /runs/{run_id}/logs`

用途：

- 获取单个任务的完整文本日志

### 3.13 `GET /messages`

查询参数：

- `since_id` 可选

返回体：

```json
{
  "ok": true,
  "messages": [
    {
      "_id": "msg_168xxxx",
      "_timestamp": "2026-05-06T08:00:00Z",
      "_channel": "agent:chat",
      "type": "chat",
      "content": "hello"
    }
  ],
  "count": 1
}
```

### 3.14 `DELETE /messages`

用途：

- 清空消息队列

返回体：

```json
{
  "ok": true,
  "message": "消息队列已清空"
}
```

### 3.15 `POST /runs/{run_id}/retry`

用途：

- 基于一个 `failed` 任务创建新的 follow-up run

行为说明：

- 只有源任务状态为 `failed` 时允许调用
- 返回新的 `RunResponse`
- 新 run 会保留原始 `prompt / context`
- 新 run 会记录 `source_run_id`
- 新 run 会记录 `trigger_mode=retry`

### 3.16 `POST /runs/{run_id}/rerun`

用途：

- 基于一个已完成或失败的任务重新创建新的 follow-up run

行为说明：

- 允许源任务状态为 `done` 或 `failed`
- 返回新的 `RunResponse`
- 新 run 会保留原始 `prompt / context`
- 新 run 会记录 `source_run_id`
- 新 run 会记录 `trigger_mode=rerun`

### 3.17 `POST /runs/{run_id}/cancel`

用途：

- 取消一个 `queued` 或 `running` 的任务

行为说明：

- 如果源任务状态为 `queued`，会直接标记为 `cancelled`
- 如果源任务状态为 `running`，会先登记 `cancel_requested=true`
- 后端会尝试终止当前本地 Python 子进程，避免“状态取消但进程仍在跑”的假取消
- 任务最终状态会落为 `cancelled`
- 如果任务已经是 `done`、`failed` 或 `cancelled`，会返回 `409`

## 4. 当前消息格式

当前消息 envelope 对应 `MessageEnvelope`：

```json
{
  "_id": "msg_168xxxx",
  "_timestamp": "2026-05-06T08:00:00Z",
  "_channel": "agent:chat",
  "type": "chat",
  "timestamp": "2026-05-06T08:00:00Z",
  "node_name": "done",
  "metadata": {},
  "content": "text"
}
```

支持的 `type`：

- `quip`
- `expression`
- `chat`
- `error`
- `status`

当前前后端约定：

- `_channel` 用于区分展示通道
- `type` 用于区分消息语义
- `_id` 用于增量拉取

## 5. 当前运行结果模型

### 5.1 `RunResponse`

核心字段：

- `run_id`
- `status`
- `output`
- `source_run_id`
- `trigger_mode`
- `cancel_requested`
- `generator`
- `attempt_count`
- `repair_attempted`
- `repair_count`
- `command`
- `returncode`
- `stdout`
- `stderr`
- `log_path`
- `artifacts`
- `attempts`

### 5.2 `RunAttemptResponse`

核心字段：

- `attempt_number`
- `generator`
- `repair_round`
- `status`
- `summary`
- `script_rel_path`
- `command`
- `cwd`
- `returncode`
- `stdout`
- `stderr`
- `error`
- `stdout_length`
- `stderr_length`
- `error_length`
- `stdout_truncated`
- `stderr_truncated`
- `error_truncated`

## 6. 安全工具边界

`safe_fs.py` 与 `safe_execute_command.py` 是后端内部工具，不是对外 HTTP API，但它们决定了 `runs` 链路的安全边界。

### 6.1 `safe_fs.py`

提供：

- `resolve_workspace_path`
- `safe_write_file`
- `safe_read_file`
- `safe_list_files`

当前安全约束：

- 所有路径必须落在 `settings.workspace_dir` 内
- 路径逃逸会抛出 `PermissionError`

### 6.2 `safe_execute_command.py`

提供：

- `normalize_command`
- `is_blocked_command`
- `safe_execute_command`

当前安全约束：

- 明确拦截 shell 类可执行文件：
  - `cmd`
  - `powershell`
  - `pwsh`
  - `sh`
  - `bash`
- 明确拦截危险参数 token：
  - `rm`
  - `rmdir`
  - `del`
  - `format`
  - `shutdown`
  - `taskkill`
  - `remove-item`
  - `/c`
  - `-c`
  - `-command`
  - `--command`
- 命令超时时返回结构化错误结果，而不是直接让进程崩掉

## 7. 当前自动化测试覆盖

当前后端已覆盖以下方向：

- `chat intent`
- `llm client` 主备链路
- `logging config`
- `message queue`
- `run` 成功 / 失败 / 修复 / 启动恢复
- `run cancel`
- `text utils`
- `safe tools`

## 8. 当前已知定位

### 8.1 稳定主线

当前稳定主线是：

- `/health`
- `/llm/diagnostics`
- `/chat`
- `/runs`
- `/messages`

### 8.2 实验性部分

以下能力目前仍更适合视作实验性或桥接态：

- `coding` 分支里的 `agent_workflow`
- 完整多 Agent 协同编排

它们不会阻塞主服务启动，但也不应被文档表述为“已经完整稳定交付”。

### 8.3 当前 runs 执行控制说明

当前 `cancel` 已经作为正式 HTTP 接口接入，并具备真实执行控制：

- 执行中的 run 会登记到进程控制表
- `cancel` 会设置取消请求，并尝试终止对应的本地子进程
- 运行中的取消会先表现为 `cancel_requested=true`
- 最终任务状态会落为 `cancelled`

当前仍存在的边界是：

- 取消主要覆盖本地脚本执行阶段
- 如果任务正处于同步的 LLM 请求阶段，取消会在该阶段结束后尽快生效，而不是强制中断远程 HTTP 请求

## 9. 建议

后续如果继续扩展本文档，建议优先同步：

- `safe tools` 的更细测试结果
- `runs` 生命周期进一步扩展，例如更细粒度的 LLM 阶段取消
- `coding` 分支从实验性桥接转为稳定能力后的契约变化
