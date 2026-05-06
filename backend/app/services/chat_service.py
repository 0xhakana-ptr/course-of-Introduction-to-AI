from llm.client import call_llm
from schemas import INTENT_TYPE
from agent_workflow.agent_graph import run_agent
from messaging.message_sender import message_sender
from agent_workflow.node_mappings import get_node_quip_and_expression
import asyncio

@dataclass(slots=True)
class ChatServiceResult:
    intent: INTENT_TYPE
    ok: bool
    output: str
    error: str | None = None


def detect_intent(prompt: str) -> INTENT_TYPE:
    text = prompt.lower()

    coding_keywords = [
        "代码",
        "脚本",
        "程序",
        "接口",
        "后端",
        "前端",
        "bug",
        "报错",
        "调试",
        "修复",
        "python",
        "java",
        "cpp",
        "c++",
        "vue",
        "react",
        "fastapi",
        "api",
        "write code",
        "debug",
        "fix",
        "backend",
        "frontend"
    ]
    chat_keywords = [
        "你好",
        "你是谁",
        "介绍一下",
        "怎么做",
        "为什么",
        "是什么",
        "hello",
        "hi",
        "what",
        "why",
        "how"
    ]

    if any(word in text for word in coding_keywords):
        return "coding"
    if any(word in text for word in chat_keywords):
        return "chat"
    return "unknown"


async def build_chat_reply(prompt: str, context: str | None) -> LLMCallResult:
    return await call_llm(prompt, context)


# def build_coding_reply(prompt: str, context: str | None) -> str:
#     _ = context
#     return (
#         "这是代码任务分支。\n\n"
#         f"我识别到你的请求更像是一个开发任务：{prompt}\n\n"
#         "建议后续把这个分支继续拆成：\n"
#         "1. 需求分析\n"
#         "2. 任务拆分\n"
#         "3. 代码生成\n"
#         "4. 测试与修复\n\n"
#         "当前项目里，下一步最适合先补安全文件读写和命令执行。"
#     )

def build_coding_reply(prompt: str, context: str | None) -> str:
    # 使用 LangGraph 运行 Agent
    result = run_agent(prompt, context)
    return result.get('output', '任务执行中...')


def build_unknown_reply(prompt: str) -> ChatServiceResult:
    return ChatServiceResult(
        intent="unknown",
        ok=True,
        output=(
            "抱歉，我暂时还不能很好地判断你的意图。\n\n"
            f"你输入的内容是：{prompt}\n\n"
            "你可以继续补充信息，或者明确说明你是想聊天还是想让我帮你处理代码任务。"
        ),
    )


def is_test_command(prompt: str) -> bool:
    """检测是否为测试命令"""
    test_prefixes = ['/test', '/测试', 'test:', '测试:']
    return any(prompt.lower().startswith(prefix) for prefix in test_prefixes)


def handle_test_command(prompt: str) -> str:
    """处理测试命令"""
    command = prompt.lower()
    
    # 测试 Quip 消息
    if '/test quip' in command or 'test:quip' in command:
        node_name = command.split()[-1] if len(command.split()) > 2 else 'start'
        quip_content, expression = get_node_quip_and_expression(node_name)
        
        message_sender.send_quip(
            content=quip_content,
            node_name=node_name,
            priority='medium',
            duration=3000
        )
        
        message_sender.send_expression(
            expression=expression,
            node_name=node_name,
            intensity=0.8,
            duration=5000,
            transition='smooth'
        )
        
        return f"✓ 测试成功：已发送 Quip 和 Expression 消息（节点: {node_name}）"
    
    # 测试 Expression 消息
    elif '/test expression' in command or 'test:expression' in command:
        expression = command.split()[-1] if len(command.split()) > 2 else 'thinking'
        
        message_sender.send_expression(
            expression=expression,
            node_name=expression,
            intensity=0.8,
            duration=5000,
            transition='smooth'
        )
        
        return f"✓ 测试成功：已发送 Expression 消息（表情: {expression}）"
    
    # 测试 Chat 消息
    elif '/test chat' in command or 'test:chat' in command:
        content = ' '.join(command.split()[2:]) if len(command.split()) > 2 else '这是一个测试消息。'
        
        message_sender.send_chat_message(
            content=content,
            is_partial=False,
            node_name='done'
        )
        
        return f"✓ 测试成功：已发送 Chat 消息（内容: {content}）"
    
    # 测试 Error 消息
    elif '/test error' in command or 'test:error' in command:
        message_sender.send_error(
            code='TEST_ERROR',
            message='这是一个测试错误',
            details='测试错误详情',
            node_name='error'
        )
        
        return '✓ 测试成功：已发送 Error 消息'
    
    # 测试 Status 消息
    elif '/test status' in command or 'test:status' in command:
        parts = command.split()
        status = parts[2] if len(parts) > 2 else 'running'
        progress = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 50
        node_name = parts[4] if len(parts) > 4 else 'coding'
        
        message_sender.send_status(
            status=status,
            progress=progress,
            node_name=node_name
        )
        
        return f"✓ 测试成功：已发送 Status 消息（状态: {status}, 进度: {progress}%, 节点: {node_name}）"
    
    # 测试完整工作流
    elif '/test workflow' in command or 'test:workflow' in command:
        return run_test_workflow()
    
    # 测试错误工作流
    elif '/test error-workflow' in command or 'test:error-workflow' in command:
        return run_error_workflow()
    
    # 测试所有消息类型
    elif '/test all' in command or 'test:all' in command:
        return test_all_messages()
    
    # 显示帮助信息
    elif '/test help' in command or 'test:help' in command or '/test' in command:
        return get_test_help()
    
    else:
        return '❌ 未知的测试命令。输入 /test help 查看可用命令。'


def run_test_workflow() -> str:
    """运行完整测试工作流"""
    nodes = ['start', 'planning', 'coding', 'executing', 'analyzing', 'done']
    progress = [0, 10, 30, 60, 80, 100]
    
    for i, node in enumerate(nodes):
        quip_content, expression = get_node_quip_and_expression(node)
        
        message_sender.send_quip(
            content=quip_content,
            node_name=node,
            priority='medium',
            duration=3000
        )
        
        message_sender.send_expression(
            expression=expression,
            node_name=node,
            intensity=0.8,
            duration=5000,
            transition='smooth'
        )
        
        message_sender.send_status(
            status='running',
            progress=progress[i],
            node_name=node
        )
    
    # 发送最终结果
    message_sender.send_chat_message(
        content='任务执行成功！这是最终的输出结果。',
        is_partial=False,
        node_name='done'
    )
    
    return '✓ 测试成功：完整工作流已运行（6 个节点）'


def run_error_workflow() -> str:
    """运行错误测试工作流"""
    nodes = ['start', 'planning', 'coding', 'error']
    progress = [0, 10, 30, None]
    
    for i, node in enumerate(nodes):
        quip_content, expression = get_node_quip_and_expression(node)
        
        message_sender.send_quip(
            content=quip_content,
            node_name=node,
            priority='medium',
            duration=3000
        )
        
        message_sender.send_expression(
            expression=expression,
            node_name=node,
            intensity=0.8,
            duration=5000,
            transition='smooth'
        )
        
        if node == 'error':
            message_sender.send_status(
                status='error',
                node_name='error'
            )
            
            message_sender.send_error(
                code='EXECUTION_FAILED',
                message='任务执行失败',
                details='模拟的错误场景',
                node_name='error'
            )
        else:
            message_sender.send_status(
                status='running',
                progress=progress[i],
                node_name=node
            )
    
    return '✓ 测试成功：错误工作流已运行'


def test_all_messages() -> str:
    """测试所有消息类型"""
    # Quip
    message_sender.send_quip(
        content='测试 Quip 消息',
        node_name='start',
        priority='medium',
        duration=3000
    )
    
    # Expression
    message_sender.send_expression(
        expression='thinking',
        node_name='start',
        intensity=0.8,
        duration=5000,
        transition='smooth'
    )
    
    # Chat
    message_sender.send_chat_message(
        content='测试 Chat 消息',
        is_partial=False,
        node_name='done'
    )
    
    # Status
    message_sender.send_status(
        status='running',
        progress=50,
        node_name='coding'
    )
    
    # Error
    message_sender.send_error(
        code='TEST_ERROR',
        message='测试错误消息',
        details='测试详情',
        node_name='error'
    )
    
    return '✓ 测试成功：所有消息类型已发送（Quip, Expression, Chat, Status, Error）'


def get_test_help() -> str:
    """获取测试命令帮助信息"""
    return '''🧪 AI Agent 测试命令帮助

可用命令：

1. 测试 Quip 消息：
   /test quip [节点名称]
   例如：/test quip start
   可用节点：start, planning, coding, executing, analyzing, done, error

2. 测试 Expression 消息：
   /test expression [表情名称]
   例如：/test expression thinking
   可用表情：thinking, focused, coding, working, analyzing, happy, sad

3. 测试 Chat 消息：
   /test chat [消息内容]
   例如：/test chat 你好

4. 测试 Error 消息：
   /test error

5. 测试 Status 消息：
   /test status [状态] [进度] [节点名称]
   例如：/test status running 50 coding
   可用状态：running, done, error

6. 测试完整工作流：
   /test workflow
   测试所有节点的消息发送

7. 测试错误工作流：
   /test error-workflow
   测试错误场景的消息发送

8. 测试所有消息类型：
   /test all
   一次性测试所有消息类型

9. 显示帮助信息：
   /test help

提示：所有测试命令都不需要真实的 LLM API，直接测试消息传输功能。'''



async def generate_chat_response(prompt: str, context: str | None) -> tuple[INTENT_TYPE, str]:
    # 优先检查是否为测试命令
    if is_test_command(prompt):
        return 'test', handle_test_command(prompt)
    
    intent = detect_intent(prompt)

    if intent == "chat":
        result = await build_chat_reply(prompt, context)
        return ChatServiceResult(
            intent=intent,
            ok=result.ok,
            output=result.output,
            error=result.error,
        )
    if intent == "coding":
        return intent, build_coding_reply(prompt, context)
    return intent, build_unknown_reply(prompt)
