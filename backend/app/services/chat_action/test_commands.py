from ...agent_workflow.node_mappings import get_node_quip_and_expression
from ...messaging.message_sender import message_sender


TEST_PREFIXES = ("/test", "/测试", "test:", "测试:")


def is_test_command(prompt: str) -> bool:
    return any(prompt.lower().startswith(prefix) for prefix in TEST_PREFIXES)


def handle_test_command(prompt: str) -> str:
    command = prompt.lower()

    if "/test quip" in command or "test:quip" in command:
        node_name = command.split()[-1] if len(command.split()) > 2 else "start"
        quip_content, expression = get_node_quip_and_expression(node_name)
        message_sender.send_quip(
            content=quip_content,
            node_name=node_name,
            priority="medium",
            duration=3000,
        )
        message_sender.send_expression(
            expression=expression,
            node_name=node_name,
            intensity=0.8,
            duration=5000,
            transition="smooth",
        )
        return f"✓ 测试成功：已发送 Quip 和 Expression 消息（节点: {node_name}）"

    if "/test expression" in command or "test:expression" in command:
        expression = command.split()[-1] if len(command.split()) > 2 else "thinking"
        message_sender.send_expression(
            expression=expression,
            node_name=expression,
            intensity=0.8,
            duration=5000,
            transition="smooth",
        )
        return f"✓ 测试成功：已发送 Expression 消息（表情: {expression}）"

    if "/test chat" in command or "test:chat" in command:
        content = " ".join(command.split()[2:]) if len(command.split()) > 2 else "这是一个测试消息。"
        message_sender.send_chat_message(
            content=content,
            is_partial=False,
            node_name="done",
        )
        return f"✓ 测试成功：已发送 Chat 消息（内容: {content}）"

    if "/test error" in command or "test:error" in command:
        message_sender.send_error(
            code="TEST_ERROR",
            message="这是一个测试错误",
            details="测试错误详情",
            node_name="error",
        )
        return "✓ 测试成功：已发送 Error 消息"

    if "/test status" in command or "test:status" in command:
        parts = command.split()
        status = parts[2] if len(parts) > 2 else "running"
        progress = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 50
        node_name = parts[4] if len(parts) > 4 else "coding"
        message_sender.send_status(
            status=status,
            progress=progress,
            node_name=node_name,
        )
        return f"✓ 测试成功：已发送 Status 消息（状态: {status}, 进度: {progress}%, 节点: {node_name}）"

    if "/test workflow" in command or "test:workflow" in command:
        return run_test_workflow()

    if "/test error-workflow" in command or "test:error-workflow" in command:
        return run_error_workflow()

    if "/test all" in command or "test:all" in command:
        return test_all_messages()

    if "/test help" in command or "test:help" in command or "/test" == command.strip():
        return get_test_help()

    return "❌ 未知的测试命令。输入 /test help 查看可用命令。"


def emit_node_updates(node_name: str, *, progress: int | None = None, status: str = "running") -> None:
    quip_content, expression = get_node_quip_and_expression(node_name)
    message_sender.send_quip(
        content=quip_content,
        node_name=node_name,
        priority="medium",
        duration=3000,
    )
    message_sender.send_expression(
        expression=expression,
        node_name=node_name,
        intensity=0.8,
        duration=5000,
        transition="smooth",
    )
    message_sender.send_status(
        status=status,
        progress=progress,
        node_name=node_name,
    )


def run_test_workflow() -> str:
    nodes = ("start", "planning", "coding", "executing", "analyzing", "done")
    progress_values = (0, 10, 30, 60, 80, 100)
    for node_name, progress in zip(nodes, progress_values, strict=True):
        status = "done" if node_name == "done" else "running"
        emit_node_updates(node_name, progress=progress, status=status)

    message_sender.send_chat_message(
        content="任务执行成功！这是最终的输出结果。",
        is_partial=False,
        node_name="done",
    )
    return "✓ 测试成功：完整工作流已运行（6 个节点）"


def run_error_workflow() -> str:
    nodes = ("start", "planning", "coding")
    progress_values = (0, 10, 30)
    for node_name, progress in zip(nodes, progress_values, strict=True):
        emit_node_updates(node_name, progress=progress, status="running")

    emit_node_updates("error", status="error")
    message_sender.send_error(
        code="EXECUTION_FAILED",
        message="任务执行失败",
        details="模拟的错误场景",
        node_name="error",
    )
    return "✓ 测试成功：错误工作流已运行"


def test_all_messages() -> str:
    message_sender.send_quip(
        content="测试 Quip 消息",
        node_name="start",
        priority="medium",
        duration=3000,
    )
    message_sender.send_expression(
        expression="thinking",
        node_name="start",
        intensity=0.8,
        duration=5000,
        transition="smooth",
    )
    message_sender.send_chat_message(
        content="测试 Chat 消息",
        is_partial=False,
        node_name="done",
    )
    message_sender.send_status(
        status="running",
        progress=50,
        node_name="coding",
    )
    message_sender.send_error(
        code="TEST_ERROR",
        message="测试错误消息",
        details="测试详情",
        node_name="error",
    )
    return "✓ 测试成功：所有消息类型已发送（Quip, Expression, Chat, Status, Error）"


def get_test_help() -> str:
    return """🧪 AI Agent 测试命令帮助

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

提示：所有测试命令都不需要真实的 LLM API，直接测试消息传输功能。"""
