from ...llm.client import LLMCallResult, call_llm
from .types import ChatServiceResult


async def build_chat_reply(prompt: str, context: str | None) -> LLMCallResult:
    return await call_llm(prompt, context)


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
