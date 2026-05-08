from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkflowGraphResult:
    ok: bool = True
    output: str = ""
    state: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "output": self.output,
            "state": dict(self.state),
        }


@dataclass(slots=True)
class WorkflowSummaryResult(WorkflowGraphResult):
    summary_text: str = ""
    summary_source: str = "fallback"
    llm_error: str | None = None

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkflowSummaryResult":
        llm_error = state.get("llm_error")
        return cls(
            ok=True,
            output=str(state.get("output") or ""),
            summary_text=str(state.get("summary_text") or ""),
            summary_source=str(state.get("summary_source") or "fallback"),
            llm_error=str(llm_error) if llm_error is not None else None,
            state=dict(state),
        )

    def as_dict(self) -> dict[str, object]:
        payload = super(WorkflowSummaryResult, self).as_dict()
        payload.update(
            {
                "summary_text": self.summary_text,
                "summary_source": self.summary_source,
                "llm_error": self.llm_error,
            }
        )
        return payload


def _coerce_mapping_text(state: Mapping[str, object], key: str) -> str | None:
    value = state.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_state_from_value(
    value: object,
    *,
    field_names: tuple[str, ...],
) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)

    state: dict[str, object] = {}
    for field_name in field_names:
        field_value = getattr(value, field_name, None)
        if field_value is not None:
            state[field_name] = field_value
    return state


@dataclass(slots=True)
class WorkflowAgentResult(WorkflowGraphResult):
    intent: str = "unknown"
    error: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    ui_status: str | None = None

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, object],
        *,
        default_intent: str = "unknown",
    ) -> "WorkflowAgentResult":
        error = _coerce_mapping_text(state, "error")
        return cls(
            ok=error is None,
            output=str(state.get("output") or ""),
            intent=_coerce_mapping_text(state, "intent") or default_intent,
            error=error,
            run_id=_coerce_mapping_text(state, "run_id"),
            run_status=_coerce_mapping_text(state, "run_status"),
            ui_status=_coerce_mapping_text(state, "ui_status"),
            state=dict(state),
        )

    def as_dict(self) -> dict[str, object]:
        payload = super(WorkflowAgentResult, self).as_dict()
        payload.update(
            {
                "intent": self.intent,
                "error": self.error,
                "run_id": self.run_id,
                "run_status": self.run_status,
                "ui_status": self.ui_status,
            }
        )
        return payload


def _coerce_attr_text(value: object, attr_name: str) -> str | None:
    attr_value = getattr(value, attr_name, None)
    if attr_value is None:
        return None
    text = str(attr_value).strip()
    return text or None


@dataclass(slots=True)
class WorkflowRepairResult(WorkflowGraphResult):
    should_attempt_repair: bool = False
    reason: str = "当前运行不满足自动修复条件。"
    analysis_note: str = ""
    analysis_source: str = "fallback"
    failure_summary: str = ""
    repaired_result: Any | None = None
    feedback_message: Any | None = None
    retry_guidance: Any | None = None

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkflowRepairResult":
        reason = str(
            state.get("decision_reason")
            or state.get("reason")
            or "当前运行不满足自动修复条件。"
        )
        feedback_message = state.get("feedback_message")
        feedback_text = _coerce_attr_text(feedback_message, "content") or _coerce_mapping_text(
            state,
            "feedback_text",
        )
        return cls(
            ok=True,
            output=feedback_text or reason,
            should_attempt_repair=bool(state.get("should_attempt_repair", False)),
            reason=reason,
            analysis_note=str(state.get("analysis_note") or state.get("failure_summary") or ""),
            analysis_source=str(state.get("analysis_source") or "fallback"),
            failure_summary=str(state.get("failure_summary") or ""),
            repaired_result=state.get("repaired_result"),
            feedback_message=feedback_message,
            retry_guidance=state.get("retry_guidance"),
            state=dict(state),
        )

    @classmethod
    def from_value(cls, value: object) -> "WorkflowRepairResult":
        if isinstance(value, cls):
            return value

        return cls.from_state(
            _extract_state_from_value(
                value,
                field_names=(
                    "should_attempt_repair",
                    "decision_reason",
                    "reason",
                    "analysis_note",
                    "analysis_source",
                    "failure_summary",
                    "repaired_result",
                    "feedback_message",
                    "feedback_text",
                    "feedback_node_name",
                    "retry_guidance",
                    "retry_next_action",
                    "retry_node_name",
                ),
            )
        )

    @property
    def feedback_text(self) -> str | None:
        return _coerce_attr_text(self.feedback_message, "content") or _coerce_mapping_text(
            self.state,
            "feedback_text",
        )

    @property
    def feedback_node_name(self) -> str | None:
        return _coerce_attr_text(self.feedback_message, "node_name") or _coerce_mapping_text(
            self.state,
            "feedback_node_name",
        )

    @property
    def retry_next_action(self) -> str | None:
        return _coerce_attr_text(self.retry_guidance, "next_action") or _coerce_mapping_text(
            self.state,
            "retry_next_action",
        )

    @property
    def retry_node_name(self) -> str | None:
        return _coerce_attr_text(self.retry_guidance, "node_name") or _coerce_mapping_text(
            self.state,
            "retry_node_name",
        )

    def as_dict(self) -> dict[str, object]:
        payload = super(WorkflowRepairResult, self).as_dict()
        payload.update(
            {
                "should_attempt_repair": self.should_attempt_repair,
                "reason": self.reason,
                "analysis_note": self.analysis_note,
                "analysis_source": self.analysis_source,
                "failure_summary": self.failure_summary,
                "repaired_result": self.repaired_result,
                "feedback_message": self.feedback_message,
                "feedback_text": self.feedback_text,
                "feedback_node_name": self.feedback_node_name,
                "retry_guidance": self.retry_guidance,
                "retry_next_action": self.retry_next_action,
                "retry_node_name": self.retry_node_name,
            }
        )
        return payload
