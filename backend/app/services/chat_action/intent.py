import re
from typing import Literal

from ...llm.client import call_llm_sync, llm_is_configured
from ...schemas import INTENT_TYPE


RUN_ACTION_TYPE = Literal["create", "inspect", "retry", "rerun", "cancel"]
CODING_ACTION_KEYWORDS = (
    "写",
    "改",
    "修改",
    "修",
    "修复",
    "调试",
    "排查",
    "检查",
    "查看",
    "打开",
    "运行",
    "执行",
    "生成",
    "创建",
    "实现",
    "测试",
    "读取",
    "重构",
    "优化",
    "分析",
    "看看",
    "查查",
    "补",
    "add",
    "build",
    "check",
    "create",
    "debug",
    "edit",
    "execute",
    "fix",
    "implement",
    "inspect",
    "open",
    "optimize",
    "read",
    "refactor",
    "run",
    "test",
    "update",
    "write",
)
CODING_OBJECT_KEYWORDS = (
    "代码",
    "脚本",
    "程序",
    "接口",
    "文件",
    "目录",
    "后端",
    "前端",
    "bug",
    "报错",
    "调试",
    "修复",
    "测试",
    "pytest",
    "terminal",
    "命令",
    "日志",
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
CODING_ISSUE_KEYWORDS = (
    "bug",
    "报错",
    "错误",
    "异常",
    "崩溃",
    "traceback",
    "exception",
    "stderr",
    "stdout",
)

CHAT_KEYWORDS = (
    "你好",
    "你是谁",
    "我是谁",
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
FILE_REFERENCE_PATTERN = re.compile(
    r"(?:^|[\s`\"'(<\[])[\w./\\-]+\.(?:py|pyi|js|jsx|ts|tsx|vue|json|yaml|yml|toml|ini|md|txt|c|cc|cpp|h|hpp|java|rs|go|sh|ps1|bat)(?:$|[\s`\"')>\],:;])",
    re.IGNORECASE,
)
NATURAL_LANGUAGE_PATTERN = re.compile(r"[A-Za-z\u4e00-\u9fff]")
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]+")
CHAT_HINTS = (
    "我",
    "你",
    "我们",
    "你们",
    "谁",
    "吗",
    "呢",
    "吧",
    "呀",
    "请",
    "帮我",
    "告诉我",
    "解释",
    "介绍",
    "记得",
    "想问",
    "想知道",
)
CODE_STRUCTURE_HINTS = (
    "def ",
    "class ",
    "import ",
    "from ",
    "console.",
    "function ",
    "=>",
    "Traceback",
    "Exception",
)
INTENT_CLASSIFIER_SYSTEM_PROMPT = """
You are the intent router for a local AI desktop companion.
Classify only the user's latest input into exactly one label:
- chat: normal conversation, memory questions, identity/persona questions, conceptual explanations, or general discussion.
- coding: requests to write, modify, inspect, debug, run, test, read files/logs, or operate on project/code tasks.
- unknown: only for non-linguistic noise or content that cannot reasonably be classified.

Rules:
- Prefer chat over unknown for normal human language.
- Prefer coding when the user is asking about code, files, logs, commands, tests, errors, or project structure.
- Return only one lowercase word: chat, coding, or unknown.
""".strip()


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


def has_file_reference(prompt: str) -> bool:
    return FILE_REFERENCE_PATTERN.search(str(prompt or "")) is not None


def _is_symbolic_or_empty_prompt(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    return NATURAL_LANGUAGE_PATTERN.search(stripped) is None


def has_strong_chat_signal(prompt: str) -> bool:
    text = str(prompt or "").strip()
    lowered = text.lower()
    if contains_any_keyword(lowered, CHAT_KEYWORDS):
        return True
    if any(hint in text for hint in CHAT_HINTS):
        return True
    if "?" in text or "？" in text:
        return True
    return False


def looks_like_chat_prompt(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if _is_symbolic_or_empty_prompt(text):
        return False

    if has_strong_chat_signal(text):
        return True
    if " " in text and LATIN_WORD_PATTERN.search(text):
        return True
    if len(text) >= 4 and CJK_PATTERN.search(text):
        return True
    return False


def looks_like_coding_prompt(prompt: str) -> bool:
    text = str(prompt or "").strip()
    lowered = text.lower()
    if not text:
        return False
    if has_file_reference(text):
        return True
    if contains_any_keyword(text, CODING_ISSUE_KEYWORDS) or contains_any_keyword(lowered, CODING_ISSUE_KEYWORDS):
        return True
    if contains_any_keyword(text, CODE_STRUCTURE_HINTS) or contains_any_keyword(lowered, CODE_STRUCTURE_HINTS):
        return True
    return (
        contains_any_keyword(text, CODING_ACTION_KEYWORDS)
        or contains_any_keyword(lowered, CODING_ACTION_KEYWORDS)
    ) and (
        contains_any_keyword(text, CODING_OBJECT_KEYWORDS)
        or contains_any_keyword(lowered, CODING_OBJECT_KEYWORDS)
    )


def normalize_intent_label(value: str | None) -> INTENT_TYPE | None:
    text = str(value or "").strip().lower()
    if text in {"chat", "coding", "unknown"}:
        return text  # type: ignore[return-value]

    matched = re.search(r"\b(chat|coding|unknown)\b", text)
    if matched is None:
        return None
    return matched.group(1)  # type: ignore[return-value]


def classify_intent_with_llm(prompt: str) -> INTENT_TYPE | None:
    if not llm_is_configured():
        return None

    result = call_llm_sync(
        prompt,
        None,
        system_prompt=INTENT_CLASSIFIER_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=8,
    )
    if not result.ok:
        return None
    return normalize_intent_label(result.output)


def detect_intent(prompt: str) -> INTENT_TYPE:
    text = str(prompt or "")
    if detect_run_action(prompt) != "create":
        return "coding"
    if looks_like_coding_prompt(prompt):
        return "coding"
    if _is_symbolic_or_empty_prompt(text):
        return "unknown"
    if has_strong_chat_signal(prompt):
        return "chat"
    llm_intent = classify_intent_with_llm(prompt)
    if llm_intent == "coding":
        return "coding"
    if llm_intent == "chat":
        return "chat"
    if looks_like_chat_prompt(prompt):
        return "chat"
    # Default to chat for general questions
    return "chat"
