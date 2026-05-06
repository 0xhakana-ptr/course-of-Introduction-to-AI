
## AI Agent 后端通信接口设计文档

### 1. 系统概述

本设计文档描述了 AI Agent 后端通信接口的完整架构，重点解决了前后端通信中的消息类型区分、数据格式统一和实时通信问题。

### 2. 核心设计原则

#### 2.1 消息类型分离
系统将消息分为两大类：
- **UI 装饰性消息**：`quip`、`expression`、`status` - 用于表示 Agent 状态变化
- **真实聊天消息**：`chat` - 用于 AI Agent 聊天窗口的对话内容

#### 2.2 LangGraph 节点与消息映射
- 每个 LangGraph 节点切换时自动发送对应的 `quip` 和 `expression`
- 只有在任务完成或需要长输出时才发送 `chat` 消息
- 确保聊天窗口不会收到过程性的装饰性消息

### 3. 架构组件

#### 3.1 消息队列系统
**文件**: `message_queue.py`

```python
class MessageQueue:
    - add_message(): 添加消息到队列
    - get_messages(): 获取消息（支持增量拉取）
    - clear(): 清空队列
```

**特性**:
- 自动生成消息 ID 和时间戳
- 支持增量拉取（since_id 参数）
- 队列大小限制（1000 条）
- 线程安全设计

#### 3.2 消息发送器
**文件**: `messaging/message_sender.py`

```python
class MessageSender:
    - send_quip(): 发送节点提示消息
    - send_expression(): 发送表情/动画消息
    - send_chat_message(): 发送聊天消息
    - send_error(): 发送错误消息
    - send_status(): 发送状态更新
```

**特性**:
- 统一的消息格式
- 自动添加 channel 信息
- 支持元数据扩展

#### 3.3 LangGraph 集成
**文件**: `agent_workflow/agent_graph.py`

**节点定义**:
- `start`: 开始节点
- `planning`: 规划节点
- `coding`: 代码生成节点
- `executing`: 执行节点
- `analyzing`: 分析节点
- `done`: 完成节点
- `error`: 错误节点

**节点行为**:
- 每个节点切换时调用 `on_node_change()` 发送 quip 和 expression
- 只有 `done` 节点发送最终的 chat 消息
- `error` 节点发送错误消息

### 4. 统一消息格式

#### 4.1 消息包结构
```json
{
  "_id": "msg_168xxxx",
  "_timestamp": "2026-05-06T08:00:00Z",
  "_channel": "agent:chat",
  "type": "chat",
  "node_name": "done",
  "timestamp": "2026-05-06T08:00:00Z",
  "metadata": { ... }
}
```

#### 4.2 各类型消息格式

**Quip 消息**:
```json
{
  "type": "quip",
  "content": "进入 planning 节点，开始分析需求。",
  "node_name": "planning",
  "timestamp": "...",
  "metadata": {
    "priority": "medium",
    "duration": 3000
  },
  "_channel": "agent:quip"
}
```

**Expression 消息**:
```json
{
  "type": "expression",
  "expression": "thinking",
  "intensity": 0.8,
  "node_name": "planning",
  "timestamp": "...",
  "metadata": {
    "duration": 5000,
    "transition": "smooth"
  },
  "_channel": "agent:expression"
}
```

**Chat 消息**:
```json
{
  "type": "chat",
  "role": "assistant",
  "content": "这是最终输出内容。",
  "timestamp": "...",
  "metadata": {
    "is_partial": false,
    "sequence_id": 1,
    "total_parts": 1,
    "node_name": "done"
  },
  "_channel": "agent:chat"
}
```

### 5. API 接口设计

#### 5.1 消息队列接口

**GET /messages**
- 描述: 获取待发送消息
- 参数: `since_id` (可选) - 从哪个消息 ID 开始获取
- 返回:
```json
{
  "ok": true,
  "messages": [...],
  "count": 10
}
```

**DELETE /messages**
- 描述: 清空消息队列
- 返回:
```json
{
  "ok": true,
  "message": "消息队列已清空"
}
```

#### 5.2 其他新增接口

**GET /llm/diagnostics**
- 描述: LLM 配置诊断
- 参数: `check_remote` (可选) - 是否测试远程连接

**GET /runs/summary**
- 描述: 轻量级任务摘要列表
- 参数: `offset`, `limit`

**GET /health**
- 描述: 健康检查
- 返回新增 `startup_recovery` 字段

### 6. 前后端通信方法

#### 6.1 通信流程
1. 后端将消息写入全局 `message_queue`
2. 前端定期调用 `GET /messages?since_id=...` 轮询获取新消息
3. 前端根据 `_channel` 和 `type` 进行路由和展示

#### 6.2 前端处理建议

**Quip/Expression 消息**:
- 仅用于 UI 装饰、节点提示、角色表情变化
- 不显示在聊天窗口中

**Chat 消息**:
- 作为 AI Agent 聊天窗口的最终输出
- 支持 `is_partial` 分片处理

**Status/Error 消息**:
- 用于状态条、进度条、系统异常提示
- 不写入对话历史

### 7. 数据模型扩展

#### 7.1 新增 Schema 字段

**ChatResponse**:
- 新增 `ok`: bool
- 新增 `error`: str | None

**RunResponse**:
- 新增 `generator`, `attempt_count`, `repair_attempted`, `repair_count`
- 新增 `started_at`, `finished_at`, `duration_ms`

**RunAttemptResponse**:
- 新增 `stdout_length`, `stderr_length`, `error_length`
- 新增裁剪标志字段

#### 7.2 新增 Schema 类型

**RunSummaryResponse**: 轻量级任务摘要
**RunSummaryListResponse**: 任务摘要列表
**LLMDiagnosticsResponse**: LLM 诊断结果

### 8. 测试与验证

#### 8.1 测试命令系统

系统提供了完整的测试命令集：
- `/test quip [node]`: 测试 Quip 消息
- `/test expression [expr]`: 测试表情消息
- `/test chat [content]`: 测试聊天消息
- `/test error`: 测试错误消息
- `/test status [status] [progress] [node]`: 测试状态消息
- `/test workflow`: 测试完整工作流
- `/test all`: 测试所有消息类型

#### 8.2 节点映射配置

**文件**: `agent_workflow/node_mappings.py`

定义了每个节点对应的 quip 内容和表情：
```python
NODE_MAPPINGS = {
    'start': ('开始执行任务...', 'thinking'),
    'planning': ('正在分析需求...', 'focused'),
    'coding': ('正在生成代码...', 'coding'),
    'executing': ('正在执行代码...', 'working'),
    'analyzing': ('正在分析结果...', 'analyzing'),
    'done': ('任务完成！', 'happy'),
    'error': ('任务失败', 'sad')
}
```

### 9. 系统特性

#### 9.1 启动恢复
- 后端启动时扫描 `runs/` 目录
- 将遗留的 `queued`/`running` 任务标记为 `failed`
- 在 `/health` 接口中返回恢复统计信息

#### 9.2 并发安全
- 任务存储增加线程锁
- 原子写入防止并发损坏
- 消息队列线程安全设计

#### 9.3 错误处理
- 完善的错误消息机制
- LLM 调用失败时的详细错误信息
- 任务执行失败的状态跟踪

### 10. 未来扩展建议

#### 10.1 统一事件包
建议使用统一的 `EventEnvelope` 格式：
```json
{
  "_id": "...",
  "_channel": "agent:chat",
  "type": "chat",
  "display_target": "agent_chat",
  "payload": { ... }
}
```

#### 10.2 长输出分片
- `metadata.is_partial`: 是否为分片
- `metadata.sequence_id`: 分片序号
- `metadata.total_parts`: 总分片数

#### 10.3 WebSocket 支持
当前使用轮询机制，未来可考虑升级为 WebSocket 实现更高效的实时通信。

---

## 需求满足度检查

### 原始需求对照检查

✅ **需求1**: 彻底封装好后端未来的通信接口
- **实现**: 创建了统一的 `MessageSender` 类和消息队列系统
- **验证**: 所有消息都通过统一接口发送，格式一致

✅ **需求2**: 彻底优化好后端需要发的数据格式
- **实现**: 定义了统一的消息包格式，包含 `_id`, `_timestamp`, `_channel` 等字段
- **验证**: 所有消息类型都遵循相同的结构

✅ **需求3**: 区分表情 quip 和真正的 AI agent 聊天窗口的区别
- **实现**: 明确区分 `quip`/`expression` 和 `chat` 消息类型
- **验证**: 通过 `_channel` 字段区分 (`agent:quip`, `agent:expression`, `agent:chat`)

✅ **需求4**: 做好数据区分
- **实现**: 每个消息类型都有明确的用途和展示目标
- **验证**: 前端可根据 `_channel` 和 `type` 进行精确路由

✅ **需求5**: 当进入不同的 LangGraph 节点时发送不同的 quip 和表情
- **实现**: `on_node_change()` 函数在每个节点切换时自动发送对应消息
- **验证**: `node_mappings.py` 定义了每个节点的 quip 和表情映射

✅ **需求6**: AI agent 聊天窗口只在全部做完或遇到长输出时才收到信息
- **实现**: 只有 `done` 节点发送 `chat` 消息，其他节点只发送装饰性消息
- **验证**: `agent_graph.py` 中 `done_node()` 是唯一发送 chat 消息的节点

✅ **需求7**: 约定好统一的数据结果
- **实现**: 所有消息都包含统一的核心字段和类型定义
- **验证**: `schemas.py` 中定义了完整的数据模型

✅ **需求8**: 写一个给后端开发者看的 markdown 说明文档
- **实现**: 创建了 `COMMUNICATION_INTERFACE.md` 详细文档
- **验证**: 文档包含接口说明、数据格式、通信方法等完整内容

✅ **需求9**: 把前后端通信方法也写入 markdown
- **实现**: 文档中详细描述了前后端通信流程和 API 接口
- **验证**: 包含消息队列 API、轮询机制、前端处理建议等

### 结论

**新版本完全满足原始需求**，并且在以下方面还有额外增强：

1. **完善的测试系统**: 提供了完整的测试命令集，方便开发者验证功能
2. **LLM 诊断接口**: 新增 LLM 配置检查和远程连接测试
3. **任务摘要接口**: 轻量级任务列表，优化前端性能
4. **启动恢复机制**: 自动处理遗留任务，提高系统健壮性
5. **并发安全**: 线程锁和原子写入，防止并发问题
6. **错误处理**: 完善的错误消息和状态跟踪

新版本不仅满足了所有原始需求，还提供了一个生产级的、可扩展的、易于维护的通信接口架构。
        