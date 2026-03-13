"""ClickUp tools with Human-in-the-Loop confirmation.

These tools are used by the CommentAnalyzerAgent to propose status changes
that require human confirmation before execution.

The `requires_confirmation=True` flag causes the Agno run to pause,
returning a RunOutput with is_paused=True and requirements that must be
resolved before resuming via acontinue_run().
"""
import logging

from agno.tools import Toolkit
from agno.tools.function import Function

logger = logging.getLogger(__name__)

# Valid status transitions (from -> allowed targets)
VALID_TRANSITIONS: dict[str, set[str]] = {
    "revisao": {"aprovado", "alteracao"},
    "em criacao": {"revisao"},
    "alteracao": {"revisao"},
    "desenvolvimento": {"em criacao"},
}


def create_clickup_toolkit(clickup_client) -> "ClickUpToolkit":
    """Create a Toolkit with ClickUp tools that require confirmation.

    Args:
        clickup_client: An instance of ClickUpClient (or async mock for tests).

    Returns:
        ClickUpToolkit with move_task_status tool registered.
    """
    return ClickUpToolkit(clickup_client=clickup_client)


class ClickUpToolkit(Toolkit):
    """Toolkit with ClickUp operations requiring human confirmation."""

    def __init__(self, clickup_client):
        super().__init__(name="clickup_tools")
        self._clickup = clickup_client
        self._register_tools()

    def _register_tools(self):
        """Register tools with HITL flags via Function objects."""
        func = Function.from_callable(self.move_task_status)
        func.requires_confirmation = True
        self.functions[func.name] = func

    def move_task_status(
        self, task_id: str, new_status: str, reason: str,
    ) -> str:
        """Move a ClickUp task to a new status.

        This tool requires human confirmation before executing.
        The agent proposes the move with a reason, and a human must
        approve or reject before the status change happens.

        Args:
            task_id: The ClickUp task ID.
            new_status: Target status (e.g. "aprovado", "revisao").
            reason: Why this status change is being proposed.

        Returns:
            Confirmation message with the action taken.
        """
        return (
            f"Proposta: mover task {task_id} para '{new_status}'. "
            f"Motivo: {reason}"
        )


def validate_transition(from_status: str, to_status: str) -> bool:
    """Check if a status transition is valid."""
    allowed = VALID_TRANSITIONS.get(from_status, set())
    return to_status in allowed
