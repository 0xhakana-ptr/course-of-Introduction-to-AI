"""Chat intent heuristics — compatibility re-export → agent_workflow.intent."""

from ...agent_workflow.intent import (  # noqa: F401
    classify_intent_with_llm,
    detect_intent,
    detect_run_action,
    extract_run_reference,
    has_command_reference,
    has_file_reference,
    has_workspace_path_reference,
)

__all__ = [
    "classify_intent_with_llm",
    "detect_intent",
    "detect_run_action",
    "extract_run_reference",
    "has_command_reference",
    "has_file_reference",
    "has_workspace_path_reference",
]
