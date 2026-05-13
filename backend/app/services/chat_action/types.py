from collections.abc import Callable
from dataclasses import dataclass, replace

from ...schemas import INTENT_TYPE
from ...agent_workflow.contracts.workflow_results import WorkflowAgentResult
from ...agent_workflow.output.text import sanitize_user_visible_run_output


VALID_CHAT_SERVICE_INTENTS: set[str] = {"chat", "coding", "unknown"}


def _normalize_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class ChatServiceResult:
    intent: INTENT_TYPE
    ok: bool
    output: str
    error: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    run_action: str | None = None
    runtime_mode: str | None = None
    route_scope: str | None = None
    runtime_warning: str | None = None
    content_type: str = "markdown"
    render_mode: str = "rich_text"

    def with_updates(self, **updates: object) -> "ChatServiceResult":
        return replace(self, **updates)

    def is_intent(self, intent: INTENT_TYPE) -> bool:
        return self.intent == intent

    def attach_session(self, session_id: str | None) -> "ChatServiceResult":
        if session_id is None:
            return self
        return self.with_updates(session_id=session_id)

    def with_user_visible_output(self) -> "ChatServiceResult":
        if not self.is_intent("coding"):
            return self
        return self.with_updates(output=sanitize_user_visible_run_output(self.output))

    @classmethod
    def from_agent_result(
        cls,
        result: object,
        *,
        intent_hint: INTENT_TYPE | None = None,
        fallback_output_builder: Callable[[INTENT_TYPE], str] | None = None,
    ) -> "ChatServiceResult":
        normalized_result = WorkflowAgentResult.from_value(
            result,
            default_intent=intent_hint or "unknown",
        )
        resolved_intent = normalized_result.resolved_intent(
            valid_intents=VALID_CHAT_SERVICE_INTENTS,
            default_intent="unknown",
        )
        output = normalized_result.resolved_output(
            intent=resolved_intent,
            fallback_output_builder=fallback_output_builder,
        )
        run_id, _ = normalized_result.run_payload()

        return cls(
            intent=resolved_intent,
            ok=normalized_result.ok,
            output=sanitize_user_visible_run_output(output) if resolved_intent == "coding" else output,
            error=_normalize_optional_str(normalized_result.error),
            run_id=_normalize_optional_str(run_id),
            run_action=_normalize_optional_str(normalized_result.run_action_name()),
        )
