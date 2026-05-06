from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ..messaging.message_sender import message_sender
from .node_mappings import get_node_quip_and_expression, should_send_chat_message
from ..core.config import settings


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
