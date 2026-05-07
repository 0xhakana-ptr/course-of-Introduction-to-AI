from datetime import datetime, timezone
import logging
import os
from typing import Any


message_queue = None
logger = logging.getLogger(__name__)


def get_message_queue():
    """获取消息队列实例"""
    global message_queue
    if message_queue is None:
        from ..message_queue import message_queue as mq
        message_queue = mq
    return message_queue

class MessageSender:
    """负责向后端发送消息到前端"""
    
    def __init__(self):
        self.electron_ipc_available = os.getenv('ELECTRON_IPC_AVAILABLE', 'false').lower() == 'true'
    
    def _get_timestamp(self) -> str:
        """获取 ISO 8601 格式时间戳"""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def _send_to_frontend(self, channel: str, message: dict[str, Any]) -> bool:
        """发送消息到前端
        
        Args:
            channel: IPC channel 名称
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        # 将消息添加到队列
        mq = get_message_queue()
        if mq:
            # 添加 channel 信息到消息中
            message['_channel'] = channel
            message_id = mq.add_message(message)
            logger.debug("Frontend message queued: id=%s channel=%s", message_id, channel)
            return True
        logger.warning("Message queue unavailable; frontend message was not sent: channel=%s", channel)
        return False
    
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
    
    def send_expression(
        self,
        expression: str,
        node_name: str,
        intensity: float = 0.8,
        duration: int = 5000,
        transition: str = 'smooth',
        mode: str = 'set',
    ) -> bool:
        """发送表情消息"""
        message = {
            'type': 'expression',
            'expression': expression,
            'mode': mode,
            'intensity': intensity,
            'node_name': node_name,
            'timestamp': self._get_timestamp(),
            'metadata': {
                'duration': duration,
                'transition': transition
            }
        }
        return self._send_to_frontend('agent:expression', message)

    def send_motion(
        self,
        motion: str,
        node_name: str,
        duration: int | None = None,
        loop: bool = False,
    ) -> bool:
        """发送动作消息"""
        metadata: dict[str, Any] = {'loop': loop}
        if duration is not None:
            metadata['duration'] = duration
        message = {
            'type': 'motion',
            'motion': motion,
            'node_name': node_name,
            'timestamp': self._get_timestamp(),
            'metadata': metadata,
        }
        return self._send_to_frontend('agent:motion', message)
    
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
    
    def send_status(self, status: str, progress: int | None = None, node_name: str = '') -> bool:
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
