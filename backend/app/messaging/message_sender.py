from datetime import datetime, timezone
import logging
import os
from typing import Any

from .event_types import AGENT_EVENT_SOURCE, AGENT_EVENT_STAGE, AGENT_EVENT_TYPE
from .runtime_events import build_runtime_event_fields, require_channel_for_message_type
from ..schemas import MESSAGE_STATUS, MESSAGE_TYPE


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

    def _build_message(
        self,
        *,
        message_type: MESSAGE_TYPE,
        node_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        event_type: AGENT_EVENT_TYPE,
        event_source: AGENT_EVENT_SOURCE,
        event_stage: AGENT_EVENT_STAGE,
        frontend_visible: bool = True,
        **fields: Any,
    ) -> dict[str, Any]:
        message: dict[str, Any] = {
            "type": message_type,
            "timestamp": self._get_timestamp(),
            **build_runtime_event_fields(
                event_type=event_type,
                event_source=event_source,
                event_stage=event_stage,
                frontend_visible=frontend_visible,
            ),
        }
        if node_name:
            message["node_name"] = node_name
        if metadata:
            message["metadata"] = dict(metadata)
        message.update(fields)
        return message

    def _send_message(self, message_type: MESSAGE_TYPE, message: dict[str, Any]) -> bool:
        return self._send_to_frontend(require_channel_for_message_type(message_type), message)

    def send_quip(
        self,
        content: str,
        node_name: str,
        priority: str = 'medium',
        duration: int = 3000,
        *,
        metadata: dict[str, Any] | None = None,
        event_type: AGENT_EVENT_TYPE = "character.quip",
        event_source: AGENT_EVENT_SOURCE = "character",
        event_stage: AGENT_EVENT_STAGE = "roleplay",
    ) -> bool:
        """发送 Quip 消息"""
        message_type: MESSAGE_TYPE = "quip"
        message_metadata = {
            'priority': priority,
            'duration': duration,
        }
        if metadata:
            message_metadata.update(metadata)
        message = self._build_message(
            message_type=message_type,
            content=content,
            node_name=node_name,
            metadata=message_metadata,
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
        )
        return self._send_message(message_type, message)
    
    def send_expression(
        self,
        expression: str,
        node_name: str,
        intensity: float = 0.8,
        duration: int = 5000,
        transition: str = 'smooth',
        mode: str = 'set',
        *,
        event_type: AGENT_EVENT_TYPE = "character.expression",
        event_source: AGENT_EVENT_SOURCE = "character",
        event_stage: AGENT_EVENT_STAGE = "roleplay",
    ) -> bool:
        """发送表情消息"""
        message_type: MESSAGE_TYPE = "expression"
        message = self._build_message(
            message_type=message_type,
            expression=expression,
            mode=mode,
            intensity=intensity,
            node_name=node_name,
            metadata={
                'duration': duration,
                'transition': transition,
            },
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
        )
        return self._send_message(message_type, message)

    def send_motion(
        self,
        motion: str,
        node_name: str,
        duration: int | None = None,
        loop: bool = False,
        *,
        event_type: AGENT_EVENT_TYPE = "character.motion",
        event_source: AGENT_EVENT_SOURCE = "character",
        event_stage: AGENT_EVENT_STAGE = "roleplay",
    ) -> bool:
        """发送动作消息"""
        metadata: dict[str, Any] = {'loop': loop}
        if duration is not None:
            metadata['duration'] = duration
        message_type: MESSAGE_TYPE = "motion"
        message = self._build_message(
            message_type=message_type,
            motion=motion,
            node_name=node_name,
            metadata=metadata,
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
        )
        return self._send_message(message_type, message)
    
    def send_chat_message(
        self,
        content: str,
        is_partial: bool = False,
        sequence_id: int = 0,
        total_parts: int = 1,
        node_name: str = '',
        *,
        event_type: AGENT_EVENT_TYPE = "chat.message",
        event_source: AGENT_EVENT_SOURCE = "roleplay",
        event_stage: AGENT_EVENT_STAGE = "roleplay",
    ) -> bool:
        """发送 Chat 消息"""
        message_type: MESSAGE_TYPE = "chat"
        message = self._build_message(
            message_type=message_type,
            role='assistant',
            content=content,
            node_name=node_name or None,
            metadata={
                'is_partial': is_partial,
                'sequence_id': sequence_id,
                'total_parts': total_parts,
                'node_name': node_name,
            },
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
        )
        return self._send_message(message_type, message)
    
    def send_error(
        self,
        code: str,
        message: str,
        details: Any = None,
        node_name: str = '',
        *,
        event_type: AGENT_EVENT_TYPE = "system.error",
        event_source: AGENT_EVENT_SOURCE = "system",
        event_stage: AGENT_EVENT_STAGE = "system",
    ) -> bool:
        """发送错误消息"""
        message_type: MESSAGE_TYPE = "error"
        error_message = self._build_message(
            message_type=message_type,
            code=code,
            message=message,
            details=details,
            node_name=node_name or None,
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
        )
        return self._send_message(message_type, error_message)
    
    def send_status(
        self,
        status: MESSAGE_STATUS,
        progress: int | None = None,
        node_name: str = '',
        *,
        metadata: dict[str, Any] | None = None,
        event_type: AGENT_EVENT_TYPE = "status.updated",
        event_source: AGENT_EVENT_SOURCE = "system",
        event_stage: AGENT_EVENT_STAGE = "system",
    ) -> bool:
        """发送状态更新"""
        message_type: MESSAGE_TYPE = "status"
        status_message = self._build_message(
            message_type=message_type,
            status=status,
            progress=progress,
            node_name=node_name or None,
            metadata=metadata,
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
        )
        return self._send_message(message_type, status_message)


# 全局消息发送器实例
message_sender = MessageSender()
