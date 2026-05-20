"""RunPort implementation: wraps run_interface orchestration.

Implements the RunPort protocol defined in agent_workflow/actions/ports.py.
Delegates to existing run_interface functions, preserving all orchestration
logic (scheduling, events, retry, repair, cancellation).
"""
from __future__ import annotations

from .. import agent_workflow  # noqa: F401  ensure package loaded
from . import run_interface


class RunServiceImpl:
    """Concrete implementation of RunPort using existing run_interface."""

    def create(self, prompt: str, context: str | None = None) -> object:
        return run_interface.create_run(prompt, context)

    def inspect(self, run_id: str) -> object | None:
        return run_interface.get_run_snapshot(run_id)

    def retry(self, run_id: str) -> object:
        return run_interface.retry_run(run_id)

    def rerun(self, run_id: str) -> object:
        return run_interface.rerun_run(run_id)

    def cancel(self, run_id: str) -> object:
        return run_interface.cancel_run(run_id)
