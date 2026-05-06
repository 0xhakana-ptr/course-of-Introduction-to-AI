from typing import List, Dict, Any
import time
from datetime import datetime, timezone


class MessageQueue:
    """消息队列，用于存储待发送的消息"""
    
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.max_size = 1000
    
    def add_message(self, message: Dict[str, Any]) -> str:
        """添加消息到队列
        
        Args:
            message: 消息内容
            
        Returns:
            消息 ID
        """
        message_id = f"msg_{int(time.time() * 1000)}"
        message['_id'] = message_id
        message['_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        self.messages.append(message)
        
        # 限制队列大小
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]
        
        print(f"[MessageQueue] 添加消息: {message_id}, 类型: {message.get('type')}, 总数: {len(self.messages)}")
        return message_id
    
    def get_messages(self, since_id: str = None) -> List[Dict[str, Any]]:
        """获取消息
        
        Args:
            since_id: 从哪个消息 ID 开始获取
            
        Returns:
            消息列表
        """
        if since_id is None:
            return self.messages.copy()
        
        # 找到 since_id 的索引
        start_index = 0
        for i, msg in enumerate(self.messages):
            if msg.get('_id') == since_id:
                start_index = i + 1
                break
        
        result = self.messages[start_index:]
        if result:
            print(f"[MessageQueue] 获取消息: {len(result)} 条, 从: {since_id}")
        return result
    
    def clear(self):
        """清空队列"""
        count = len(self.messages)
        self.messages.clear()
        print(f"[MessageQueue] 清空队列: {count} 条消息")


# 全局消息队列实例
message_queue = MessageQueue()