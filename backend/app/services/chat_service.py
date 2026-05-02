from backend.app.llm.client import call_llm
from backend.app.schemas import INTENT_TYPE


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


async def build_chat_reply(prompt: str, context: str | None) -> str:
    return await call_llm(prompt, context)


def build_coding_reply(prompt: str, context: str | None) -> str:
    _ = context
    return (
        "这是代码任务分支。\n\n"
        f"我识别到你的请求更像是一个开发任务：{prompt}\n\n"
        "建议后续把这个分支继续拆成：\n"
        "1. 需求分析\n"
        "2. 任务拆分\n"
        "3. 代码生成\n"
        "4. 测试与修复\n\n"
        "当前项目里，下一步最适合先补安全文件读写和命令执行。"
    )


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
