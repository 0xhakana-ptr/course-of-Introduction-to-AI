# AI Agent 后端通信接口规范文档 - 实现指南

## 7. 工作区代码实现指南

### 7.1 实现概述

本指南详细说明如何修改现有工作区代码以实现文档中描述的功能。主要修改包括：

1. **后端修改**：添加 LangGraph 集成和消息发送机制
2. **Electron 主进程修改**：添加消息转发逻辑
3. **前端组件修改**：接收并处理不同类型的消息

### 7.2 后端实现

#### 7.2.1 安装依赖

首先，在 `backend/requirements.txt` 中添加 LangGraph 相关依赖：

```text
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic>=2.0,<3.0
httpx>=0.28,<1.0
python-dotenv>=1.0,<2.0
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
```

#### 7.2.2 创建消息发送模块

创建新文件 `backend/app/messaging/message_sender.py`：

```python
from datetime import datetime, timezone
from typing import Any, Dict
import json
import os


class MessageSender:
    """负责向后端发送消息到前端"""
    
    def __init__(self):
        self.electron_ipc_available = os.getenv('ELECTRON_IPC_AVAILABLE', 'false').lower() == 'true'
    
    def _get_timestamp(self) -> str:
        """获取 ISO 8601 格式时间戳"""
        return datetime.now(timezone.utc).isoformat() + 'Z'
    
    def _send_to_frontend(self, channel: str, message: Dict[str, Any]) -> bool:
        """发送消息到前端
        
        Args:
            channel: IPC channel 名称
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        if not self.electron_ipc_available:
            # 如果 Electron IPC 不可用，记录到日志
            print(f"[MessageSender] Would send to {channel}: {json.dumps(message, ensure_ascii=False)}")
            return False
        
        # TODO: 实现实际的 IPC 发送逻辑
        # 这里需要与 Electron 主进程建立连接
        print(f"[MessageSender] Sending to {channel}: {json.dumps(message, ensure_ascii=False)}")
        return True
    
    def send_quip(self, content: str, node_name: str, priority: str = 'medium', duration: int = 3000) -> bool:
        """发送 Quip 消息"""
        message = {
            'type': 'quip',
            'content': content,
            'node_name': node_name,
            'timestamp': self._get_timestamp(),
            'metadata': {
                'priority': priority,
                'duration': duration
            }
        }
        return self._send_to_frontend('agent:quip', message)
    
    def send_expression(self, expression: str, node_name: str, intensity: float = 0.8, 
                        duration: int = 5000, transition: str = 'smooth') -> bool:
        """发送表情消息"""
        message = {
            'type': 'expression',
            'expression': expression,
            'intensity': intensity,
            'node_name': node_name,
            'timestamp': self._get_timestamp(),
            'metadata': {
                'duration': duration,
                'transition': transition
            }
        }
        return self._send_to_frontend('agent:expression', message)
    
    def send_chat_message(self, content: str, is_partial: bool = False, 
                         sequence_id: int = 0, total_parts: int = 1, node_name: str = '') -> bool:
        """发送 Chat 消息"""
        message = {
            'type': 'chat',
            'role': 'assistant',
            'content': content,
            'timestamp': self._get_timestamp(),
            'metadata': {
                'is_partial': is_partial,
                'sequence_id': sequence_id,
                'total_parts': total_parts,
                'node_name': node_name
            }
        }
        return self._send_to_frontend('agent:chat', message)
    
    def send_error(self, code: str, message: str, details: Any = None, node_name: str = '') -> bool:
        """发送错误消息"""
        error_message = {
            'type': 'error',
            'code': code,
            'message': message,
            'details': details,
            'timestamp': self._get_timestamp(),
            'node_name': node_name
        }
        return self._send_to_frontend('agent:error', error_message)
    
    def send_status(self, status: str, progress: int = None, node_name: str = '') -> bool:
        """发送状态更新"""
        status_message = {
            'type': 'status',
            'status': status,
            'progress': progress,
            'node_name': node_name,
            'timestamp': self._get_timestamp()
        }
        return self._send_to_frontend('agent:status', status_message)


# 全局消息发送器实例
message_sender = MessageSender()
```

#### 7.2.3 创建 LangGraph 节点映射模块

创建新文件 `backend/app/langgraph/node_mappings.py`：

```python
from typing import Tuple


def get_node_quip_and_expression(node_name: str) -> Tuple[str, str]:
    """获取节点对应的 Quip 和表情
    
    Args:
        node_name: LangGraph 节点名称
        
    Returns:
        (quip_content, expression_name)
    """
    node_mappings = {
        'start': ('开始思考...', 'thinking'),
        'planning': ('正在规划任务...', 'focused'),
        'coding': ('正在编写代码...', 'coding'),
        'executing': ('正在执行代码...', 'working'),
        'analyzing': ('正在分析结果...', 'analyzing'),
        'repairing': ('正在修复问题...', 'worried'),
        'done': ('任务完成！', 'happy'),
        'error': ('遇到错误...', 'sad')
    }
    return node_mappings.get(node_name, ('处理中...', 'neutral'))


def should_send_chat_message(content: str, node_name: str) -> bool:
    """判断是否应该发送 Chat 消息
    
    Args:
        content: 消息内容
        node_name: 节点名称
        
    Returns:
        是否应该发送
    """
    # 任务完成时发送
    if node_name in ['done', 'error']:
        return True
    
    # 长输出时发送（>500 字符）
    if len(content) > 500:
        return True
    
    return False
```

#### 7.2.4 创建 LangGraph 集成模块

创建新文件 `backend/app/langgraph/agent_graph.py`：

```python
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from backend.app.messaging.message_sender import message_sender
from backend.app.langgraph.node_mappings import get_node_quip_and_expression, should_send_chat_message
from backend.app.core.config import settings


class AgentState(TypedDict):
    """Agent 状态定义"""
    messages: Annotated[Sequence[BaseMessage], "消息历史"]
    current_node: str
    output: str
    error: str | None


def on_node_change(node_name: str):
    """LangGraph 节点切换时的回调
    
    Args:
        node_name: 新节点名称
    """
    # 获取节点对应的 Quip 和表情
    quip_content, expression = get_node_quip_and_expression(node_name)
    
    # 发送 Quip
    message_sender.send_quip(
        content=quip_content,
        node_name=node_name,
        priority='medium',
        duration=3000
    )
    
    # 发送表情
    message_sender.send_expression(
        expression=expression,
        node_name=node_name,
        intensity=0.8,
        duration=5000,
        transition='smooth'
    )


def create_llm():
    """创建 LLM 实例"""
    if not settings.llm_base_url or not settings.llm_api_key:
        return None
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=0.3
    )


# ========== LangGraph 节点定义 ==========

def start_node(state: AgentState) -> AgentState:
    """开始节点"""
    on_node_change('start')
    message_sender.send_status('running', progress=0, node_name='start')
    
    return {**state, 'current_node': 'start'}


def planning_node(state: AgentState) -> AgentState:
    """规划节点"""
    on_node_change('planning')
    message_sender.send_status('running', progress=10, node_name='planning')
    
    return {**state, 'current_node': 'planning'}


def coding_node(state: AgentState) -> AgentState:
    """代码生成节点"""
    on_node_change('coding')
    message_sender.send_status('running', progress=30, node_name='coding')
    
    return {**state, 'current_node': 'coding'}


def executing_node(state: AgentState) -> AgentState:
    """执行节点"""
    on_node_change('executing')
    message_sender.send_status('running', progress=60, node_name='executing')
    
    return {**state, 'current_node': 'executing'}


def analyzing_node(state: AgentState) -> AgentState:
    """分析节点"""
    on_node_change('analyzing')
    message_sender.send_status('running', progress=80, node_name='analyzing')
    
    return {**state, 'current_node': 'analyzing'}


def done_node(state: AgentState) -> AgentState:
    """完成节点"""
    on_node_change('done')
    message_sender.send_status('done', progress=100, node_name='done')
    
    # 发送最终结果到聊天窗口
    output = state.get('output', '任务执行成功')
    if should_send_chat_message(output, 'done'):
        message_sender.send_chat_message(
            content=output,
            is_partial=False,
            node_name='done'
        )
    
    return {**state, 'current_node': 'done'}


def error_node(state: AgentState) -> AgentState:
    """错误节点"""
    on_node_change('error')
    message_sender.send_status('error', node_name='error')
    
    # 发送错误消息到聊天窗口
    error_msg = state.get('error', '未知错误')
    message_sender.send_error(
        code='EXECUTION_FAILED',
        message=error_msg,
        node_name='error'
    )
    
    return {**state, 'current_node': 'error'}


# ========== 构建图 ==========

def create_agent_graph():
    """创建 Agent 图"""
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("start", start_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("coding", coding_node)
    workflow.add_node("executing", executing_node)
    workflow.add_node("analyzing", analyzing_node)
    workflow.add_node("done", done_node)
    workflow.add_node("error", error_node)
    
    # 设置入口点
    workflow.set_entry_point("start")
    
    # 添加边
    workflow.add_edge("start", "planning")
    workflow.add_edge("planning", "coding")
    workflow.add_edge("coding", "executing")
    workflow.add_edge("executing", "analyzing")
    
    # 条件边：根据分析结果决定是完成还是出错
    def decide_next(state: AgentState) -> str:
        if state.get('error'):
            return "error"
        return "done"
    
    workflow.add_conditional_edges(
        "analyzing",
        decide_next,
        {
            "done": "done",
            "error": "error"
        }
    )
    
    workflow.add_edge("done", END)
    workflow.add_edge("error", END)
    
    return workflow.compile()


# 全局图实例
agent_graph = create_agent_graph()


def run_agent(prompt: str, context: str | None = None) -> dict:
    """运行 Agent
    
    Args:
        prompt: 用户输入
        context: 上下文
        
    Returns:
        执行结果
    """
    initial_state: AgentState = {
        'messages': [HumanMessage(content=prompt)],
        'current_node': '',
        'output': '',
        'error': None
    }
    
    try:
        result = agent_graph.invoke(initial_state)
        return {
            'ok': True,
            'output': result.get('output', ''),
            'state': result
        }
    except Exception as e:
        return {
            'ok': False,
            'output': f'执行失败: {str(e)}',
            'error': str(e)
        }
```

#### 7.2.5 修改 chat_service.py

修改 `backend/app/services/chat_service.py`，集成 LangGraph：

```python
from backend.app.llm.client import call_llm
from backend.app.schemas import INTENT_TYPE
from backend.app.langgraph.agent_graph import run_agent


def detect_intent(prompt: str) -> INTENT_TYPE:
    text = prompt.lower()

    coding_keywords = [
        "代码", "脚本", "程序", "接口", "后端", "前端",
        "bug", "报错", "调试", "修复", "python", "java",
        "cpp", "c++", "vue", "react", "fastapi", "api",
        "write code", "debug", "fix", "backend", "frontend"
    ]
    chat_keywords = [
        "你好", "你是谁", "介绍一下", "怎么做", "为什么",
        "是什么", "hello", "hi", "what", "why", "how"
    ]

    if any(word in text for word in coding_keywords):
        return "coding"
    if any(word in text for word in chat_keywords):
        return "chat"
    return "unknown"


async def build_chat_reply(prompt: str, context: str | None) -> str:
    return await call_llm(prompt, context)


def build_coding_reply(prompt: str, context: str | None) -> str:
    # 使用 LangGraph 运行 Agent
    result = run_agent(prompt, context)
    return result.get('output', '任务执行中...')


def build_unknown_reply(prompt: str) -> str:
    return (
        "抱歉，我暂时还不能很好地判断你的意图。\n\n"
        f"你输入的内容是：{prompt}\n\n"
        "你可以继续补充信息，或者明确说明你是想聊天还是想让我帮你处理代码任务。"
    )


async def generate_chat_response(prompt: str, context: str | None) -> tuple[INTENT_TYPE, str]:
    intent = detect_intent(prompt)

    if intent == "chat":
        return intent, await build_chat_reply(prompt, context)
    if intent == "coding":
        return intent, build_coding_reply(prompt, context)
    return intent, build_unknown_reply(prompt)
```

### 7.3 Electron 主进程实现

#### 7.3.1 修改 electron/main.ts

在 `electron/main.ts` 中添加消息转发逻辑。你需要：

1. 在文件开头添加类型定义
2. 在 `app.whenReady()` 之前添加消息转发处理器
3. 修改 `runBackendAgent` 函数以支持消息转发

### 7.4 前端组件实现

#### 7.4.1 修改 Live2DConsole.vue

修改 `src/components/Live2DConsole.vue`，添加 Quip 和表情接收功能：

1. 添加 Quip 和表情消息类型定义
2. 添加 `handleQuip` 和 `handleExpression` 函数
3. 在 `onMounted` 中注册消息监听器
4. 在 `onUnmounted` 中移除消息监听器
5. 添加 UI 元素显示当前 Quip 和表情

#### 7.4.2 修改 AgentChat.vue

修改 `src/components/AgentChat.vue`，添加消息接收和流式输出处理：

1. 添加 Chat、Error、Status 消息类型定义
2. 添加 `handleChat`、`handleError`、`handleStatus` 函数
3. 添加部分消息存储逻辑（`partialMessages`）
4. 在 `onMounted` 中注册消息监听器
5. 在 `onUnmounted` 中移除消息监听器
6. 添加 UI 元素显示当前状态、进度和节点

### 7.5 配置文件修改

#### 7.5.1 创建 messaging 模块的 __init__.py

创建 `backend/app/messaging/__init__.py`：

```python
from backend.app.messaging.message_sender import message_sender

__all__ = ['message_sender']
```

#### 7.5.2 创建 langgraph 模块的 __init__.py

创建 `backend/app/langgraph/__init__.py`：

```python
from backend.app.langgraph.agent_graph import agent_graph, run_agent
from backend.app.langgraph.node_mappings import get_node_quip_and_expression, should_send_chat_message

__all__ = ['agent_graph', 'run_agent', 'get_node_quip_and_expression', 'should_send_chat_message']
```

### 7.6 测试和验证

#### 7.6.1 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m backend.app.main
```

#### 7.6.2 启动 Electron

```bash
pnpm dev
```

#### 7.6.3 测试流程

1. 在 AI Chat 窗口输入一个代码任务，例如："帮我写一个计算器"
2. 观察 Live2D 控制台是否收到 Quip 和表情消息
3. 观察 AI Chat 窗口是否在任务完成时收到最终结果
4. 测试错误场景，观察错误消息是否正确显示

### 7.7 故障排除

#### 7.7.1 消息未发送

- 检查 `ELECTRON_IPC_AVAILABLE` 环境变量是否设置为 `true`
- 检查 Electron 主进程是否正确监听了消息
- 检查前端组件是否正确注册了消息监听器

#### 7.7.2 LangGraph 未正常工作

- 检查是否正确安装了 LangGraph 依赖
- 检查 LLM 配置是否正确（`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`）
- 查看后端日志，确认节点切换是否正常

#### 7.7.3 前端组件未收到消息

- 打开浏览器开发者工具，查看 Console 是否有错误
- 检查 IPC channel 名称是否匹配
- 确认窗口是否正确创建（`mainWindow`, `quipWindow`, `chatWindow`）

### 7.8 后续优化建议

1. **性能优化**：对于大量消息，考虑使用消息队列和批处理
2. **错误恢复**：添加消息重试机制和错误恢复逻辑
3. **日志记录**：完善前后端日志记录，便于调试
4. **配置管理**：将节点映射和消息配置移到配置文件中
5. **单元测试**：为关键功能添加单元测试