from ...schemas import INTENT_TYPE


CODING_KEYWORDS = (
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
    "frontend",
)

CHAT_KEYWORDS = (
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
    "how",
)


def contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def detect_intent(prompt: str) -> INTENT_TYPE:
    text = prompt.lower()
    if contains_any_keyword(text, CODING_KEYWORDS):
        return "coding"
    if contains_any_keyword(text, CHAT_KEYWORDS):
        return "chat"
    return "unknown"
