import re

from ...schemas import (
    WORKSPACE_TOOL_CATEGORY,
    WORKSPACE_TOOL_ERROR_CODE,
    WORKSPACE_TOOL_OUTPUT_KIND,
)


DEFAULT_TOOL_TEXT_LIMIT = 4000
DEFAULT_TOOL_ENTRY_LIMIT = 200
DEFAULT_FAILURE_SUMMARY_LIMIT = 1200
DEFAULT_TOOL_TEST_TIMEOUT_SECONDS = 20
DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT = 12
DEFAULT_WORKSPACE_OVERVIEW_FILE_PREVIEW_LIMIT = 600
DEFAULT_WORKSPACE_OVERVIEW_FILES = (
    "README.md",
    "backend/README.md",
    "backend/requirements.txt",
)
DEFAULT_WORKSPACE_TEST_PATH_CANDIDATES = (
    "backend/tests",
    "tests",
)
DEFAULT_WRITE_TEXT_LIMIT = 8000
DEFAULT_WRITE_TEXT_REL_PATH = "generated/request.txt"
DEFAULT_DESKTOP_EXPORT_FILE_NAME = "request.txt"
CODE_CONTENT_SUFFIXES = frozenset(
    {
        ".bash",
        ".bat",
        ".c",
        ".cc",
        ".cpp",
        ".css",
        ".go",
        ".h",
        ".hpp",
        ".html",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".kt",
        ".php",
        ".ps1",
        ".py",
        ".rb",
        ".rs",
        ".sh",
        ".sql",
        ".ts",
        ".tsx",
        ".vue",
        ".xml",
        ".yaml",
        ".yml",
    }
)
WORKSPACE_TOOL_NAME_OVERVIEW = "build_workspace_overview"
WORKSPACE_TOOL_NAME_LIST = "list_workspace_entries"
WORKSPACE_TOOL_NAME_READ = "read_workspace_text"
WORKSPACE_TOOL_NAME_TEST = "run_workspace_tests"
WORKSPACE_TOOL_NAME_WRITE = "write_workspace_text"
WORKSPACE_TOOL_NAME_MOVE = "move_workspace_path"
WORKSPACE_TOOL_NAME_COPY = "copy_workspace_path"
WORKSPACE_TOOL_NAME_DELETE = "delete_workspace_path"
WORKSPACE_TOOL_NAME_SEARCH = "search_workspace_text"
WORKSPACE_TOOL_CATEGORY_CONTEXT: WORKSPACE_TOOL_CATEGORY = "context"
WORKSPACE_TOOL_CATEGORY_EXECUTION: WORKSPACE_TOOL_CATEGORY = "execution"
WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW: WORKSPACE_TOOL_OUTPUT_KIND = "overview_text"
WORKSPACE_TOOL_OUTPUT_KIND_LISTING: WORKSPACE_TOOL_OUTPUT_KIND = "entry_listing"
WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW: WORKSPACE_TOOL_OUTPUT_KIND = "file_preview"
WORKSPACE_TOOL_OUTPUT_KIND_COMMAND_RESULT: WORKSPACE_TOOL_OUTPUT_KIND = "command_result"
WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE: WORKSPACE_TOOL_OUTPUT_KIND = "file_write"
WORKSPACE_TOOL_OUTPUT_KIND_FILE_OPERATION: WORKSPACE_TOOL_OUTPUT_KIND = "file_operation"
WORKSPACE_TOOL_OUTPUT_KIND_TEXT_SEARCH: WORKSPACE_TOOL_OUTPUT_KIND = "text_search"
WORKSPACE_TOOL_ERROR_UNREGISTERED: WORKSPACE_TOOL_ERROR_CODE = "WORKSPACE_TOOL_UNREGISTERED"
WORKSPACE_TOOL_ERROR_EXECUTION_FAILED: WORKSPACE_TOOL_ERROR_CODE = (
    "WORKSPACE_TOOL_EXECUTION_FAILED"
)
WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED: WORKSPACE_TOOL_ERROR_CODE = (
    "WORKSPACE_TOOL_TARGET_UNSUPPORTED"
)
WORKSPACE_TOOL_ERROR_TARGET_DISABLED: WORKSPACE_TOOL_ERROR_CODE = (
    "WORKSPACE_TOOL_TARGET_DISABLED"
)
WORKSPACE_TOOL_PATH_PATTERN = re.compile(
    r"(?:[\w\u4e00-\u9fff_.-]+[\\/])+[\w\u4e00-\u9fff_.-]*|[\w\u4e00-\u9fff_.-]+\.[A-Za-z0-9_-]+"
)
WORKSPACE_TOOL_QUOTED_PATH_PATTERN = re.compile(
    r"[`\"'“”‘’]([^`\"'“”‘’]+)[`\"'“”‘’]"
)
WORKSPACE_TOOL_TEST_KEYWORDS = (
    "pytest",
    "test",
    "tests",
    "单元测试",
    "测试",
    "运行测试",
    "run tests",
)
WORKSPACE_TOOL_LIST_KEYWORDS = (
    "目录",
    "结构",
    "文件列表",
    "list",
    "ls",
    "tree",
)
WORKSPACE_TOOL_READ_KEYWORDS = (
    "读取",
    "读一下",
    "查看",
    "看一下",
    "显示",
    "打开",
    "预览",
    "read",
    "show",
    "view",
    "open",
    "cat",
    "preview",
)
WORKSPACE_TOOL_WRITE_KEYWORDS = (
    "创建",
    "新建",
    "写入",
    "保存",
    "create",
    "new",
    "write",
    "save",
)
WORKSPACE_TOOL_MOVE_KEYWORDS = (
    "重命名",
    "改名",
    "移动",
    "移到",
    "挪到",
    "rename",
    "move",
)
WORKSPACE_TOOL_COPY_KEYWORDS = (
    "复制",
    "拷贝",
    "copy",
    "duplicate",
)
WORKSPACE_TOOL_DELETE_KEYWORDS = (
    "删除",
    "删掉",
    "移除",
    "delete",
    "remove",
)
WORKSPACE_TOOL_SEARCH_KEYWORDS = (
    "搜索",
    "查找",
    "包含",
    "含有",
    "search",
    "find",
    "grep",
    "contains",
)
WORKSPACE_TOOL_DIRECTORY_KEYWORDS = (
    "目录",
    "文件夹",
    "folder",
    "directory",
    "dir",
)
WORKSPACE_TOOL_RECURSIVE_KEYWORDS = (
    "递归",
    "及其内容",
    "所有内容",
    "整个目录",
    "整个文件夹",
    "里面所有",
    "全部内容",
    "recursive",
    "recursively",
    "with contents",
)
WORKSPACE_TOOL_TEXT_FILE_KEYWORDS = (
    ".txt",
    "txt",
    "文本文件",
    "text file",
)
WORKSPACE_TOOL_DESKTOP_KEYWORDS = (
    "桌面",
    "desktop",
)
WORKSPACE_TOOL_CODEGEN_TASK_KEYWORDS = (
    "修复",
    "修改",
    "改",
    "优化",
    "实现",
    "编写",
    "开发",
    "生成代码",
    "写代码",
    "重构",
    "补充",
    "完善",
    "新增功能",
    "分析",
    "诊断",
    "问题",
    "报错",
    "失败",
    "bug",
    "fix",
    "modify",
    "update",
    "change",
    "optimize",
    "implement",
    "build",
    "develop",
    "generate code",
    "write code",
    "refactor",
    "add feature",
    "analyze",
    "diagnose",
    "problem",
    "error",
    "failed",
    "failure",
)
WORKSPACE_TOOL_INPUT_KEYS = (
    "rel_path",
    "recursive",
    "max_entries",
    "max_chars",
    "test_paths",
    "cwd",
    "timeout_seconds",
    "max_output_chars",
    "include_files",
    "file_preview_chars",
    "content",
    "overwrite",
    "target_location",
    "source_path",
    "target_path",
    "query",
    "max_matches",
)

