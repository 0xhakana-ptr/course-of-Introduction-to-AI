from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from ..state.runtime_models import build_runtime_turn_from_state, coerce_runtime_steps


GraphResultT = TypeVar("GraphResultT", bound="WorkflowGraphResult")
SUMMARY_RESULT_FIELDS = (
    "ok",
    "output",
    "summary_text",
    "summary_source",
    "llm_error",
)
AGENT_RESULT_FIELDS = (
    "ok",
    "output",
    "turn_id",
    "intent",
    "error",
    "run_id",
    "run_status",
    "run_action",
    "ui_status",
    "workflow_trace",
    "runtime_steps",
    "runtime_turn",
)
REPAIR_RESULT_FIELDS = (
    "ok",
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
)


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


def invoke_graph_with_result(
    graph: object,
    *,
    initial_state: Mapping[str, object],
    on_success: Callable[[Mapping[str, object]], GraphResultT],
    on_error: Callable[[Exception, dict[str, object]], GraphResultT],
) -> GraphResultT:
    normalized_state = dict(initial_state)

    try:
        result = graph.invoke(normalized_state, config={"recursion_limit": 200})
    except Exception as exc:
        return on_error(exc, normalized_state)

    if not isinstance(result, Mapping):
        return on_error(
            TypeError("workflow graph returned non-mapping state"),
            normalized_state,
        )

    return on_success(result)


@dataclass(slots=True)
class WorkflowSummaryResult(WorkflowGraphResult):
    summary_text: str = ""
    summary_source: str = "fallback"
    llm_error: str | None = None

    @classmethod
    def _from_normalized_state(
        cls,
        state: Mapping[str, object],
        *,
        ok: bool,
    ) -> "WorkflowSummaryResult":
        llm_error = state.get("llm_error")
        return cls(
            ok=ok,
            output=_coerce_mapping_str(state, "output"),
            summary_text=_coerce_mapping_str(state, "summary_text"),
            summary_source=_coerce_mapping_str(state, "summary_source", default="fallback"),
            llm_error=str(llm_error) if llm_error is not None else None,
            state=dict(state),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkflowSummaryResult":
        return cls._from_normalized_state(state, ok=True)

    @classmethod
    def from_error(
        cls,
        exc: Exception,
        state: Mapping[str, object],
    ) -> "WorkflowSummaryResult":
        message = f"总结工作流执行失败：{exc}"
        return cls(
            ok=False,
            output=message,
            summary_text="",
            summary_source="fallback",
            llm_error=str(exc),
            state=dict(state),
        )

    @classmethod
    def from_value(cls, value: object) -> "WorkflowSummaryResult":
        if isinstance(value, cls):
            return value

        state = _extract_state_from_value(value, field_names=SUMMARY_RESULT_FIELDS)
        return cls._from_normalized_state(
            state,
            ok=_resolve_result_ok(state, fallback=True),
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


def _coerce_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_mapping_text(state: Mapping[str, object], key: str) -> str | None:
    return _coerce_optional_text(state.get(key))


def _coerce_mapping_str(
    state: Mapping[str, object],
    key: str,
    *,
    default: str = "",
) -> str:
    return str(state.get(key) or default)


def _coerce_mapping_first_str(
    state: Mapping[str, object],
    *keys: str,
    default: str = "",
) -> str:
    for key in keys:
        value = state.get(key)
        if value:
            return str(value)
    return default


def _resolve_result_ok(
    state: Mapping[str, object],
    *,
    fallback: bool,
) -> bool:
    ok_value = state.get("ok")
    return fallback if ok_value is None else bool(ok_value)


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
    turn_id: str | None = None
    intent: str = "unknown"
    error: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    run_action: str | None = None
    ui_status: str | None = None
    workflow_trace: list[dict[str, object]] = field(default_factory=list)
    runtime_steps: list[dict[str, object]] = field(default_factory=list)
    runtime_turn: dict[str, object] = field(default_factory=dict)

    @classmethod
    def _from_normalized_state(
        cls,
        state: Mapping[str, object],
        *,
        ok: bool,
        default_intent: str = "unknown",
    ) -> "WorkflowAgentResult":
        workflow_trace = state.get("workflow_trace")
        normalized_trace = [
            dict(item)
            for item in workflow_trace
            if isinstance(workflow_trace, list) and isinstance(item, Mapping)
        ] if isinstance(workflow_trace, list) else []
        runtime_turn = build_runtime_turn_from_state(
            state,
            ok=ok,
            workflow_trace=normalized_trace,
        ).as_dict()
        runtime_steps = coerce_runtime_steps(state.get("runtime_steps")) or list(
            runtime_turn.get("steps", [])
        )
        return cls(
            ok=ok,
            output=_coerce_mapping_str(state, "output"),
            turn_id=_coerce_mapping_text(state, "turn_id"),
            intent=_coerce_mapping_text(state, "intent") or default_intent,
            error=_coerce_mapping_text(state, "error"),
            run_id=_coerce_mapping_text(state, "run_id"),
            run_status=_coerce_mapping_text(state, "run_status"),
            run_action=_coerce_mapping_text(state, "run_action"),
            ui_status=_coerce_mapping_text(state, "ui_status"),
            workflow_trace=normalized_trace,
            runtime_steps=runtime_steps,
            runtime_turn=runtime_turn,
            state=dict(state),
        )

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, object],
        *,
        default_intent: str = "unknown",
    ) -> "WorkflowAgentResult":
        error = _coerce_mapping_text(state, "error")
        return cls._from_normalized_state(
            state,
            ok=error is None,
            default_intent=default_intent,
        )

    @classmethod
    def from_error(
        cls,
        exc: Exception,
        state: Mapping[str, object],
        *,
        default_intent: str = "unknown",
    ) -> "WorkflowAgentResult":
        return cls(
            ok=False,
            output=f"Agent 工作流执行失败：{exc}",
            turn_id=_coerce_mapping_text(state, "turn_id"),
            intent=default_intent,
            error=str(exc),
            run_id=None,
            run_status=None,
            run_action=None,
            ui_status=None,
            workflow_trace=[],
            runtime_steps=[],
            runtime_turn=build_runtime_turn_from_state(
                state,
                ok=False,
                workflow_trace=[],
            ).as_dict(),
            state=dict(state),
        )

    @classmethod
    def from_value(
        cls,
        value: object,
        *,
        default_intent: str = "unknown",
    ) -> "WorkflowAgentResult":
        if isinstance(value, cls):
            return value

        state = _extract_state_from_value(value, field_names=AGENT_RESULT_FIELDS)
        error = _coerce_mapping_text(state, "error")
        return cls._from_normalized_state(
            state,
            ok=_resolve_result_ok(state, fallback=error is None),
            default_intent=default_intent,
        )

    def as_dict(self) -> dict[str, object]:
        payload = super(WorkflowAgentResult, self).as_dict()
        payload.update(
            {
                "turn_id": self.turn_id,
                "intent": self.intent,
                "error": self.error,
                "run_id": self.run_id,
                "run_status": self.run_status,
                "run_action": self.run_action,
                "ui_status": self.ui_status,
                "workflow_trace": list(self.workflow_trace),
                "runtime_steps": list(self.runtime_steps),
                "runtime_turn": dict(self.runtime_turn),
            }
        )
        return payload

    def resolved_intent(
        self,
        *,
        valid_intents: Collection[str] | None = None,
        default_intent: str = "unknown",
    ) -> str:
        intent = self.intent.strip()
        if not intent:
            return default_intent
        if valid_intents is not None and intent not in valid_intents:
            return default_intent
        return intent

    def resolved_output(
        self,
        *,
        intent: str | None = None,
        fallback_output_builder: Callable[[str], str] | None = None,
    ) -> str:
        output = self.output.strip()
        if output:
            return output
        if fallback_output_builder is None:
            return ""
        return fallback_output_builder(intent or self.intent)

    def run_payload(self) -> tuple[str | None, str | None]:
        return self.run_id, self.run_status

    def run_action_name(self) -> str | None:
        return self.run_action


def _coerce_attr_text(value: object, attr_name: str) -> str | None:
    return _coerce_optional_text(getattr(value, attr_name, None))


def _coerce_attr_or_mapping_text(
    value: object,
    attr_name: str,
    state: Mapping[str, object],
    state_key: str,
) -> str | None:
    return _coerce_attr_text(value, attr_name) or _coerce_mapping_text(state, state_key)


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
    def _from_normalized_state(
        cls,
        state: Mapping[str, object],
        *,
        ok: bool,
        reason_override: str | None = None,
    ) -> "WorkflowRepairResult":
        feedback_message = state.get("feedback_message")
        reason = reason_override or _coerce_mapping_first_str(
            state,
            "decision_reason",
            "reason",
            default="当前运行不满足自动修复条件。",
        )
        feedback_text = _coerce_attr_or_mapping_text(
            feedback_message,
            "content",
            state,
            "feedback_text",
        )
        return cls(
            ok=ok,
            output=feedback_text or reason,
            should_attempt_repair=bool(state.get("should_attempt_repair", False)),
            reason=reason,
            analysis_note=_coerce_mapping_first_str(
                state,
                "analysis_note",
                "failure_summary",
            ),
            analysis_source=_coerce_mapping_str(state, "analysis_source", default="fallback"),
            failure_summary=_coerce_mapping_str(state, "failure_summary"),
            repaired_result=state.get("repaired_result"),
            feedback_message=feedback_message,
            retry_guidance=state.get("retry_guidance"),
            state=dict(state),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkflowRepairResult":
        return cls._from_normalized_state(state, ok=True)

    @classmethod
    def from_error(
        cls,
        exc: Exception,
        state: Mapping[str, object],
    ) -> "WorkflowRepairResult":
        return cls._from_normalized_state(
            state,
            ok=False,
            reason_override=f"自动修复工作流执行失败：{exc}",
        )

    @classmethod
    def from_value(cls, value: object) -> "WorkflowRepairResult":
        if isinstance(value, cls):
            return value

        state = _extract_state_from_value(value, field_names=REPAIR_RESULT_FIELDS)
        return cls._from_normalized_state(
            state,
            ok=_resolve_result_ok(state, fallback=True),
        )

    @property
    def feedback_text(self) -> str | None:
        return _coerce_attr_or_mapping_text(
            self.feedback_message,
            "content",
            self.state,
            "feedback_text",
        )

    @property
    def feedback_node_name(self) -> str | None:
        return _coerce_attr_or_mapping_text(
            self.feedback_message,
            "node_name",
            self.state,
            "feedback_node_name",
        )

    @property
    def retry_next_action(self) -> str | None:
        return _coerce_attr_or_mapping_text(
            self.retry_guidance,
            "next_action",
            self.state,
            "retry_next_action",
        )

    @property
    def retry_node_name(self) -> str | None:
        return _coerce_attr_or_mapping_text(
            self.retry_guidance,
            "node_name",
            self.state,
            "retry_node_name",
        )

    def analysis_log_payload(self) -> tuple[str | None, str | None]:
        analysis_note = self.analysis_note.strip() or None
        analysis_source = self.analysis_source.strip() or None
        return analysis_note, analysis_source

    def feedback_payload(
        self,
        *,
        default_node_name: str,
    ) -> tuple[str, str] | None:
        feedback_text = self.feedback_text
        if feedback_text is None:
            return None
        return (
            self.feedback_node_name or default_node_name,
            feedback_text,
        )

    def repaired_result_or(self, fallback: object) -> Any:
        return self.repaired_result or fallback

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
