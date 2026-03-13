"""Tests for A10: Report handler (time-per-status analytics)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.report_handler import (
    _format_report,
    generate_time_report,
)


class _FakeRow:
    """Simulates a SQLAlchemy Row object with named attributes."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestFormatReport:
    def test_no_data(self):
        result = _format_report([], [], 30)
        assert "Sem dados" in result

    def test_single_client_single_status(self):
        rows = [
            _FakeRow(
                from_status="revisao",
                client_name="client_delta",
                transitions=5,
                avg_seconds=7200,  # 2h
            ),
        ]
        result = _format_report(rows, [], 30)
        assert "ClientDelta" in result
        assert "revisao" in result
        assert "2.0h" in result
        assert "5 transicoes" in result

    def test_multiple_clients(self):
        rows = [
            _FakeRow(
                from_status="revisao", client_name="client_delta",
                transitions=3, avg_seconds=3600,
            ),
            _FakeRow(
                from_status="em criacao", client_name="client_alpha",
                transitions=10, avg_seconds=86400,  # 24h = 1d
            ),
        ]
        result = _format_report(rows, [], 30)
        assert "ClientDelta" in result
        assert "CLIENT_ALPHA" in result
        assert "1.0d" in result

    def test_empty_client_name(self):
        rows = [
            _FakeRow(
                from_status="revisao", client_name="",
                transitions=2, avg_seconds=1800,
            ),
        ]
        result = _format_report(rows, [], 30)
        assert "Sem cliente" in result

    def test_bottleneck_section(self):
        avg_rows = [
            _FakeRow(
                from_status="revisao", client_name="client_delta",
                transitions=1, avg_seconds=3600,
            ),
        ]
        bottleneck_rows = [
            _FakeRow(
                from_status="alteracao", task_id="t1",
                task_name="Post ClientDelta Mar",
                client_name="client_delta",
                seconds_in_status=172800,  # 2 days
            ),
        ]
        result = _format_report(avg_rows, bottleneck_rows, 30)
        assert "Gargalos" in result
        assert "Post ClientDelta Mar" in result
        assert "alteracao" in result

    def test_bottleneck_with_days_display(self):
        bottleneck_rows = [
            _FakeRow(
                from_status="revisao", task_id="t2",
                task_name="Post ClientAlpha",
                client_name="client_alpha",
                seconds_in_status=50 * 3600,  # 50h = 2.08 days
            ),
        ]
        result = _format_report([], bottleneck_rows, 7)
        assert "Gargalos" in result
        assert "Post ClientAlpha" in result
        assert "d" in result  # shows days

    def test_days_param_in_header(self):
        result = _format_report([], [], 7)
        assert "7 dias" in result

    def test_bottleneck_without_task_name(self):
        bottleneck_rows = [
            _FakeRow(
                from_status="revisao", task_id="xyz",
                task_name="",
                client_name="",
                seconds_in_status=180000,
            ),
        ]
        result = _format_report([], bottleneck_rows, 30)
        assert "xyz" in result


class TestGenerateTimeReport:
    @pytest.mark.asyncio
    async def test_returns_formatted_report(self):
        mock_session = AsyncMock()
        mock_result_avg = MagicMock()
        mock_result_avg.fetchall.return_value = [
            _FakeRow(
                from_status="revisao", client_name="client_delta",
                transitions=5, avg_seconds=7200,
            ),
        ]
        mock_result_bottleneck = MagicMock()
        mock_result_bottleneck.fetchall.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_avg, mock_result_bottleneck],
        )

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await generate_time_report(mock_factory, days=30)
        assert "ClientDelta" in result
        assert "revisao" in result

    @pytest.mark.asyncio
    async def test_returns_error_on_db_failure(self):
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("DB error"),
        )
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await generate_time_report(mock_factory)
        assert "Erro" in result


class TestRelatorioCommand:
    @pytest.mark.asyncio
    async def test_handle_relatorio_no_db(self):
        """Without session_factory, returns unavailable message."""
        from src.bot.command_handlers import CommandHandlers

        rules = MagicMock()
        rules.get_all_clients.return_value = {}
        rules.get_default_list_id.return_value = ""

        cmd = CommandHandlers(
            clickup_client=AsyncMock(),
            rules_engine=rules,
            allowed_user_ids=[123],
            session_factory=None,
        )
        update = MagicMock()
        update.effective_user.id = 123
        update.message = AsyncMock()

        ctx = MagicMock()
        ctx.args = []

        await cmd.handle_relatorio(update, ctx)
        update.message.reply_text.assert_awaited_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "indisponivel" in msg

    @pytest.mark.asyncio
    async def test_handle_relatorio_with_db(self):
        """With session_factory, generates report."""
        from src.bot.command_handlers import CommandHandlers

        rules = MagicMock()
        rules.get_all_clients.return_value = {}
        rules.get_default_list_id.return_value = ""

        cmd = CommandHandlers(
            clickup_client=AsyncMock(),
            rules_engine=rules,
            allowed_user_ids=[123],
            session_factory=MagicMock(),
        )
        update = MagicMock()
        update.effective_user.id = 123
        update.message = AsyncMock()

        ctx = MagicMock()
        ctx.args = ["7"]

        with patch(
            "src.bot.report_handler.generate_time_report",
            new_callable=AsyncMock,
            return_value="*Report*",
        ) as mock_gen:
            await cmd.handle_relatorio(update, ctx)
            mock_gen.assert_awaited_once()
            # Check days param was passed
            assert mock_gen.call_args[1]["days"] == 7

    @pytest.mark.asyncio
    async def test_handle_relatorio_unauthorized(self):
        """Unauthorized user gets no response."""
        from src.bot.command_handlers import CommandHandlers

        rules = MagicMock()
        rules.get_all_clients.return_value = {}
        rules.get_default_list_id.return_value = ""

        cmd = CommandHandlers(
            clickup_client=AsyncMock(),
            rules_engine=rules,
            allowed_user_ids=[123],
        )
        update = MagicMock()
        update.effective_user.id = 999  # not authorized
        update.message = AsyncMock()

        ctx = MagicMock()
        ctx.args = []

        await cmd.handle_relatorio(update, ctx)
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_relatorio_default_days(self):
        """Default is 30 days when no args."""
        from src.bot.command_handlers import CommandHandlers

        rules = MagicMock()
        rules.get_all_clients.return_value = {}
        rules.get_default_list_id.return_value = ""

        cmd = CommandHandlers(
            clickup_client=AsyncMock(),
            rules_engine=rules,
            allowed_user_ids=[123],
            session_factory=MagicMock(),
        )
        update = MagicMock()
        update.effective_user.id = 123
        update.message = AsyncMock()

        ctx = MagicMock()
        ctx.args = []

        with patch(
            "src.bot.report_handler.generate_time_report",
            new_callable=AsyncMock,
            return_value="report",
        ) as mock_gen:
            await cmd.handle_relatorio(update, ctx)
            assert mock_gen.call_args[1]["days"] == 30
