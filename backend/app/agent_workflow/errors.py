"""Agent-level error hierarchy for diagnostics and API error handling.

New code should raise these instead of raw ValueError / RuntimeError
so the API layer can produce consistent error shapes.

Existing call sites continue to work — this is additive.
"""


class AgentError(Exception):
    """Base for all domain errors the agent workflow can surface."""

    def __init__(self, message: str, *, code: str = "agent_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class RoutingError(AgentError):
    """Layer 1 routing could not classify the user input."""

    def __init__(self, message: str, *, raw_prompt: str = "") -> None:
        super().__init__(message, code="routing_error")
        self.raw_prompt = raw_prompt


class WorkEngineError(AgentError):
    """Layer 3 work engine failed to complete the requested action."""

    def __init__(self, message: str, *, action_name: str = "", details: str = "") -> None:
        super().__init__(message, code="work_engine_error")
        self.action_name = action_name
        self.details = details


class CodegenError(AgentError):
    """Code generation or LLM repair failed."""

    def __init__(self, message: str, *, filename: str = "", raw_output: str = "") -> None:
        super().__init__(message, code="codegen_error")
        self.filename = filename
        self.raw_output = raw_output
