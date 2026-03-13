from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.deadline_alert import (
    collect_at_risk_tasks,
    deadline_alert_callback,
    format_alert_message,
    send_deadline_alerts,
    should_send_alert,
)


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


def _now_ms():
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def _make_task(
    task_id,
    name,
    status,
    due_date=None,
    date_updated=None,
    assignees=None,
    url=None,
):
    return {
        "id": task_id,
        "name": name,
        "status": {"status": status},
        "assignees": assignees or [],
        "due_date": str(due_date) if due_date is not None else None,
        "date_updated": str(date_updated) if date_updated is not None else str(_now_ms()),
        "url": url or f"https://app.clickup.com/t/{task_id}",
    }


# ===== collect_at_risk_tasks =====


@pytest.mark.asyncio
async def test_critical_24h_task(mock_clickup, mock_rules):
    """Task due in 12h -> critical_24h."""
    due_ms = _now_ms() + 12 * 3600 * 1000  # 12h from now
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Post ClientDelta", "desenvolvimento", due_date=due_ms),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["critical_24h"]) == 1
    assert result["critical_24h"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_attention_48h_task(mock_clickup, mock_rules):
    """Task due in 36h -> attention_48h."""
    due_ms = _now_ms() + 36 * 3600 * 1000  # 36h from now
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Post ClientGamma", "revisao", due_date=due_ms),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["attention_48h"]) == 1
    assert result["attention_48h"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_done_tasks_excluded(mock_clickup, mock_rules):
    """Done tasks (aprovado/pronto) excluded from all categories."""
    due_ms = _now_ms() + 12 * 3600 * 1000
    old_update = _now_ms() - 30 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Done task", "aprovado", due_date=due_ms, date_updated=old_update),
        _make_task("t2", "Done task 2", "pronto", due_date=due_ms, date_updated=old_update),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["critical_24h"]) == 0
    assert len(result["attention_48h"]) == 0
    assert len(result["stalled"]) == 0


@pytest.mark.asyncio
async def test_overdue_excluded(mock_clickup, mock_rules):
    """Due date in the past -> not in any category."""
    past_ms = _now_ms() - 2 * 3600 * 1000  # 2h ago
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Overdue task", "desenvolvimento", due_date=past_ms),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["critical_24h"]) == 0
    assert len(result["attention_48h"]) == 0


@pytest.mark.asyncio
async def test_no_due_date_excluded(mock_clickup, mock_rules):
    """No due_date -> not in critical/attention."""
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "No due date", "desenvolvimento"),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["critical_24h"]) == 0
    assert len(result["attention_48h"]) == 0


@pytest.mark.asyncio
async def test_stalled_task(mock_clickup, mock_rules):
    """No update for 30h -> stalled."""
    old_update = _now_ms() - 30 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Stalled task", "desenvolvimento", date_updated=old_update),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["stalled"]) == 1
    assert result["stalled"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_recently_updated_not_stalled(mock_clickup, mock_rules):
    """Updated 6h ago -> not stalled."""
    recent_update = _now_ms() - 6 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Active task", "desenvolvimento", date_updated=recent_update),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["stalled"]) == 0


@pytest.mark.asyncio
async def test_stalled_done_excluded(mock_clickup, mock_rules):
    """Done + old update -> not stalled."""
    old_update = _now_ms() - 30 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Done stalled", "pronto", date_updated=old_update),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["stalled"]) == 0


@pytest.mark.asyncio
async def test_task_critical_and_stalled(mock_clickup, mock_rules):
    """Due 12h + old update -> both critical and stalled."""
    due_ms = _now_ms() + 12 * 3600 * 1000
    old_update = _now_ms() - 30 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Critical stalled", "desenvolvimento",
                   due_date=due_ms, date_updated=old_update),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["critical_24h"]) == 1
    assert len(result["stalled"]) == 1


@pytest.mark.asyncio
async def test_boundary_24h(mock_clickup, mock_rules):
    """Due exactly 24h from now -> attention (not critical)."""
    due_ms = _now_ms() + 24 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Boundary task", "desenvolvimento", due_date=due_ms),
    ]

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert len(result["critical_24h"]) == 0
    assert len(result["attention_48h"]) == 1


@pytest.mark.asyncio
async def test_empty_tasks(mock_clickup, mock_rules):
    """No tasks -> all lists empty."""
    mock_clickup.get_tasks.return_value = []

    result = await collect_at_risk_tasks(mock_clickup, mock_rules)

    assert result["critical_24h"] == []
    assert result["attention_48h"] == []
    assert result["stalled"] == []


# ===== format_alert_message =====


def test_format_alert_critical():
    """Message contains 'CRITICO' and task name."""
    at_risk = {
        "critical_24h": [
            _make_task("t1", "Post ClientDelta 03/03", "desenvolvimento",
                       due_date=_now_ms() + 10 * 3600 * 1000,
                       assignees=[{"username": "Pedro"}]),
        ],
        "attention_48h": [],
        "stalled": [],
    }

    msg = format_alert_message(at_risk)

    assert "CRITICO" in msg
    assert "Post ClientDelta 03/03" in msg


def test_format_alert_empty():
    """All empty -> returns empty string."""
    at_risk = {"critical_24h": [], "attention_48h": [], "stalled": []}

    msg = format_alert_message(at_risk)

    assert msg == ""


def test_format_alert_combined():
    """3 categories -> contains all task names."""
    at_risk = {
        "critical_24h": [
            _make_task("t1", "Task Critical", "desenvolvimento",
                       due_date=_now_ms() + 10 * 3600 * 1000),
        ],
        "attention_48h": [
            _make_task("t2", "Task Attention", "revisao",
                       due_date=_now_ms() + 30 * 3600 * 1000),
        ],
        "stalled": [
            _make_task("t3", "Task Stalled", "em criacao",
                       date_updated=_now_ms() - 30 * 3600 * 1000),
        ],
    }

    msg = format_alert_message(at_risk)

    assert "Task Critical" in msg
    assert "Task Attention" in msg
    assert "Task Stalled" in msg
    assert "CRITICO" in msg
    assert "ATENCAO" in msg.upper()
    assert "PARADA" in msg.upper()


# ===== should_send_alert =====


def test_should_send_empty_cache():
    """Empty cache -> True."""
    assert should_send_alert("t1", "critical", {}, 6) is True


def test_should_send_debounced():
    """Recent entry in cache -> False."""
    cache = {("t1", "critical"): datetime.now(tz=timezone.utc)}
    assert should_send_alert("t1", "critical", cache, 6) is False


def test_should_send_expired():
    """7h ago with debounce=6 -> True."""
    from datetime import timedelta

    old = datetime.now(tz=timezone.utc) - timedelta(hours=7)
    cache = {("t1", "critical"): old}
    assert should_send_alert("t1", "critical", cache, 6) is True


def test_should_send_different_type():
    """('t1','critical') in cache, query ('t1','stalled') -> True."""
    cache = {("t1", "critical"): datetime.now(tz=timezone.utc)}
    assert should_send_alert("t1", "stalled", cache, 6) is True


# ===== send_deadline_alerts =====


@pytest.mark.asyncio
async def test_send_individual_and_group():
    """Mapped assignee -> 2 messages (individual + group)."""
    bot = AsyncMock()
    rules = MagicMock()
    rules.get_telegram_chat_id.return_value = 12345

    at_risk = {
        "critical_24h": [
            _make_task("t1", "Task1", "desenvolvimento",
                       due_date=_now_ms() + 10 * 3600 * 1000,
                       assignees=[{"id": "user1", "username": "Pedro"}]),
        ],
        "attention_48h": [],
        "stalled": [],
    }

    cache = {}
    await send_deadline_alerts(
        bot=bot,
        at_risk_tasks=at_risk,
        rules_engine=rules,
        group_chat_id=-100123,
        debounce_cache=cache,
        debounce_hours=6,
    )

    assert bot.send_message.call_count >= 2  # individual + group


@pytest.mark.asyncio
async def test_send_unmapped_group_only():
    """chat_id=0 -> only group message."""
    bot = AsyncMock()
    rules = MagicMock()
    rules.get_telegram_chat_id.return_value = 0

    at_risk = {
        "critical_24h": [
            _make_task("t1", "Task1", "desenvolvimento",
                       due_date=_now_ms() + 10 * 3600 * 1000,
                       assignees=[{"id": "user1", "username": "Pedro"}]),
        ],
        "attention_48h": [],
        "stalled": [],
    }

    cache = {}
    await send_deadline_alerts(
        bot=bot,
        at_risk_tasks=at_risk,
        rules_engine=rules,
        group_chat_id=-100123,
        debounce_cache=cache,
        debounce_hours=6,
    )

    # Only group message (no individual)
    for call in bot.send_message.call_args_list:
        chat_id = call[1].get("chat_id") or call[0][0]
        assert chat_id != 0


@pytest.mark.asyncio
async def test_send_debounce_prevents_duplicate():
    """2nd immediate call -> 0 new messages."""
    bot = AsyncMock()
    rules = MagicMock()
    rules.get_telegram_chat_id.return_value = 12345

    at_risk = {
        "critical_24h": [
            _make_task("t1", "Task1", "desenvolvimento",
                       due_date=_now_ms() + 10 * 3600 * 1000,
                       assignees=[{"id": "user1", "username": "Pedro"}]),
        ],
        "attention_48h": [],
        "stalled": [],
    }

    cache = {}
    await send_deadline_alerts(
        bot=bot, at_risk_tasks=at_risk, rules_engine=rules,
        group_chat_id=-100123, debounce_cache=cache, debounce_hours=6,
    )
    first_count = bot.send_message.call_count

    # Second call - should be debounced
    await send_deadline_alerts(
        bot=bot, at_risk_tasks=at_risk, rules_engine=rules,
        group_chat_id=-100123, debounce_cache=cache, debounce_hours=6,
    )

    assert bot.send_message.call_count == first_count


@pytest.mark.asyncio
async def test_send_empty_no_messages():
    """No tasks at-risk -> send_message not called."""
    bot = AsyncMock()
    rules = MagicMock()
    at_risk = {"critical_24h": [], "attention_48h": [], "stalled": []}

    await send_deadline_alerts(
        bot=bot, at_risk_tasks=at_risk, rules_engine=rules,
        group_chat_id=-100123, debounce_cache={}, debounce_hours=6,
    )

    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_error_no_crash():
    """send_message raises -> no crash."""
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("Telegram down")
    rules = MagicMock()
    rules.get_telegram_chat_id.return_value = 12345

    at_risk = {
        "critical_24h": [
            _make_task("t1", "Task1", "desenvolvimento",
                       due_date=_now_ms() + 10 * 3600 * 1000,
                       assignees=[{"id": "user1", "username": "Pedro"}]),
        ],
        "attention_48h": [],
        "stalled": [],
    }

    # Should not raise
    await send_deadline_alerts(
        bot=bot, at_risk_tasks=at_risk, rules_engine=rules,
        group_chat_id=-100123, debounce_cache={}, debounce_hours=6,
    )


# ===== deadline_alert_callback =====


@pytest.mark.asyncio
async def test_callback_no_tasks(mock_clickup, mock_rules):
    """Empty tasks -> send_message not called."""
    mock_clickup.get_tasks.return_value = []

    context = MagicMock()
    context.bot = AsyncMock()
    context.job = MagicMock()
    context.job.data = {
        "clickup_client": mock_clickup,
        "rules_engine": mock_rules,
        "group_chat_id": -100123,
        "debounce_cache": {},
        "debounce_hours": 6,
    }

    await deadline_alert_callback(context)

    context.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_callback_sends_on_critical(mock_clickup, mock_rules):
    """Critical task -> group notified."""
    due_ms = _now_ms() + 10 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Urgent task", "desenvolvimento", due_date=due_ms),
    ]

    context = MagicMock()
    context.bot = AsyncMock()
    context.job = MagicMock()
    context.job.data = {
        "clickup_client": mock_clickup,
        "rules_engine": mock_rules,
        "group_chat_id": -100123,
        "debounce_cache": {},
        "debounce_hours": 6,
    }

    await deadline_alert_callback(context)

    context.bot.send_message.assert_called()
    # Check group received the alert
    calls = context.bot.send_message.call_args_list
    group_calls = [c for c in calls if c[1].get("chat_id") == -100123]
    assert len(group_calls) >= 1


@pytest.mark.asyncio
async def test_callback_handles_error(mock_clickup, mock_rules):
    """get_tasks raises -> error message sent."""
    mock_clickup.get_tasks.side_effect = Exception("API down")

    context = MagicMock()
    context.bot = AsyncMock()
    context.job = MagicMock()
    context.job.data = {
        "clickup_client": mock_clickup,
        "rules_engine": mock_rules,
        "group_chat_id": -100123,
        "debounce_cache": {},
        "debounce_hours": 6,
    }

    await deadline_alert_callback(context)

    context.bot.send_message.assert_called_once()
    msg = context.bot.send_message.call_args[1]["text"]
    assert "erro" in msg.lower()


@pytest.mark.asyncio
async def test_callback_passes_debounce_cache(mock_clickup, mock_rules):
    """Cache from job_data is used (not a new one)."""
    due_ms = _now_ms() + 10 * 3600 * 1000
    mock_clickup.get_tasks.return_value = [
        _make_task("t1", "Urgent task", "desenvolvimento", due_date=due_ms),
    ]

    shared_cache = {}
    context = MagicMock()
    context.bot = AsyncMock()
    context.job = MagicMock()
    context.job.data = {
        "clickup_client": mock_clickup,
        "rules_engine": mock_rules,
        "group_chat_id": -100123,
        "debounce_cache": shared_cache,
        "debounce_hours": 6,
    }

    await deadline_alert_callback(context)

    # Cache should have been populated
    assert len(shared_cache) > 0
