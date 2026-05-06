from dataclasses import dataclass

from ...schemas import INTENT_TYPE


@dataclass(slots=True)
class ChatServiceResult:
    intent: INTENT_TYPE
    ok: bool
    output: str
    error: str | None = None
