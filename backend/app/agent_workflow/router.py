# -*- coding: utf-8 -*-
"""Layer 1: Routing Guard.

Independent layer that detects user intent and determines routing.
Does NOT execute work - only classifies and routes.
Uses lightweight LLM extraction only for complex workspace actions that need
structured parameters (write, delete, move, copy, test, search).
Read/list use heuristic extraction for speed.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from ..llm.client import call_llm_sync
from ..core.limits import ROUTER_LLM_EXTRACTION_MAX_TOKENS
from .intent import detect_intent, detect_run_action, extract_run_reference

logger = logging.getLogger(__name__)

# Intent constants
INTENT_CHAT = "chat"
INTENT_CODING = "coding"
INTENT_UNKNOWN = "unknown"

# ---------------------------------------------------------------------------
# Coding action classification with parameter extraction
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = ("写", "生成", "创建", "write", "create", "generate", "新建", "实现", "implement")
_READ_KEYWORDS = ("读", "打开", "查看", "read", "open", "view", "cat")
_LIST_KEYWORDS = ("列出", "目录", "list", "ls", "tree", "结构", "文件列表")
_SEARCH_KEYWORDS = ("搜索", "查找", "search", "find", "grep", "包含")
_DELETE_KEYWORDS = ("删除", "delete", "remove", "rm")
_TEST_KEYWORDS = ("测试", "运行测试", "test", "pytest")
_COPY_KEYWORDS = ("复制", "copy", "拷贝")
_MOVE_KEYWORDS = ("移动", "move", "重命名", "rename")

# Comma-separated list of common file extensions for path detection
_PATH_EXTENSIONS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".md", ".txt", ".csv", ".log",
    ".env", ".cfg", ".ini", ".sh", ".bat", ".ps1", ".c", ".cpp", ".h", ".hpp",
    ".java", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".r",
    ".sql", ".graphql", ".proto", ".dockerfile",
)

# Pattern: word.word or path/word.word
_PATH_RE = re.compile(
    r"([a-zA-Z0-9_\-./\\]+(?:\.[a-zA-Z0-9]{1,10}))"
)

_EXTRACTION_SYSTEM_PROMPT = """You are a workspace file-operation parameter extractor.
Given a user request in Chinese or English, extract structured parameters.
Return ONLY valid JSON. Do NOT include markdown fences, explanations, or other text.

JSON schema for each action:
- workspace.write: {"rel_path": "relative/file/path.py", "content": "complete file content...", "overwrite": false}
- workspace.read:   {"rel_path": "relative/file/path.py"}
- workspace.list:   {"rel_path": ""}
- workspace.delete: {"rel_path": "relative/file/path.py"}
- workspace.move:   {"source_path": "old/path.py", "target_path": "new/path.py"}
- workspace.copy:   {"source_path": "src/path.py", "target_path": "dst/path.py"}
- workspace.search: {"query": "search text or pattern", "rel_path": ""}
- workspace.test:   {"rel_path": "test/path.py"}
- run.create:       {"action": "run.create"}

Rules:
- rel_path must be a relative workspace path (no absolute paths, no .. escapes)
- Preserve the full relative path the user specifies (e.g., "src/components/Button.vue"); if no path given, generate a reasonable filename
- For workspace.write: generate COMPLETE, working file content based on the request
- For workspace.write: if the user asks for code, write the code; if text, write text
- For workspace.write: NEVER leave content empty; always generate appropriate content
- For search: extract the search term from the prompt; leave rel_path empty unless a directory is specified
- For test: use the exact test file path mentioned
"""




def _extract_dir_from_chinese_prompt(prompt: str, filename: str) -> str | None:
    """If prompt has '在 dir 下' pattern, extract the directory."""
    dir_match = re.search(
        r"(?:\u5728|\u4ece)\s*([a-zA-Z0-9_\-./\\\\]+)\s*(?:\u4e0b|\u91cc|\u4e2d|\u76ee\u5f55)",
        prompt
    )
    if dir_match:
        return dir_match.group(1).strip().strip("'\"").replace("\\", "/")
    return None

def _extract_path_from_prompt(prompt: str) -> str | None:
    """Heuristically extract a file path from a user prompt (no LLM).

    Handles both bare paths and Chinese patterns like "在 xxx 下创建 yyy.ext".
    """
    # Try to find a full path+filename via regex first
    for m in _PATH_RE.finditer(prompt):
        candidate = m.group(1).strip().strip("'\"")
        candidate = candidate.replace("\\", "/")
        if candidate and not candidate.startswith(".."):
            if any(candidate.endswith(ext) for ext in _PATH_EXTENSIONS):
                # Check if a directory prefix exists in Chinese patterns
                dir_prefix = _extract_dir_from_chinese_prompt(prompt, candidate)
                if dir_prefix:
                    return dir_prefix + "/" + candidate
                return candidate
            if "/" in candidate:
                return candidate

    # Fallback: extract directory from Chinese pattern + generate filename
    dir_match = re.search(
        r"(?:\u5728|\u4ece)\s*([a-zA-Z0-9_\-./\\\\]+)\s*(?:\u4e0b|\u91cc|\u4e2d|\u76ee\u5f55)",
        prompt
    )
    if dir_match:
        dir_path = dir_match.group(1).strip().strip("'\"").replace("\\", "/")
        # Also look for a filename in the prompt
        for m in _PATH_RE.finditer(prompt):
            fname = m.group(1).strip().strip("'\"").replace("\\", "/")
            if fname and not fname.startswith("..") and any(fname.endswith(ext) for ext in _PATH_EXTENSIONS):
                return dir_path + "/" + fname
        return dir_path

    return None


def _safe_json_parse(text: str) -> dict[str, Any] | None:
    """Parse JSON with automatic repair for truncated/incomplete LLM output."""

    text = text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fixed = text.rstrip()
    in_string = False
    i = 0
    while i < len(fixed):
        ch = fixed[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
        i += 1

    if in_string:
        fixed = fixed + '"'

    open_braces = fixed.count('{') - fixed.count('}')
    open_brackets = fixed.count('[') - fixed.count(']')

    import re as _re
    fixed = _re.sub(r",\s*$", "", fixed.rstrip())

    fixed += "}" * max(0, open_braces)
    fixed += "]" * max(0, open_brackets)

    try:
        result = json.loads(fixed)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    return None

def _extract_workspace_params_via_llm(
    prompt: str,
    context: str | None,
    detected_action: str,
) -> "tuple[str, dict[str, Any], str]":
    """Use a single lightweight LLM call to extract structured workspace parameters."""
    try:
        full_prompt = f"Detected action: {detected_action}\nUser request: {prompt}"
        if context:
            full_prompt = f"Project context: {context}\n\n{full_prompt}"

        result = call_llm_sync(
            prompt=full_prompt,
            context=None,
            system_prompt=_EXTRACTION_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=ROUTER_LLM_EXTRACTION_MAX_TOKENS,
        )
        if result.ok and result.output:
            output = result.output.strip()
            # Strip markdown fences
            output = re.sub(r"^`(?:json)?\s*\n?", "", output)
            output = re.sub(r"\n?`\s*$", "", output)
            params = _safe_json_parse(output)
            if isinstance(params, dict):
                # The LLM may override the action
                action = params.pop("action", detected_action)
                params.setdefault("prompt", prompt)
                if context:
                    params.setdefault("context", context)
                logger.debug(
                    "LLM extracted workspace params: action=%s keys=%s",
                    action, list(params),
                )
                return action, params, f"LLM-extracted params for {action}."
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("LLM workspace param extraction failed: %s", exc)

    # Fallback: try heuristic path extraction; if found, use workspace.write
    heuristic_path = _extract_path_from_prompt(prompt)
    if heuristic_path and detected_action.startswith("workspace."):
        logger.info("LLM extraction failed, but heuristic path found: %s", heuristic_path)
        return detected_action, {"rel_path": heuristic_path, "prompt": prompt, "context": context}, "Heuristic fallback with path."
    logger.info("Falling back to run.create for prompt: %.120s", prompt)
    return "run.create", {"prompt": prompt, "context": context}, "Fallback to run.create."


def _classify_coding_action(prompt: str, context: str | None) -> "tuple[str, dict[str, Any], str]":
    """Classify coding prompt and extract structured parameters.

    Priority order (most specific/actionable first):
    1. WRITE / DELETE / MOVE / COPY (complex, need LLM extraction)
    2. TEST / SEARCH (moderate complexity)
    3. READ (heuristic path extraction, fallback to LLM)
    4. LIST (direct execution, lowest priority)
    """
    text = str(prompt or "").lower()
    raw_input: dict[str, Any] = {"prompt": prompt, "context": context}

    # ---- Tier 1: Complex actions (LLM extraction) ----
    if any(kw.lower() in text for kw in _WRITE_KEYWORDS):
        return _extract_workspace_params_via_llm(prompt, context, "workspace.write")
    if any(kw.lower() in text for kw in _DELETE_KEYWORDS):
        return _extract_workspace_params_via_llm(prompt, context, "workspace.delete")
    if any(kw.lower() in text for kw in _MOVE_KEYWORDS):
        return _extract_workspace_params_via_llm(prompt, context, "workspace.move")
    if any(kw.lower() in text for kw in _COPY_KEYWORDS):
        return _extract_workspace_params_via_llm(prompt, context, "workspace.copy")

    # ---- Tier 2: Moderate actions (LLM extraction) ----
    if any(kw.lower() in text for kw in _TEST_KEYWORDS):
        return _extract_workspace_params_via_llm(prompt, context, "workspace.test")
    if any(kw.lower() in text for kw in _SEARCH_KEYWORDS):
        return _extract_workspace_params_via_llm(prompt, context, "workspace.search")

    # ---- Tier 3: Read (heuristic first, LLM fallback) ----
    if any(kw.lower() in text for kw in _READ_KEYWORDS):
        path = _extract_path_from_prompt(prompt)
        if path:
            return "workspace.read", {"rel_path": path, **raw_input}, f"Heuristic read: {path}"
        return _extract_workspace_params_via_llm(prompt, context, "workspace.read")

    # ---- Tier 4: List (direct, lowest priority to avoid false matches) ----
    if any(kw.lower() in text for kw in _LIST_KEYWORDS):
        return "workspace.list", raw_input, "List intent via keywords."

    # Default: run.create with raw prompt
    return "run.create", raw_input, "Defaulting to run.create for coding intent."


# ---------------------------------------------------------------------------
# Routing Decision (immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Output of Layer 1: tells Layer 2 what to do."""
    intent: str
    action_name: str
    action_input: dict[str, Any]
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_chat(cls, prompt: str, context: str | None = None) -> "RoutingDecision":
        return cls(
            intent=INTENT_CHAT,
            action_name="chat.reply",
            action_input={"prompt": prompt, "context": context},
            reason="Chat intent detected.",
            metadata={"intent": INTENT_CHAT},
        )

    @classmethod
    def for_coding(cls, prompt: str, action_name: str, action_input: dict[str, Any],
                   reason: str = "", metadata: dict[str, Any] | None = None) -> "RoutingDecision":
        return cls(
            intent=INTENT_CODING,
            action_name=action_name,
            action_input=action_input,
            reason=reason or "Coding intent detected.",
            metadata=metadata or {},
        )

    @classmethod
    def for_unknown(cls, prompt: str) -> "RoutingDecision":
        return cls(
            intent=INTENT_UNKNOWN,
            action_name="final.answer",
            action_input={"content": "本机不太确定你想做什么呢...能再说清楚一点吗？"},
            reason="Unknown intent, falling back.",
            metadata={"intent": INTENT_UNKNOWN},
        )


# ---------------------------------------------------------------------------
# Layer 1 Router
# ---------------------------------------------------------------------------

class RoutingGuard:
    """Layer 1: Intent detection and routing.

    Pure classification layer. Takes user input, detects intent,
    and returns a RoutingDecision. No side effects, no LLM, no tool planning.
    """

    def route(self, prompt: str, context: str | None = None,
              file_context: dict[str, Any] | None = None) -> RoutingDecision:
        intent = detect_intent(prompt)
        if intent == INTENT_CHAT:
            return RoutingDecision.for_chat(prompt, context)
        if intent == INTENT_CODING:
            return self._route_coding(prompt, context)
        return RoutingDecision.for_unknown(prompt)

    def _route_coding(self, prompt: str, context: str | None) -> RoutingDecision:
        """Route coding requests using keyword heuristics (no LLM)."""
        run_action = detect_run_action(prompt)
        # Run control actions (inspect, retry, rerun, cancel)
        if run_action and run_action != "create":
            target_run_id = extract_run_reference(prompt)
            action_name = {
                "retry": "run.retry",
                "rerun": "run.rerun",
                "cancel": "run.cancel",
                "inspect": "run.inspect",
            }.get(run_action, "run.inspect")
            return RoutingDecision.for_coding(
                prompt=prompt,
                action_name=action_name,
                action_input={"run_id": target_run_id},
                reason=f"Run control: {run_action}",
                metadata={"run_action": run_action, "target_run_id": target_run_id},
            )

        # New coding request: classify via simple keywords
        action_name, action_input, reason = _classify_coding_action(prompt, context)
        return RoutingDecision.for_coding(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
            reason=reason,
            metadata={"coding_action": action_name},
        )


# Singleton instance
routing_guard = RoutingGuard()
