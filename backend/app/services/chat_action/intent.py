import re
from typing import Literal

from ...schemas import INTENT_TYPE


RUN_ACTION_TYPE = Literal["create", "inspect", "retry", "rerun", "cancel"]
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
RUN_INSPECTION_KEYWORDS = (
    "run_id",
    "任务",
    "状态",
    "进度",
    "快照",
    "查看",
    "查询",
    "inspect",
    "snapshot",
    "日志",
    "log",
    "attempt",
    "结果",
)
RUN_RETRY_KEYWORDS = ("retry", "重试", "再试一次")
RUN_RERUN_KEYWORDS = ("rerun", "重新运行", "重新执行", "重新跑", "再跑一次")
RUN_CANCEL_KEYWORDS = ("cancel", "取消", "停止", "终止")
RUN_REFERENCE_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def extract_run_reference(prompt: str) -> str | None:
    matched = RUN_REFERENCE_PATTERN.search(str(prompt or ""))
    if matched is None:
        return None
    return matched.group(0)


def detect_run_action(prompt: str) -> RUN_ACTION_TYPE:
    text = str(prompt or "").lower()
    if extract_run_reference(prompt) is None:
        return "create"
    if contains_any_keyword(text, RUN_RETRY_KEYWORDS):
        return "retry"
    if contains_any_keyword(text, RUN_RERUN_KEYWORDS):
        return "rerun"
    if contains_any_keyword(text, RUN_CANCEL_KEYWORDS):
        return "cancel"
    if contains_any_keyword(text, RUN_INSPECTION_KEYWORDS):
        return "inspect"
    return "create"


def looks_like_run_inspection_request(prompt: str) -> bool:
    return detect_run_action(prompt) == "inspect"


def detect_intent(prompt: str) -> INTENT_TYPE:
    text = prompt.lower()
    if detect_run_action(prompt) != "create":
        return "coding"
    if contains_any_keyword(text, CODING_KEYWORDS):
        return "coding"
    if contains_any_keyword(text, CHAT_KEYWORDS):
        return "chat"
    # Default to chat for general questions
    return "chat"
