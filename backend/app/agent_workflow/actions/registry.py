from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import AgentActionDefinition, AgentActionDescriptor, AgentActionResult


class AgentActionRegistry:
    def __init__(self, definitions: Iterable[AgentActionDefinition] = ()) -> None:
        self._definitions: dict[str, AgentActionDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: AgentActionDefinition) -> None:
        self._definitions[definition.descriptor.name] = definition

    def get(self, action_name: str) -> AgentActionDefinition | None:
        return self._definitions.get(str(action_name or "").strip())

    def require(self, action_name: str) -> AgentActionDefinition:
        definition = self.get(action_name)
        if definition is None:
            raise KeyError(f"agent action is not registered: {action_name}")
        return definition

    def list_descriptors(self) -> list[dict[str, object]]:
        return [
            definition.descriptor.as_dict()
            for definition in self._definitions.values()
        ]

    def execute(
        self,
        action_name: str,
        action_input: Mapping[str, object] | None = None,
    ) -> AgentActionResult:
        normalized_action_name = str(action_name or "").strip()
        definition = self.get(normalized_action_name)
        if definition is None:
            return AgentActionResult(
                action_name=normalized_action_name,
                ok=False,
                summary=f"Agent action `{normalized_action_name}` is not registered.",
                error=f"unregistered agent action: {normalized_action_name}",
            )

        try:
            return definition.execute(dict(action_input or {}))
        except Exception as exc:
            return AgentActionResult(
                action_name=normalized_action_name,
                ok=False,
                summary=f"Agent action `{normalized_action_name}` failed: {exc}",
                error=str(exc),
            )
