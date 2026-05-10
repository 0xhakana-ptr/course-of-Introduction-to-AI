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