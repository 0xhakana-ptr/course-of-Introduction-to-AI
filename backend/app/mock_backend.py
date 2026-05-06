"""
模拟后端测试脚本
用于在不启动完整后端的情况下测试前端消息接收功能
"""

from typing import List, Dict, Any
import time
from datetime import datetime, timezone
import json
import threading
import asyncio
import websockets
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class MessageQueue:
    """消息队列，用于存储待发送的消息"""
    
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.max_size = 1000
        self.last_get_time = 0
        self.message_counter = 0  # 消息计数器，确保 ID 唯一
    
    def add_message(self, message: Dict[str, Any]) -> str:
        """添加消息到队列"""
        # 使用计数器确保消息 ID 唯一
        self.message_counter += 1
        message_id = f"msg_{int(time.time() * 1000)}_{self.message_counter}"
        message['_id'] = message_id
        message['_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        self.messages.append(message)
        
        # 限制队列大小
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size:]
        
        # 添加换行符，确保日志不会干扰用户输入
        print(f"\n[MessageQueue] 添加消息: {message_id}, 类型: {message.get('type')}, 总数: {len(self.messages)}")
        return message_id
    
    def get_messages(self, since_id: str = None) -> List[Dict[str, Any]]:
        """获取消息"""
        if since_id is None:
            return self.messages.copy()
        
        # 找到 since_id 的索引
        start_index = None
        for i, msg in enumerate(self.messages):
            if msg.get('_id') == since_id:
                start_index = i + 1
                break
        
        # 如果 since_id 不存在，返回空列表（避免死循环）
        if start_index is None:
            return []
        
        result = self.messages[start_index:]
        # 禁用 get_messages 的日志输出，避免干扰用户输入
        # if result:
        #     print(f"[MessageQueue] 获取消息: {len(result)} 条, 从: {since_id}")
        return result
    
    def clear(self):
        """清空队列"""
        count = len(self.messages)
        self.messages.clear()
        print(f"[MessageQueue] 清空队列: {count} 条消息")


class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.clients = set()
        self.loop = None  # 事件循环
    
    def set_event_loop(self, loop):
        """设置事件循环"""
        self.loop = loop
    
    async def register(self, websocket):
        """注册新的 WebSocket 连接"""
        self.clients.add(websocket)
        print(f"[WebSocket] 新客户端连接，当前连接数: {len(self.clients)}")
    
    async def unregister(self, websocket):
        """注销 WebSocket 连接"""
        self.clients.discard(websocket)
        print(f"[WebSocket] 客户端断开，当前连接数: {len(self.clients)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接的客户端"""
        if not self.clients:
            return
        
        message_json = json.dumps(message, ensure_ascii=False)
        disconnected = set()
        
        for client in self.clients:
            try:
                await client.send(message_json)
            except Exception as e:
                print(f"[WebSocket] 发送消息失败: {e}")
                disconnected.add(client)
        
        # 移除断开的连接
        for client in disconnected:
            self.clients.discard(client)
    
    def broadcast_sync(self, message: Dict[str, Any]):
        """同步广播消息（用于在非异步上下文中调用）"""
        if self.loop is None:
            print("[WebSocket] 警告: 事件循环未设置，无法广播消息")
            return
        
        asyncio.run_coroutine_threadsafe(
            self.broadcast(message),
            self.loop
        )


# 全局 WebSocket 管理器
ws_manager = WebSocketManager()


class MockBackendHandler(BaseHTTPRequestHandler):
    """模拟后端的 HTTP 请求处理器"""
    
    message_queue = MessageQueue()
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/messages':
            # 获取消息队列
            query = parse_qs(parsed_path.query)
            since_id = query.get('since_id', [None])[0]
            
            messages = self.message_queue.get_messages(since_id)
            
            response = {
                'ok': True,
                'messages': messages,
                'count': len(messages)
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_DELETE(self):
        """处理 DELETE 请求"""
        if self.path == '/messages':
            # 清空消息队列
            self.message_queue.clear()
            
            response = {
                'ok': True,
                'message': '消息队列已清空'
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """禁用默认的日志输出"""
        pass


def send_quip(content: str, node_name: str = 'start', priority: str = 'medium', duration: int = 3000):
    """发送 Quip 消息"""
    message = {
        'type': 'quip',
        'content': content,
        'node_name': node_name,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        'metadata': {
            'priority': priority,
            'duration': duration
        },
        '_channel': 'agent:quip'
    }
    # 使用 WebSocket 同步广播消息
    ws_manager.broadcast_sync(message)
    print(f"✓ 已发送 Quip 消息: {content}")


def send_expression(expression: str, node_name: str = 'start', intensity: float = 0.8, 
                     duration: int = 5000, transition: str = 'smooth'):
    """发送表情消息"""
    message = {
        'type': 'expression',
        'expression': expression,
        'intensity': intensity,
        'node_name': node_name,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        'metadata': {
            'duration': duration,
            'transition': transition
        },
        '_channel': 'agent:expression'
    }
    # 使用 WebSocket 同步广播消息
    ws_manager.broadcast_sync(message)
    print(f"✓ 已发送 Expression 消息: {expression}")


def send_chat_message(content: str, is_partial: bool = False, 
                       sequence_id: int = 0, total_parts: int = 1, node_name: str = 'done'):
    """发送 Chat 消息"""
    message = {
        'type': 'chat',
        'role': 'assistant',
        'content': content,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        'metadata': {
            'is_partial': is_partial,
            'sequence_id': sequence_id,
            'total_parts': total_parts,
            'node_name': node_name
        },
        '_channel': 'agent:chat'
    }
    # 使用 WebSocket 同步广播消息
    ws_manager.broadcast_sync(message)
    print(f"✓ 已发送 Chat 消息: {content}")


def send_error(code: str, message: str, details: Any = None, node_name: str = 'error'):
    """发送错误消息"""
    error_message = {
        'type': 'error',
        'code': code,
        'message': message,
        'details': details,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        'node_name': node_name,
        '_channel': 'agent:error'
    }
    # 使用 WebSocket 同步广播消息
    ws_manager.broadcast_sync(error_message)
    print(f"✓ 已发送 Error 消息: {code} - {message}")


def send_status(status: str, progress: int = None, node_name: str = ''):
    """发送状态更新"""
    status_message = {
        'type': 'status',
        'status': status,
        'progress': progress,
        'node_name': node_name,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        '_channel': 'agent:status'
    }
    # 使用 WebSocket 同步广播消息
    ws_manager.broadcast_sync(status_message)
    print(f"✓ 已发送 Status 消息: {status}")


def run_test_workflow():
    """运行完整测试工作流"""
    nodes = [
        ('start', '开始思考...', 'thinking', 0),
        ('planning', '正在规划任务...', 'focused', 10),
        ('coding', '正在编写代码...', 'coding', 30),
        ('executing', '正在执行代码...', 'working', 60),
        ('analyzing', '正在分析结果...', 'analyzing', 80),
        ('done', '任务完成！', 'happy', 100)
    ]
    
    for node_name, quip_content, expression, progress in nodes:
        send_quip(quip_content, node_name)
        send_expression(expression, node_name)
        send_status('running', progress, node_name)
        time.sleep(1)  # 模拟处理时间
    
    # 发送最终结果
    send_chat_message('任务执行成功！这是最终的输出结果。', node_name='done')
    print("✓ 完整工作流已运行")


def run_error_workflow():
    """运行错误测试工作流"""
    nodes = [
        ('start', '开始思考...', 'thinking', 0),
        ('planning', '正在规划任务...', 'focused', 10),
        ('coding', '正在编写代码...', 'coding', 30),
        ('error', '遇到错误...', 'sad', None)
    ]
    
    for node_name, quip_content, expression, progress in nodes:
        send_quip(quip_content, node_name)
        send_expression(expression, node_name)
        
        if node_name == 'error':
            send_status('error', node_name='error')
            send_error('EXECUTION_FAILED', '任务执行失败', '模拟的错误场景', node_name='error')
        else:
            send_status('running', progress, node_name)
        
        time.sleep(1)
    
    print("✓ 错误工作流已运行")


async def websocket_handler(websocket):
    """WebSocket 处理器"""
    await ws_manager.register(websocket)
    try:
        async for message in websocket:
            # 处理来自客户端的消息（如果需要）
            pass
    finally:
        await ws_manager.unregister(websocket)


async def start_websocket_server(port: int = 8001):
    """启动 WebSocket 服务器"""
    # 获取当前事件循环并设置给 WebSocketManager
    loop = asyncio.get_running_loop()
    ws_manager.set_event_loop(loop)
    
    async with websockets.serve(websocket_handler, "localhost", port):
        print(f"✓ WebSocket 服务器已启动: ws://localhost:{port}")
        await asyncio.Future()  # 永久运行


def start_mock_server(port: int = 8000):
    """启动模拟后端服务器"""
    server = HTTPServer(('localhost', port), MockBackendHandler)
    print(f"✓ 模拟后端服务器已启动: http://localhost:{port}")
    print(f"✓ 消息队列 API: http://localhost:{port}/messages")
    print(f"✓ 按 Ctrl+C 停止服务器")
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ 服务器已停止")
        server.shutdown()


def print_help():
    """打印帮助信息"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║              模拟后端测试工具 - 帮助信息                        ║
╚════════════════════════════════════════════════════════════════╝

可用命令：

1. 发送 Quip 消息：
   quip [内容] [节点名称]
   例如：quip 开始思考... start

2. 发送 Expression 消息：
   expression [表情名称] [节点名称]
   例如：expression thinking start
   可用表情：thinking, focused, coding, working, analyzing, happy, sad

3. 发送 Chat 消息：
   chat [内容]
   例如：chat 你好，这是测试消息

4. 发送 Error 消息：
   error [错误代码] [错误消息]
   例如：error TEST_ERROR 这是一个测试错误

5. 发送 Status 消息：
   status [状态] [进度] [节点名称]
   例如：status running 50 coding
   可用状态：running, done, error

6. 运行完整工作流：
   workflow

7. 运行错误工作流：
   error-workflow

8. 清空消息队列：
   clear

9. 显示帮助信息：
   help

10. 退出：
    exit

提示：
- 所有命令都不需要真实的 LLM API
- 直接测试消息传输功能
- 前端会自动轮询消息队列
""")


def main():
    """主函数"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║              模拟后端测试工具 v1.0 (WebSocket 版本)          ║
╚════════════════════════════════════════════════════════════════╝
""")
    
    # 启动 WebSocket 服务器（在新的事件循环中）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 在后台线程中启动 WebSocket 服务器
    def run_server():
        loop.run_until_complete(start_websocket_server(8001))
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)  # 等待服务器启动
    
    print_help()
    
    # 主循环
    while True:
        try:
            # 显示输入提示
            command = input("\n请输入命令（输入 help 查看帮助）: ").strip()
            
            if not command:
                continue
            
            parts = command.split()
            cmd = parts[0].lower()
            
            if cmd == 'help':
                print_help()
            
            elif cmd == 'exit':
                print("✓ 退出测试工具")
                break
            
            elif cmd == 'clear':
                MockBackendHandler.message_queue.clear()
                print("✓ 消息队列已清空")
            
            elif cmd == 'quip':
                content = ' '.join(parts[1:-1]) if len(parts) > 2 else '测试 Quip 消息'
                node_name = parts[-1] if len(parts) > 1 else 'start'
                send_quip(content, node_name)
            
            elif cmd == 'expression':
                expression = parts[1] if len(parts) > 1 else 'thinking'
                node_name = parts[2] if len(parts) > 2 else 'start'
                send_expression(expression, node_name)
            
            elif cmd == 'chat':
                content = ' '.join(parts[1:]) if len(parts) > 1 else '测试 Chat 消息'
                send_chat_message(content)
            
            elif cmd == 'error':
                code = parts[1] if len(parts) > 1 else 'TEST_ERROR'
                message = ' '.join(parts[2:]) if len(parts) > 2 else '测试错误消息'
                send_error(code, message)
            
            elif cmd == 'status':
                status = parts[1] if len(parts) > 1 else 'running'
                progress = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 50
                node_name = parts[3] if len(parts) > 3 else 'coding'
                send_status(status, progress, node_name)
            
            elif cmd == 'workflow':
                run_test_workflow()
            
            elif cmd == 'error-workflow':
                run_error_workflow()
            
            else:
                print(f"❌ 未知命令: {cmd}，输入 help 查看帮助")
        
        except KeyboardInterrupt:
            print("\n✓ 退出测试工具")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == '__main__':
    main()