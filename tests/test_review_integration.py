import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from src.bot.webhook_handler import WebhookHandler
from src.engine.rules import RulesEngine


@pytest.fixture
def rules_with_notifications(tmp_path):
    rules = {
        "assignment_rules": {"design": {"default_assignees": ["101"], "tags": []}},
        "reviewers": {},
        "client_overrides": {},
        "default_config": {"list_id": "list1"},
        "team_mapping": {
            "201": {"telegram_chat_id": 2001, "name": "Luis", "role": "strategy_reviewer"},
            "202": {"telegram_chat_id": 2002, "name": "Content Lead", "role": "content_reviewer"},
        },
        "notification_rules": {
            "revisao": {
                "notify_roles": ["strategy_reviewer", "content_reviewer"],
                "message": "precisa de revisao",
            },
            "desenvolvimento": {
                "notify_roles": ["strategy_reviewer"],
                "message": "em desenvolvimento",
            },
        },
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_review_handler():
    handler = AsyncMock()
    handler.trigger_review = AsyncMock()
    return handler


def _make_event(after_status, task_id="t1", list_id="list1"):
    return {
        "event": "taskStatusUpdated",
        "task_id": task_id,
        "list_id": list_id,
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": after_status},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }


@pytest.mark.asyncio
async def test_webhook_revisao_triggers_review(
    mock_bot, rules_with_notifications, mock_review_handler,
):
    handler = WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="",
        review_handler=mock_review_handler,
    )
    event = _make_event("revisao", task_id="t1", list_id="list_abc")
    await handler.handle_event(event)

    # Let the fire-and-forget task run
    await asyncio.sleep(0.05)

    mock_review_handler.trigger_review.assert_called_once_with("t1", "list_abc")


@pytest.mark.asyncio
async def test_webhook_other_status_no_review(
    mock_bot, rules_with_notifications, mock_review_handler,
):
    handler = WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="",
        review_handler=mock_review_handler,
    )
    event = _make_event("desenvolvimento")
    await handler.handle_event(event)
    await asyncio.sleep(0.05)

    mock_review_handler.trigger_review.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_no_review_handler_ok(mock_bot, rules_with_notifications):
    handler = WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="",
        review_handler=None,
    )
    event = _make_event("revisao")
    # Should not raise even without review_handler
    await handler.handle_event(event)


@pytest.mark.asyncio
async def test_webhook_review_error_no_crash(
    mock_bot, rules_with_notifications,
):
    mock_rh = AsyncMock()
    mock_rh.trigger_review = AsyncMock(side_effect=Exception("Review failed"))

    handler = WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="",
        review_handler=mock_rh,
    )
    event = _make_event("revisao")

    # Should not raise
    await handler.handle_event(event)
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_webhook_still_sends_notification(
    mock_bot, rules_with_notifications, mock_review_handler,
):
    handler = WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="",
        review_handler=mock_review_handler,
    )
    event = _make_event("revisao")
    await handler.handle_event(event)
    await asyncio.sleep(0.05)

    # Normal notifications still sent (2 reviewers)
    assert mock_bot.send_message.call_count == 2
    # And review was triggered
    mock_review_handler.trigger_review.assert_called_once()


@pytest.mark.asyncio
async def test_fire_and_forget_pattern(
    mock_bot, rules_with_notifications, mock_review_handler,
):
    """Verify that asyncio.create_task is used (fire-and-forget pattern)."""
    handler = WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="",
        review_handler=mock_review_handler,
    )
    event = _make_event("revisao")

    with patch("src.bot.webhook_handler.asyncio.create_task") as mock_ct:
        await handler.handle_event(event)
        mock_ct.assert_called_once()
