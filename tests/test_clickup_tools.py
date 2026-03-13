"""Tests for ClickUp tools with HITL confirmation (Phase 6.1)."""
from unittest.mock import AsyncMock

from src.agents.tools.clickup_tools import (
    ClickUpToolkit,
    create_clickup_toolkit,
    validate_transition,
)


class TestValidateTransition:
    def test_revisao_to_aprovado(self):
        assert validate_transition("revisao", "aprovado") is True

    def test_revisao_to_alteracao(self):
        assert validate_transition("revisao", "alteracao") is True

    def test_revisao_to_em_criacao_invalid(self):
        assert validate_transition("revisao", "em criacao") is False

    def test_em_criacao_to_revisao(self):
        assert validate_transition("em criacao", "revisao") is True

    def test_alteracao_to_revisao(self):
        assert validate_transition("alteracao", "revisao") is True

    def test_unknown_status(self):
        assert validate_transition("unknown", "revisao") is False

    def test_desenvolvimento_to_em_criacao(self):
        assert validate_transition("desenvolvimento", "em criacao") is True


class TestClickUpToolkit:
    def test_creates_toolkit(self):
        mock_client = AsyncMock()
        toolkit = create_clickup_toolkit(mock_client)
        assert isinstance(toolkit, ClickUpToolkit)

    def test_toolkit_has_functions(self):
        mock_client = AsyncMock()
        toolkit = ClickUpToolkit(clickup_client=mock_client)
        assert toolkit.name == "clickup_tools"
        # Toolkit should have registered functions
        func_names = [f.name for f in toolkit.functions.values()]
        assert "move_task_status" in func_names

    def test_move_task_status_returns_proposal(self):
        mock_client = AsyncMock()
        toolkit = ClickUpToolkit(clickup_client=mock_client)
        result = toolkit.move_task_status(
            task_id="t1",
            new_status="aprovado",
            reason="Reviewer approved",
        )
        assert "t1" in result
        assert "aprovado" in result
        assert "Reviewer approved" in result

    def test_move_task_status_requires_confirmation(self):
        """Tool should be registered with requires_confirmation=True."""
        mock_client = AsyncMock()
        toolkit = ClickUpToolkit(clickup_client=mock_client)
        # The function should be in the toolkit's functions dict
        func = toolkit.functions.get("move_task_status")
        assert func is not None
        assert func.requires_confirmation is True
