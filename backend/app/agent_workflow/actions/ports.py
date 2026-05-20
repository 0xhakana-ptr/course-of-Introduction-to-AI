"""Port interfaces for agent-to-service communication.

Defines abstract ports that the agent layer depends on.
Services layer implements these ports and injects them at startup.
This breaks the circular dependency: agent -> services -> agent.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable, TypedDict


class RunCreateResult(TypedDict, total=False):
    run_id: str
    status: str
    output: str
    summary: str


class RunInspectResult(TypedDict, total=False):
    run_id: str
    status: str
    summary: str
    terminal: bool


@runtime_checkable
class RunPort(Protocol):

    def create(self, prompt: str, context: str | None = None) -> object:
        ...

    def inspect(self, run_id: str) -> object | None:
        ...

    def retry(self, run_id: str) -> object:
        ...

    def rerun(self, run_id: str) -> object:
        ...

    def cancel(self, run_id: str) -> object:
        ...


_run_port: RunPort | None = None


def bind_run_port(port: RunPort) -> None:
    global _run_port
    _run_port = port


def get_run_port() -> RunPort:
    if _run_port is None:
        raise RuntimeError(
            'RunPort is not bound. Call bind_run_port() at application startup.'
        )
    return _run_port


def is_run_port_bound() -> bool:
    return _run_port is not None


def clear_run_port_for_tests() -> None:
    global _run_port
    _run_port = None
