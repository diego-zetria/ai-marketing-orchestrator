"""Tests for monthly report triggers: command handler, callback, and EventBridge dispatch."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.monthly_report_job import (
    _dispatch_to_eventbridge,
    handle_relatorio_mensal,
    monthly_report_callback,
)


class TestHandleRelatorioMensal:
    @pytest.mark.asyncio
    async def test_no_args_shows_usage(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = []

        await handle_relatorio_mensal(update, context)
        update.message.reply_text.assert_called_once()
        assert "Uso:" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_missing_config_returns_indisponivel(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["ClientDelta"]
        context.bot_data = {}

        await handle_relatorio_mensal(update, context)
        calls = [c[0][0] for c in update.message.reply_text.call_args_list]
        assert any("indisponivel" in c for c in calls)

    @pytest.mark.asyncio
    async def test_successful_generation_with_eventbridge(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 12345
        context = MagicMock()
        context.args = ["ClientDelta", "2", "2026"]

        mock_collector = AsyncMock()
        mock_collector.collect_and_format.return_value = "test data"

        mock_report = MagicMock()
        mock_report.period = "Fevereiro 2026"
        mock_report.client_name = "ClientDelta"
        mock_report.resumo_executivo = "Resumo teste"
        mock_report.model_dump.return_value = {"period": "Fevereiro 2026"}

        mock_rules = MagicMock()
        mock_rules.get_client_config.return_value = {"email": "test@example.com"}

        context.bot_data = {
            "report_collector": mock_collector,
            "report_agent": MagicMock(),
            "eventbridge_bus_name": "test-bus",
            "aws_region": "us-east-1",
            "rules_engine": mock_rules,
        }

        with patch(
            "src.bot.monthly_report_job.ai_generate_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "src.bot.monthly_report_job._dispatch_to_eventbridge",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            await handle_relatorio_mensal(update, context)

        mock_dispatch.assert_called_once()
        # Should have 2 calls: "Gerando..." and "Relatorio de... enviado..."
        assert update.message.reply_text.call_count == 2
        final_msg = update.message.reply_text.call_args_list[-1][0][0]
        assert "enviado para processamento" in final_msg

    @pytest.mark.asyncio
    async def test_no_eventbridge_shows_resumo(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 12345
        context = MagicMock()
        context.args = ["ClientAlpha"]

        mock_collector = AsyncMock()
        mock_collector.collect_and_format.return_value = "test data"

        mock_report = MagicMock()
        mock_report.period = "Janeiro 2026"
        mock_report.client_name = "ClientAlpha"
        mock_report.resumo_executivo = "Resumo executivo de teste"
        mock_report.model_dump.return_value = {"period": "Janeiro 2026"}

        context.bot_data = {
            "report_collector": mock_collector,
            "report_agent": MagicMock(),
            "eventbridge_bus_name": "",
            "aws_region": "us-east-1",
            "rules_engine": MagicMock(get_client_config=MagicMock(return_value={})),
        }

        with patch(
            "src.bot.monthly_report_job.ai_generate_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            await handle_relatorio_mensal(update, context)

        final_msg = update.message.reply_text.call_args_list[-1][0][0]
        assert "EventBridge nao configurado" in final_msg
        assert "Resumo executivo de teste" in final_msg

    @pytest.mark.asyncio
    async def test_generation_error_notifies_user(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 12345
        context = MagicMock()
        context.args = ["ClientDelta"]

        mock_collector = AsyncMock()
        mock_collector.collect_and_format.side_effect = RuntimeError("boom")

        context.bot_data = {
            "report_collector": mock_collector,
            "report_agent": MagicMock(),
            "eventbridge_bus_name": "bus",
            "aws_region": "us-east-1",
            "rules_engine": MagicMock(),
        }

        await handle_relatorio_mensal(update, context)

        final_msg = update.message.reply_text.call_args_list[-1][0][0]
        assert "Erro ao gerar relatorio" in final_msg


class TestDispatchToEventBridge:
    @pytest.mark.asyncio
    async def test_dispatches_correct_event(self):
        mock_report = MagicMock()
        mock_report.client_name = "ClientDelta"
        mock_report.period = "Fevereiro 2026"
        mock_report.model_dump.return_value = {
            "client_name": "ClientDelta",
            "period": "Fevereiro 2026",
        }

        mock_eb = MagicMock()
        mock_eb.put_events.return_value = {"FailedEntryCount": 0}

        with patch("src.bot.monthly_report_job.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_eb
            await _dispatch_to_eventbridge(
                report=mock_report,
                client_email="client@test.com",
                account_manager_chat_id=99999,
                bus_name="test-bus",
                region="us-east-1",
            )

        mock_boto3.client.assert_called_once_with("events", region_name="us-east-1")
        mock_eb.put_events.assert_called_once()
        entries = mock_eb.put_events.call_args[1]["Entries"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["Source"] == "app.bot.reports"
        assert entry["DetailType"] == "MonthlyReportGenerated"
        assert entry["EventBusName"] == "test-bus"

        detail = json.loads(entry["Detail"])
        assert detail["report_type"] == "monthly"
        assert detail["client_name"] == "ClientDelta"
        assert detail["client_email"] == "client@test.com"
        assert detail["account_manager_chat_id"] == 99999


class TestMonthlyReportCallback:
    @pytest.mark.asyncio
    async def test_generates_reports_for_all_clients(self):
        mock_collector = AsyncMock()
        mock_collector.collect_and_format.return_value = "data text"

        mock_report = MagicMock()
        mock_report.client_name = "ClientDelta"
        mock_report.period = "Janeiro 2026"
        mock_report.model_dump.return_value = {}

        mock_rules = MagicMock()
        mock_rules.get_all_clients.return_value = {"ClientDelta": {}, "ClientAlpha": {}}
        mock_rules.get_client_config.return_value = {
            "email": "test@test.com",
            "account_manager_id": "123",
        }
        mock_rules.get_telegram_chat_id.return_value = 55555

        mock_context = MagicMock()
        mock_context.bot.send_message = AsyncMock()

        # Simulate February 2026 (report for January)
        fixed_now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

        mock_context.job.data = {
            "collector": mock_collector,
            "report_agent": MagicMock(),
            "rules_engine": mock_rules,
            "eventbridge_bus_name": "test-bus",
            "aws_region": "us-east-1",
            "group_chat_id": 12345,
        }

        with patch(
            "src.bot.monthly_report_job.ai_generate_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "src.bot.monthly_report_job._dispatch_to_eventbridge",
            new_callable=AsyncMock,
        ) as mock_dispatch, patch(
            "src.bot.monthly_report_job.datetime",
        ) as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await monthly_report_callback(mock_context)

        # Should generate for both clients
        assert mock_dispatch.call_count == 2
        # Should notify group
        mock_context.bot.send_message.assert_called_once()
        msg = mock_context.bot.send_message.call_args[1]["text"]
        assert "2/2" in msg
        assert "Janeiro" in msg

    @pytest.mark.asyncio
    async def test_handles_january_wraps_to_december(self):
        mock_collector = AsyncMock()
        mock_collector.collect_and_format.return_value = "data"

        mock_report = MagicMock()
        mock_report.client_name = "ClientDelta"
        mock_report.period = "Dezembro 2025"
        mock_report.model_dump.return_value = {}

        mock_rules = MagicMock()
        mock_rules.get_all_clients.return_value = {"ClientDelta": {}}
        mock_rules.get_client_config.return_value = {}

        mock_context = MagicMock()
        mock_context.bot.send_message = AsyncMock()

        # January 2026 -> should report December 2025
        fixed_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        mock_context.job.data = {
            "collector": mock_collector,
            "report_agent": MagicMock(),
            "rules_engine": mock_rules,
            "eventbridge_bus_name": "bus",
            "aws_region": "us-east-1",
            "group_chat_id": 12345,
        }

        with patch(
            "src.bot.monthly_report_job.ai_generate_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "src.bot.monthly_report_job._dispatch_to_eventbridge",
            new_callable=AsyncMock,
        ), patch(
            "src.bot.monthly_report_job.datetime",
        ) as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await monthly_report_callback(mock_context)

        # Verify it collected for December 2025
        mock_collector.collect_and_format.assert_called_once_with("ClientDelta", 12, 2025)
        msg = mock_context.bot.send_message.call_args[1]["text"]
        assert "Dezembro" in msg

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self):
        mock_collector = AsyncMock()
        # First client fails, second succeeds
        mock_collector.collect_and_format.side_effect = [
            RuntimeError("boom"),
            "data text",
        ]

        mock_report = MagicMock()
        mock_report.client_name = "ClientAlpha"
        mock_report.period = "Janeiro 2026"
        mock_report.model_dump.return_value = {}

        mock_rules = MagicMock()
        mock_rules.get_all_clients.return_value = {"ClientDelta": {}, "ClientAlpha": {}}
        mock_rules.get_client_config.return_value = {}

        mock_context = MagicMock()
        mock_context.bot.send_message = AsyncMock()

        fixed_now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

        mock_context.job.data = {
            "collector": mock_collector,
            "report_agent": MagicMock(),
            "rules_engine": mock_rules,
            "eventbridge_bus_name": "bus",
            "aws_region": "us-east-1",
            "group_chat_id": 12345,
        }

        with patch(
            "src.bot.monthly_report_job.ai_generate_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ), patch(
            "src.bot.monthly_report_job._dispatch_to_eventbridge",
            new_callable=AsyncMock,
        ), patch(
            "src.bot.monthly_report_job.datetime",
        ) as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await monthly_report_callback(mock_context)

        # Only 1 dispatch (second client succeeded)
        msg = mock_context.bot.send_message.call_args[1]["text"]
        assert "1/2" in msg
