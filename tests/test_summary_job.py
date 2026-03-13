from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.schemas import DailySummary
from src.bot.summary_job import collect_task_data, daily_summary_callback


@pytest.fixture
def mock_clickup():
    return AsyncMock()


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_all_clients.return_value = {}
    rules.get_default_list_id.return_value = "list_default"
    rules.get_client_config.return_value = {}
    return rules


def _make_task(
    task_id, name, status, due_date=None, date_updated=None, assignees=None,
):
    now_ms = str(int(datetime.now(tz=timezone.utc).timestamp() * 1000))
    return {
        "id": task_id,
        "name": name,
        "status": {"status": status},
        "assignees": assignees or [],
        "due_date": due_date,
        "date_updated": date_updated or now_ms,
    }


# === collect_task_data ===

@pytest.mark.asyncio
async def test_collect_task_data_basic(mock_clickup, mock_rules):
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Post ClientDelta", "desenvolvimento"),
        _make_task("t2", "Post ClientGamma", "pronto"),
    ]

    result = await collect_task_data(mock_clickup, mock_rules)

    assert isinstance(result, str)
    assert "Post ClientDelta" in result
    assert "Concluidas: 1" in result


@pytest.mark.asyncio
async def test_collect_task_data_identifies_overdue(mock_clickup, mock_rules):
    past_ms = "1609459200000"  # 2021-01-01 (past)
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Post atrasado", "desenvolvimento", due_date=past_ms),
    ]

    result = await collect_task_data(mock_clickup, mock_rules)

    assert "atrasad" in result.lower()


@pytest.mark.asyncio
async def test_collect_task_data_identifies_upcoming_deadline(mock_clickup, mock_rules):
    # Due date 24h from now
    soon_ms = str(int((datetime.now(tz=timezone.utc).timestamp() + 86400) * 1000))
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Post urgente", "desenvolvimento", due_date=soon_ms),
    ]

    result = await collect_task_data(mock_clickup, mock_rules)

    assert "deadline" in result.lower() or "prazo" in result.lower()


@pytest.mark.asyncio
async def test_collect_task_data_identifies_bottleneck(mock_clickup, mock_rules):
    old_update_ms = str(int((datetime.now(tz=timezone.utc).timestamp() - 200000) * 1000))
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Post parado", "revisao", date_updated=old_update_ms),
    ]

    result = await collect_task_data(mock_clickup, mock_rules)

    assert "gargalo" in result.lower() or "parad" in result.lower()


@pytest.mark.asyncio
async def test_collect_task_data_empty_lists(mock_clickup, mock_rules):
    mock_clickup.get_tasks.return_value = []

    result = await collect_task_data(mock_clickup, mock_rules)

    assert isinstance(result, str)
    assert "0" in result or "nenhuma" in result.lower()


# === daily_summary_callback ===

@pytest.mark.asyncio
async def test_daily_summary_callback_sends_message():
    mock_summary = DailySummary(
        resumo="Resumo do dia: 3 ativas, 1 concluida.",
        total_ativas=3,
        total_concluidas=1,
        total_atrasadas=0,
        gargalos=[],
        deadlines_proximos=[],
    )

    mock_bot = AsyncMock()

    context = MagicMock()
    context.bot = mock_bot
    context.job = MagicMock()
    context.job.data = {
        "clickup_client": AsyncMock(),
        "rules_engine": MagicMock(),
        "summary_agent": MagicMock(),
        "group_chat_id": -100123456,
    }
    # Setup rules for collect_task_data
    context.job.data["rules_engine"].get_all_clients.return_value = {}
    context.job.data["rules_engine"].get_default_list_id.return_value = "list_default"
    context.job.data["rules_engine"].get_client_config.return_value = {}
    context.job.data["clickup_client"].get_tasks.return_value = []

    with patch(
        "src.bot.summary_job.generate_summary",
        new_callable=AsyncMock,
        return_value=mock_summary,
    ):
        await daily_summary_callback(context)

    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    assert call_kwargs[1]["chat_id"] == -100123456
    assert "Resumo do dia" in call_kwargs[1]["text"]


@pytest.mark.asyncio
async def test_daily_summary_callback_handles_error():
    context = MagicMock()
    context.bot = AsyncMock()
    context.job = MagicMock()
    context.job.data = {
        "clickup_client": AsyncMock(),
        "rules_engine": MagicMock(),
        "summary_agent": MagicMock(),
        "group_chat_id": -100123456,
    }
    context.job.data["rules_engine"].get_all_clients.return_value = {}
    context.job.data["rules_engine"].get_default_list_id.return_value = "list_default"
    context.job.data["rules_engine"].get_client_config.return_value = {}
    context.job.data["clickup_client"].get_tasks.side_effect = Exception("API down")

    with patch(
        "src.bot.summary_job.generate_summary",
        new_callable=AsyncMock,
    ):
        await daily_summary_callback(context)

    # Should NOT have called generate_summary since data collection failed
    # But should have sent an error message
    context.bot.send_message.assert_called_once()
    msg = context.bot.send_message.call_args[1]["text"]
    assert "erro" in msg.lower()
