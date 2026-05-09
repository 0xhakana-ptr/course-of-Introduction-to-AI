import re
from typing import Literal

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
    "modify",
    "open",
    "optimize",
    "read",
    "refactor",
    "run",
    "test",
    "update",
    "write",
)

STRONG_OPERATION_ACTION_KEYWORDS = (
    "写",
    "改",
    "修改",
    "修",
    "修复",
    "调试",
    "运行",
    "执行",
    "生成",
    "创建",
    "实现",
    "测试",
    "读取",
    "重构",
    "add",
    "build",
    "create",
    "debug",
    "edit",
    "execute",
    "fix",
    "implement",
    "modify",
    "read",
    "refactor",
    "run",
    "test",
    "update",
    "write",
)

WORKSPACE_OBJECT_KEYWORDS = (
    "代码",
    "脚本",
    "程序",
    "项目",
    "工程",
    "仓库",
    "文件",
    "目录",
    "路径",
    "模块",
    "包",
    "依赖",
    "配置",
    "接口",
    "路由",
    "服务",
    "后端",
    "前端",
    "组件",
    "页面",
    "函数",
    "方法",
    "类",
    "变量",
    "测试",
    "用例",
    "日志",
    "命令",
    "终端",
    "api",
    "backend",
    "bug",
    "code",
    "command",
    "component",
    "config",
    "directory",
    "error",
    "file",
    "frontend",
    "function",
    "interface",
    "log",
    "module",
    "project",
    "route",
    "script",
    "service",
    "shell",
    "test",
    "terminal",
)

TECH_CONTEXT_KEYWORDS = (
    "python",
    "java",
    "cpp",
    "c++",
    "javascript",
    "typescript",
    "vue",
    "react",
    "fastapi",
    "node",
    "pytest",
    "uvicorn",
    "pnpm",
    "npm",
    "git",
)

COMMAND_INLINE_KEYWORDS = (
    "pytest",
    "pnpm",
    "npm",
    "yarn",
    "uvicorn",
    "python",
    "node",
    "pip",
    "poetry",
    "curl",
    "powershell",
)

CODING_ISSUE_KEYWORDS = (
    "bug",
    "报错",
    "错误",
    "异常",
    "崩溃",
    "失败",
    "traceback",
    "exception",
    "stderr",
    "stdout",
    "failed",
    "failure",
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
COMMAND_REFERENCE_PATTERN = re.compile(
    r"(?:^|[\s`\"'(<\[])(?:pytest|pnpm|npm|yarn|uv|uvicorn|python|node|git|pip|poetry|curl|powershell|cmd|bash|sh)(?:$|[\s`\"')>\],:;])",
    re.IGNORECASE,
)
NATURAL_LANGUAGE_PATTERN = re.compile(r"[A-Za-z\u4e00-\u9fff]")
MATH_EXPRESSION_PATTERN = re.compile(
    r"^\s*[\d\s+\-*/%=().]+(?:[?？]|等于几|等于多少|结果是多少|怎么算)?\s*$"
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


def contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _contains_keyword_casefold(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in text or keyword.lower() in lowered for keyword in keywords)


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


def has_command_reference(prompt: str) -> bool:
    text = str(prompt or "")
    return COMMAND_REFERENCE_PATTERN.search(text) is not None or _contains_keyword_casefold(
        text,
        COMMAND_INLINE_KEYWORDS,
    )


def _is_empty_or_noise_prompt(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if NATURAL_LANGUAGE_PATTERN.search(stripped) is not None:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    return True


def _is_symbolic_or_empty_prompt(text: str) -> bool:
    return _is_empty_or_noise_prompt(text)


def looks_like_math_question(prompt: str) -> bool:
    text = str(prompt or "").strip()
    return MATH_EXPRESSION_PATTERN.fullmatch(text) is not None


def _has_code_structure_hint(prompt: str) -> bool:
    return _contains_keyword_casefold(str(prompt or ""), CODE_STRUCTURE_HINTS)


def _has_workspace_object(prompt: str) -> bool:
    return _contains_keyword_casefold(str(prompt or ""), WORKSPACE_OBJECT_KEYWORDS)


def _has_tech_context(prompt: str) -> bool:
    return _contains_keyword_casefold(str(prompt or ""), TECH_CONTEXT_KEYWORDS)


def _has_coding_action(prompt: str) -> bool:
    return _contains_keyword_casefold(str(prompt or ""), CODING_ACTION_KEYWORDS)


def _has_strong_operation_action(prompt: str) -> bool:
    return _contains_keyword_casefold(str(prompt or ""), STRONG_OPERATION_ACTION_KEYWORDS)


def _has_issue_keyword(prompt: str) -> bool:
    return _contains_keyword_casefold(str(prompt or ""), CODING_ISSUE_KEYWORDS)


def looks_like_coding_prompt(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if not text:
        return False
    if has_file_reference(text) or _has_code_structure_hint(text):
        return True

    has_action = _has_coding_action(text)
    has_strong_action = _has_strong_operation_action(text)
    has_workspace_object = _has_workspace_object(text)
    has_command = has_command_reference(text)
    has_issue = _has_issue_keyword(text)
    has_tech_context = _has_tech_context(text)

    if has_issue and (has_workspace_object or has_command or has_tech_context):
        return True
    if has_action and (has_workspace_object or has_command):
        return True
    if has_strong_action and has_tech_context:
        return True
    return False


def looks_like_chat_prompt(prompt: str) -> bool:
    text = str(prompt or "").strip()
    return not _is_empty_or_noise_prompt(text) and not looks_like_coding_prompt(text)


def normalize_intent_label(value: str | None) -> INTENT_TYPE | None:
    text = str(value or "").strip().lower()
    if text in {"chat", "coding", "unknown"}:
        return text  # type: ignore[return-value]

    matched = re.search(r"\b(chat|coding|unknown)\b", text)
    if matched is None:
        return None
    return matched.group(1)  # type: ignore[return-value]


def classify_intent_with_llm(_prompt: str) -> INTENT_TYPE | None:
    # The frontend-facing agent now uses a narrow deterministic router.
    # Keeping this compatibility hook avoids reintroducing token-heavy pre-classification.
    return None


def detect_intent(prompt: str) -> INTENT_TYPE:
    text = str(prompt or "").strip()
    if _is_empty_or_noise_prompt(text):
        return "unknown"
    if detect_run_action(text) != "create":
        return "coding"
    if looks_like_coding_prompt(text):
        return "coding"
    return "chat"
