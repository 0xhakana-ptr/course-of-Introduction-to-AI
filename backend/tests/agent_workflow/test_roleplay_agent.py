"""Tests for the Layer 2 Roleplay Agent (roleplay_agent.py)."""

import pytest
from backend.app.agent_workflow.roleplay import (
    RoleplayAgentContext,
    RoleplayMood,
    RoleplayResponse,
    _parse_llm_json,
    _scenario_fallback,
    generate_roleplay_response,
    get_session_mood,
    reset_session_mood,
)


class TestRoleplayAgentContext:
    """Tests for RoleplayAgentContext -- the Layer 1 -> Layer 2 boundary."""

    def test_from_state_extracts_safe_fields_only(self):
        """Only sanitized fields cross the boundary; raw engineering state is discarded."""
        state = {
            "intent": "coding",
            "ui_status": "coding_executor_done",
            "action_name": "workspace.write",
            "action_result": {"ok": True},
            "output": "Successfully wrote file",
            "error": None,
            "step_count": 2,
            "node_name": "agent_loop_roleplay",
            # Engineering internals that MUST NOT leak
            "raw_error_ref": "artifact:raw-error:abc123",
            "workflow_trace": [{"node": "executor", "event": "ran"}],
            "file_context": {"last_created_file": "test.txt"},
            "full_code": "def foo(): pass",
        }
        ctx = RoleplayAgentContext.from_state(state)
        # Safe fields are copied
        assert ctx.intent == "coding"
        assert ctx.ui_status == "coding_executor_done"
        assert ctx.action_name == "workspace.write"
        assert ctx.action_ok is True
        assert ctx.output_summary == "Successfully wrote file"
        assert ctx.step_count == 2
        # Engineering fields are NOT exposed
        assert not hasattr(ctx, "raw_error_ref")
        assert not hasattr(ctx, "workflow_trace")
        assert not hasattr(ctx, "file_context")
        assert not hasattr(ctx, "full_code")

    def test_from_state_action_failed_extracts_error_summary(self):
        state = {
            "action_result": {"ok": False},
            "error": "File not found",
            "ui_status": "workspace_tool_failed",
        }
        ctx = RoleplayAgentContext.from_state(state)
        assert ctx.action_ok is False
        assert "File not found" in ctx.error_summary

    def test_from_state_truncates_long_output(self):
        state = {
            "action_result": {"ok": True},
            "output": "x" * 500,
        }
        ctx = RoleplayAgentContext.from_state(state)
        assert len(ctx.output_summary) <= 400

    def test_from_state_truncates_long_error(self):
        state = {
            "action_result": {"ok": False},
            "error": "x" * 300,
        }
        ctx = RoleplayAgentContext.from_state(state)
        assert len(ctx.error_summary) <= 200

    def test_scenario_success(self):
        ctx = RoleplayAgentContext(
            terminal_status="completed", action_ok=True, action_name="workspace.write"
        )
        assert ctx.scenario() == "success"

    def test_scenario_failure(self):
        ctx = RoleplayAgentContext(
            terminal_status="failed", action_ok=False, action_name="workspace.read"
        )
        assert ctx.scenario() == "failure"

    def test_scenario_chat(self):
        ctx = RoleplayAgentContext(intent="chat", action_name="chat.reply")
        assert ctx.scenario() == "chat"

    def test_scenario_coding(self):
        ctx = RoleplayAgentContext(intent="coding", ui_status="coding_executor_done")
        assert ctx.scenario() == "coding"

    def test_scenario_thinking(self):
        ctx = RoleplayAgentContext(intent="coding", ui_status="perceive thinking observe")
        assert ctx.scenario() == "thinking"

    def test_scenario_idle_default(self):
        ctx = RoleplayAgentContext(intent="unknown")
        assert ctx.scenario() == "idle"


class TestRoleplayMood:
    """Tests for the mood state machine."""

    def test_initial_mood_is_neutral(self):
        mood = RoleplayMood()
        assert mood.label == "neutral"

    def test_consecutive_successes_lead_to_happy(self):
        mood = RoleplayMood()
        mood.record_success()
        mood.record_success()
        assert mood.label == "neutral"
        mood.record_success()
        assert mood.label == "happy"

    def test_consecutive_failures_lead_to_frustrated(self):
        mood = RoleplayMood()
        mood.record_failure()
        assert mood.label == "tired"
        mood.record_failure()
        mood.record_failure()
        assert mood.label == "frustrated"

    def test_success_resets_failure_streak(self):
        mood = RoleplayMood()
        mood.record_failure()
        mood.record_failure()
        assert mood.label == "tired"
        mood.record_success()
        assert mood.label == "neutral"

    def test_idle_streak_leads_to_lonely(self):
        mood = RoleplayMood()
        for _ in range(5):
            mood.record_neutral()
        assert mood.label == "lonely"

    def test_modifier_text_returns_non_empty(self):
        mood = RoleplayMood()
        assert mood.modifier_text
        mood.record_success()
        mood.record_success()
        mood.record_success()
        assert mood.modifier_text  # happy modifier


class TestScenarioFallback:
    """Tests for the persona.md template fallback (LLM-free)."""

    def test_generates_valid_output_for_all_scenarios(self):
        """Verify fallback generates valid output for each scenario type."""
        # Map scenarios to context configurations
        scenario_configs = {
            "success": RoleplayAgentContext(intent="coding", terminal_status="completed", action_ok=True),
            "failure": RoleplayAgentContext(intent="coding", terminal_status="failed", action_ok=False),
            "chat": RoleplayAgentContext(intent="chat", action_name="chat.reply"),
            "coding": RoleplayAgentContext(intent="coding", ui_status="coding_executor_done"),
            "thinking": RoleplayAgentContext(intent="coding", ui_status="perceive thinking observe"),
            "idle": RoleplayAgentContext(intent="unknown"),
        }
        for scenario, ctx in scenario_configs.items():
            assert ctx.scenario() == scenario, f"Expected {scenario}, got {ctx.scenario()}"
            result = _scenario_fallback(ctx)
            assert result["chat_line"], f"No chat_line for {scenario}"
            assert result["expression"] in (
                "happy", "proud", "thinking", "focused", "worried",
                "sad", "neutral", "surprised", "blush",
            ), f"Bad expression for {scenario}: {result['expression']}"
            assert result["quip"], f"No quip for {scenario}"


class TestGenerateRoleplayResponse:
    """Integration-style tests for generate_roleplay_response."""

    def setup_method(self):
        reset_session_mood()

    def test_returns_roleplay_response_on_success(self):
        state = {
            "intent": "coding",
            "ui_status": "coding_executor_done",
            "action_name": "workspace.write",
            "action_result": {"ok": True},
            "output": "File written successfully",
            "step_count": 1,
            "node_name": "agent_loop_roleplay",
        }
        response = generate_roleplay_response(state)
        assert isinstance(response, RoleplayResponse)
        assert response.chat_line
        assert response.expression
        assert response.scenario in ("success", "coding")

    def test_returns_roleplay_response_on_failure(self):
        state = {
            "intent": "coding",
            "action_name": "workspace.write",
            "action_result": {"ok": False},
            "error": "Permission denied",
            "ui_status": "workspace_tool_failed",
        }
        response = generate_roleplay_response(state)
        assert response.chat_line
        assert response.scenario == "failure"
        assert response.mood_label != ""

    def test_chat_scenario_uses_output(self):
        state = {
            "intent": "chat",
            "action_name": "chat.reply",
            "action_result": {"ok": True},
            "output": "Hello, how can I help you today?",
        }
        response = generate_roleplay_response(state)
        assert response.chat_line

    def test_uses_llm_fallback_when_unconfigured(self):
        """When LLM is not configured, persona.md templates are used."""
        state = {
            "action_result": {"ok": True},
            "output": "test output",
        }
        response = generate_roleplay_response(state)
        assert not response.llm_used
        assert response.chat_line  # fallback works


class TestParseLLMJson:
    """Tests for the JSON parser used on LLM output."""

    def test_parses_clean_json(self):
        raw = '{"chat_line": "Hello!", "expression": "happy", "quip": "Hi~", "motion": "wave"}'
        result = _parse_llm_json(raw)
        assert result["chat_line"] == "Hello!"
        assert result["expression"] == "happy"
        assert result["quip"] == "Hi~"

    def test_parses_json_in_markdown_fence(self):
        raw = '```json\n{"chat_line": "Hi!", "expression": "neutral"}\n```'
        result = _parse_llm_json(raw)
        assert result["chat_line"] == "Hi!"

    def test_parses_json_with_surrounding_text(self):
        raw = 'Sure! Here is the response:\n{"chat_line": "OK~", "expression": "happy"}'
        result = _parse_llm_json(raw)
        assert result["chat_line"] == "OK~"

    def test_returns_empty_on_garbage(self):
        result = _parse_llm_json("not json at all")
        assert result == {}

    def test_truncates_long_chat_line(self):
        long_line = "A" * 500
        raw = f'{{"chat_line": "{long_line}", "expression": "neutral"}}'
        result = _parse_llm_json(raw)
        assert len(result["chat_line"]) <= 400
