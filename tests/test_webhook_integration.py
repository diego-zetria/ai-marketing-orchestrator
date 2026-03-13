"""Integration test: ClickUp webhook event -> notification on Telegram."""
from unittest.mock import AsyncMock

import pytest
import yaml

from src.bot.webhook_handler import WebhookHandler
from src.engine.rules import RulesEngine

RULES_WITH_FULL_CONFIG = {
    "assignment_rules": {"design": {"default_assignees": ["101"], "tags": []}},
    "reviewers": {"strategy": "201", "content": "202"},
    "client_overrides": {},
    "default_config": {"list_id": "list1", "initial_status": "planejamento"},
    "team_mapping": {
        "101": {"telegram_chat_id": 1001, "name": "Pedro Designer", "role": "designer"},
        "201": {"telegram_chat_id": 2001, "name": "Luis Reviewer", "role": "strategy_reviewer"},
        "202": {"telegram_chat_id": 2002, "name": "Content Lead Reviewer", "role": "content_reviewer"},
        "301": {"telegram_chat_id": 3001, "name": "Account Manager A Account", "role": "account"},
    },
    "notification_rules": {
        "revisao": {
            "notify_roles": ["strategy_reviewer", "content_reviewer"],
            "message": "precisa de revisao",
        },
        "alteracao": {
            "notify_roles": ["designer"],
            "message": "voltou para alteracao",
        },
        "aprovado": {
            "notify_roles": ["designer", "account"],
            "message": "foi aprovada!",
        },
    },
}


@pytest.fixture
def rules_engine(tmp_path):
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(RULES_WITH_FULL_CONFIG))
    return RulesEngine(f)


def _status_event(task_id, before, after, user_id, username):
    return {
        "event": "taskStatusUpdated",
        "task_id": task_id,
        "history_items": [{
            "field": "status",
            "before": {"status": before},
            "after": {"status": after},
            "user": {"id": user_id, "username": username},
        }],
    }


@pytest.mark.asyncio
async def test_full_review_cycle(rules_engine):
    """Simulate: designer finishes -> reviewer reviews -> asks changes -> approves."""
    bot = AsyncMock()
    handler = WebhookHandler(bot=bot, rules_engine=rules_engine, webhook_secret="")

    # Step 1: Designer moves to "revisao"
    await handler.handle_event(
        _status_event("task_abc", "desenvolvimento", "revisao", 101, "Pedro"),
    )
    assert bot.send_message.call_count == 2
    notified = {c[1]["chat_id"] for c in bot.send_message.call_args_list}
    assert notified == {2001, 2002}

    bot.reset_mock()

    # Step 2: Reviewer sends back to "alteracao"
    await handler.handle_event(
        _status_event("task_abc", "revisao", "alteracao", 201, "Luis"),
    )
    assert bot.send_message.call_count == 1
    assert bot.send_message.call_args[1]["chat_id"] == 1001

    bot.reset_mock()

    # Step 3: Designer fixes and moves back to "revisao"
    await handler.handle_event(
        _status_event("task_abc", "alteracao", "revisao", 101, "Pedro"),
    )
    assert bot.send_message.call_count == 2

    bot.reset_mock()

    # Step 4: Reviewer approves
    await handler.handle_event(
        _status_event("task_abc", "revisao", "aprovado", 201, "Luis"),
    )
    assert bot.send_message.call_count == 2
    notified = {c[1]["chat_id"] for c in bot.send_message.call_args_list}
    assert notified == {1001, 3001}


@pytest.mark.asyncio
async def test_multiple_tasks_independent(rules_engine):
    """Notifications for different tasks don't interfere."""
    bot = AsyncMock()
    handler = WebhookHandler(bot=bot, rules_engine=rules_engine, webhook_secret="")

    await handler.handle_event(
        _status_event("task_1", "desenvolvimento", "revisao", 101, "Pedro"),
    )
    await handler.handle_event(
        _status_event("task_2", "desenvolvimento", "revisao", 101, "Pedro"),
    )

    # 2 reviewers * 2 tasks = 4 messages
    assert bot.send_message.call_count == 4

    # Verify both task IDs appear in messages
    msgs = [c[1]["text"] for c in bot.send_message.call_args_list]
    task_1_msgs = [m for m in msgs if "task_1" in m]
    task_2_msgs = [m for m in msgs if "task_2" in m]
    assert len(task_1_msgs) == 2
    assert len(task_2_msgs) == 2


@pytest.mark.asyncio
async def test_non_status_events_ignored(rules_engine):
    """Non-status events should not trigger notifications."""
    bot = AsyncMock()
    handler = WebhookHandler(bot=bot, rules_engine=rules_engine, webhook_secret="")

    for event_type in ["taskCreated", "taskUpdated", "taskDeleted", "listUpdated"]:
        await handler.handle_event({
            "event": event_type,
            "task_id": "task_abc",
            "history_items": [{"field": "name", "before": "old", "after": "new"}],
        })

    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_unconfigured_status_ignored(rules_engine):
    """Status transitions not in notification_rules are silently ignored."""
    bot = AsyncMock()
    handler = WebhookHandler(bot=bot, rules_engine=rules_engine, webhook_secret="")

    await handler.handle_event(
        _status_event("task_abc", "planejamento", "desenvolvimento", 101, "Pedro"),
    )
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_notification_message_format(rules_engine):
    """Verify notification message contains all expected information."""
    bot = AsyncMock()
    handler = WebhookHandler(bot=bot, rules_engine=rules_engine, webhook_secret="")

    await handler.handle_event(
        _status_event("task_xyz", "desenvolvimento", "revisao", 101, "Pedro"),
    )

    msg = bot.send_message.call_args_list[0][1]["text"]
    assert "task_xyz" in msg
    assert "revisao" in msg.lower()
    assert "Pedro" in msg
    assert "clickup.com" in msg
    assert "Markdown" == bot.send_message.call_args_list[0][1]["parse_mode"]
