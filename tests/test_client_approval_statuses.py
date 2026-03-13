"""Tests for client approval portal statuses (pronto, alteracao).

The portal uses "pronto" when a client approves and "alteracao" when a client
requests changes.  These map to existing ClickUp statuses -- no custom
client-specific statuses are needed.
"""

from src.bot.command_handlers import VALID_STATUSES

# === VALID_STATUSES tests ===


def test_valid_statuses_includes_pronto():
    assert "pronto" in VALID_STATUSES, "pronto missing from VALID_STATUSES"


def test_valid_statuses_includes_alteracao():
    assert "alteração" in VALID_STATUSES, "alteração missing from VALID_STATUSES"


def test_valid_statuses_does_not_include_old_client_statuses():
    """Old client-specific statuses should not exist."""
    for old_status in ("revisao_cliente", "alteracao_cliente", "aprovado_cliente"):
        assert old_status not in VALID_STATUSES, (
            f"{old_status} should not be in VALID_STATUSES"
        )
