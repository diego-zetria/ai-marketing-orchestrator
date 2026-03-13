import hashlib
import hmac
from unittest.mock import AsyncMock

import pytest
import yaml

from src.bot.webhook_handler import WebhookHandler
from src.engine.rules import RulesEngine


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def rules_with_notifications(tmp_path):
    rules = {
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
            "pronto": {
                "notify": "group",
                "message": "esta pronta",
            },
        },
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


@pytest.fixture
def mock_clickup():
    """Mock ClickUpClient for A2/A5/A7 tests."""
    client = AsyncMock()
    client.get_task = AsyncMock(return_value={
        "id": "t1",
        "assignees": [{"id": 101, "username": "Pedro"}],
        "custom_fields": [],
    })
    client.update_task = AsyncMock(return_value={"id": "t1"})
    client.set_custom_field = AsyncMock(return_value={})
    return client


@pytest.fixture
def rules_with_clients(tmp_path):
    """Rules with client_overrides for A7 auto-assign tests."""
    rules = {
        "assignment_rules": {"design": {"default_assignees": ["101"], "tags": []}},
        "reviewers": {"strategy": "201", "content": "202"},
        "client_overrides": {
            "client_alpha": {
                "list_id": "list_hp",
                "designer": "401",
                "account": "501",
            },
        },
        "default_config": {"list_id": "list1", "initial_status": "planejamento"},
        "team_mapping": {
            "101": {"telegram_chat_id": 1001, "name": "Pedro", "role": "designer"},
            "201": {"telegram_chat_id": 2001, "name": "Luis", "role": "strategy_reviewer"},
            "202": {"telegram_chat_id": 2002, "name": "Content Lead", "role": "content_reviewer"},
            "301": {"telegram_chat_id": 3001, "name": "Account Manager A", "role": "account"},
            "401": {"telegram_chat_id": 4001, "name": "Designer A", "role": "designer"},
            "501": {"telegram_chat_id": 5001, "name": "Account Manager B", "role": "account"},
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
            "pronto": {
                "notify": "group",
                "message": "esta pronta",
            },
        },
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


@pytest.fixture
def handler(mock_bot, rules_with_notifications):
    return WebhookHandler(
        bot=mock_bot,
        rules_engine=rules_with_notifications,
        webhook_secret="test_secret",
    )


# === Signature verification ===

def test_verify_signature_valid(handler):
    payload = b'{"event":"taskStatusUpdated"}'
    sig = hmac.new(b"test_secret", payload, hashlib.sha256).hexdigest()
    assert handler.verify_signature(payload, sig) is True


def test_verify_signature_invalid(handler):
    payload = b'{"event":"taskStatusUpdated"}'
    assert handler.verify_signature(payload, "invalid_sig") is False


def test_verify_signature_no_secret(mock_bot, rules_with_notifications):
    h = WebhookHandler(bot=mock_bot, rules_engine=rules_with_notifications, webhook_secret="")
    assert h.verify_signature(b"anything", "anything") is True


# === Status change notifications ===

@pytest.mark.asyncio
async def test_notify_reviewers_on_revisao(handler, mock_bot):
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    await handler.handle_event(event)
    assert mock_bot.send_message.call_count == 2
    notified_ids = {call[1]["chat_id"] for call in mock_bot.send_message.call_args_list}
    assert notified_ids == {2001, 2002}


@pytest.mark.asyncio
async def test_notify_designer_on_alteracao(handler, mock_bot):
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "revisao"},
            "after": {"status": "alteracao"},
            "user": {"id": 201, "username": "Luis"},
        }],
    }
    await handler.handle_event(event)
    assert mock_bot.send_message.call_count == 1
    assert mock_bot.send_message.call_args[1]["chat_id"] == 1001


@pytest.mark.asyncio
async def test_notify_designer_and_account_on_aprovado(handler, mock_bot):
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "revisao"},
            "after": {"status": "aprovado"},
            "user": {"id": 201, "username": "Luis"},
        }],
    }
    await handler.handle_event(event)
    assert mock_bot.send_message.call_count == 2
    notified_ids = {call[1]["chat_id"] for call in mock_bot.send_message.call_args_list}
    assert notified_ids == {1001, 3001}


@pytest.mark.asyncio
async def test_message_contains_task_info(handler, mock_bot):
    event = {
        "event": "taskStatusUpdated",
        "task_id": "task_xyz",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    await handler.handle_event(event)
    msg = mock_bot.send_message.call_args_list[0][1]["text"]
    assert "task_xyz" in msg
    assert "revisao" in msg.lower()
    assert "Pedro" in msg
    assert "clickup.com" in msg


@pytest.mark.asyncio
async def test_ignores_non_status_event(handler, mock_bot):
    event = {
        "event": "taskUpdated",
        "task_id": "t1",
        "history_items": [{"field": "name", "before": "old", "after": "new"}],
    }
    await handler.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_unknown_event_type(handler, mock_bot):
    event = {"event": "spaceCreated", "space_id": "123"}
    await handler.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_status_not_in_rules(handler, mock_bot):
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "planejamento"},
            "after": {"status": "desenvolvimento"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    await handler.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_failure_does_not_crash(handler, mock_bot):
    mock_bot.send_message.side_effect = Exception("Telegram API error")
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    # Should not raise
    await handler.handle_event(event)


# === Multi-event dispatcher ===

@pytest.mark.asyncio
async def test_dispatches_task_comment_posted(handler, mock_bot):
    """taskCommentPosted events should be dispatched (placeholder handler logs)."""
    event = {
        "event": "taskCommentPosted",
        "task_id": "t1",
        "history_items": [{"comment": {"text_content": "aprovado"}}],
    }
    # Should not raise, dispatches to _handle_comment_posted
    await handler.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_dispatches_task_created(handler, mock_bot):
    """taskCreated events should be dispatched (placeholder handler logs)."""
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list1",
        "user": {"id": 101, "username": "Pedro"},
    }
    await handler.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_still_ignores_unregistered_event_type(handler, mock_bot):
    """Event types not in the dispatcher dict should be silently ignored."""
    event = {"event": "taskDeleted", "task_id": "t1"}
    await handler.handle_event(event)
    mock_bot.send_message.assert_not_called()


# === EventFilter integration ===

@pytest.mark.asyncio
async def test_skips_bot_events_with_filter(mock_bot, rules_with_notifications):
    from src.bot.event_filter import EventFilter
    ef = EventFilter(bot_user_id="101")
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", event_filter=ef,
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Bot"},
        }],
    }
    await h.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_skips_debounced_events_with_filter(mock_bot, rules_with_notifications):
    from src.bot.event_filter import EventFilter
    ef = EventFilter(bot_user_id="", debounce_seconds=30)
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", event_filter=ef,
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 999, "username": "Human"},
        }],
    }
    await h.handle_event(event)
    assert mock_bot.send_message.call_count == 2

    mock_bot.send_message.reset_mock()
    await h.handle_event(event)
    # Second time: debounced, no notifications sent
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_no_filter_processes_normally(handler, mock_bot):
    """Without event_filter set, events process normally (backward compat)."""
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    await handler.handle_event(event)
    assert mock_bot.send_message.call_count == 2


# === A2: Smart notification by assignee ===

@pytest.mark.asyncio
async def test_a2_smart_notif_uses_assignees(mock_bot, rules_with_notifications, mock_clickup):
    """A2: When ClickUpClient is available, notify task assignees instead of roles."""
    mock_clickup.get_task.return_value = {
        "id": "t1",
        "assignees": [{"id": 101, "username": "Pedro"}],
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 999, "username": "Human"},
        }],
    }
    await h.handle_event(event)
    # Should notify Pedro (assignee) not Luis+Content Lead (reviewers)
    assert mock_bot.send_message.call_count == 1
    assert mock_bot.send_message.call_args[1]["chat_id"] == 1001


@pytest.mark.asyncio
async def test_a2_falls_back_to_role_if_no_assignees(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """A2: Falls back to role-based when task has no assignees."""
    mock_clickup.get_task.return_value = {"id": "t1", "assignees": []}
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 999, "username": "Human"},
        }],
    }
    await h.handle_event(event)
    # Falls back to reviewers (2001, 2002)
    assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_a2_falls_back_on_api_error(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """A2: Falls back to role-based if ClickUp API fails."""
    mock_clickup.get_task.side_effect = Exception("API error")
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 999, "username": "Human"},
        }],
    }
    await h.handle_event(event)
    assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_a2_no_clickup_uses_role_based(handler, mock_bot):
    """A2: Without ClickUpClient, uses role-based resolution (backward compat)."""
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    await handler.handle_event(event)
    assert mock_bot.send_message.call_count == 2
    notified_ids = {call[1]["chat_id"] for call in mock_bot.send_message.call_args_list}
    assert notified_ids == {2001, 2002}


# === A5: Alteration cycle counter ===

@pytest.mark.asyncio
async def test_a5_increments_on_revisao_to_alteracao(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """A5: revisao->alteracao triggers alteration counter increment."""
    mock_clickup.get_task.return_value = {
        "id": "t1",
        "assignees": [{"id": 101}],
        "custom_fields": [{"id": "cf_alt", "value": 2}],
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        alteration_field_id="cf_alt",
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "revisao"},
            "after": {"status": "alteracao"},
            "user": {"id": 201, "username": "Luis"},
        }],
    }
    await h.handle_event(event)
    # Await the fire-and-forget task
    import asyncio
    await asyncio.sleep(0.05)

    mock_clickup.set_custom_field.assert_awaited_once_with("t1", "cf_alt", 3)


@pytest.mark.asyncio
async def test_a5_no_increment_on_other_transitions(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """A5: Non-alteration transitions don't trigger counter."""
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        alteration_field_id="cf_alt",
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "desenvolvimento"},
            "after": {"status": "revisao"},
            "user": {"id": 101, "username": "Pedro"},
        }],
    }
    await h.handle_event(event)
    import asyncio
    await asyncio.sleep(0.05)

    mock_clickup.set_custom_field.assert_not_awaited()


@pytest.mark.asyncio
async def test_a5_no_field_id_skips(mock_bot, rules_with_notifications, mock_clickup):
    """A5: Without alteration_field_id, counter is silently skipped."""
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        alteration_field_id="",
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "revisao"},
            "after": {"status": "alteracao"},
            "user": {"id": 201, "username": "Luis"},
        }],
    }
    await h.handle_event(event)
    import asyncio
    await asyncio.sleep(0.05)

    mock_clickup.set_custom_field.assert_not_awaited()


@pytest.mark.asyncio
async def test_a5_api_error_doesnt_crash(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """A5: API failure in counter increment doesn't crash the handler."""
    mock_clickup.get_task.side_effect = Exception("API error")
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        alteration_field_id="cf_alt",
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "revisao"},
            "after": {"status": "alteracao"},
            "user": {"id": 201, "username": "Luis"},
        }],
    }
    # Should not raise
    await h.handle_event(event)
    import asyncio
    await asyncio.sleep(0.05)


# === A7: Auto-assign by client ===

@pytest.mark.asyncio
async def test_a7_auto_assigns_designer_and_account(
    mock_bot, rules_with_clients, mock_clickup,
):
    """A7: taskCreated auto-assigns designer + account from client_overrides."""
    mock_clickup.get_task.return_value = {
        "id": "t1",
        "assignees": [],
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list_hp",  # client_alpha
        "user": {"id": 999, "username": "Someone"},
    }
    await h.handle_event(event)

    mock_clickup.update_task.assert_awaited_once_with(
        "t1",
        assignees={"add": [401, 501], "rem": []},
    )


@pytest.mark.asyncio
async def test_a7_skips_already_assigned(mock_bot, rules_with_clients, mock_clickup):
    """A7: Doesn't add assignees that are already present."""
    mock_clickup.get_task.return_value = {
        "id": "t1",
        "assignees": [{"id": 401, "username": "Designer A"}],
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list_hp",
        "user": {"id": 999, "username": "Someone"},
    }
    await h.handle_event(event)

    # Should only add account (501), not designer (401 already present)
    mock_clickup.update_task.assert_awaited_once_with(
        "t1",
        assignees={"add": [501], "rem": []},
    )


@pytest.mark.asyncio
async def test_a7_skips_all_already_assigned(
    mock_bot, rules_with_clients, mock_clickup,
):
    """A7: Skips update_task if all assignees already present."""
    mock_clickup.get_task.return_value = {
        "id": "t1",
        "assignees": [
            {"id": 401, "username": "Designer A"},
            {"id": 501, "username": "Account Manager B"},
        ],
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list_hp",
        "user": {"id": 999},
    }
    await h.handle_event(event)

    mock_clickup.update_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_a7_skips_unknown_list(mock_bot, rules_with_clients, mock_clickup):
    """A7: Skips auto-assign for unknown list_id (no client override)."""
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "unknown_list",
        "user": {"id": 999},
    }
    await h.handle_event(event)

    mock_clickup.get_task.assert_not_awaited()
    mock_clickup.update_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_a7_disabled_skips(mock_bot, rules_with_clients, mock_clickup):
    """A7: auto_assign_enabled=False disables the feature."""
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="", clickup_client=mock_clickup,
        auto_assign_enabled=False,
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list_hp",
        "user": {"id": 999},
    }
    await h.handle_event(event)

    mock_clickup.get_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_a7_no_clickup_skips(mock_bot, rules_with_clients):
    """A7: Without ClickUpClient, auto-assign is silently skipped."""
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="",
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list_hp",
        "user": {"id": 999},
    }
    await h.handle_event(event)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_a7_api_error_doesnt_crash(
    mock_bot, rules_with_clients, mock_clickup,
):
    """A7: API failure in auto-assign doesn't crash the handler."""
    mock_clickup.get_task.side_effect = Exception("API error")
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_clients,
        webhook_secret="", clickup_client=mock_clickup,
    )
    event = {
        "event": "taskCreated",
        "task_id": "t1",
        "list_id": "list_hp",
        "user": {"id": 999},
    }
    await h.handle_event(event)


# === revisao_cliente → EventBridge ===

@pytest.mark.asyncio
async def test_revisao_cliente_fires_eventbridge(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """Moving to revisao_cliente sends EventBridge event."""
    # Add revisao_cliente to notification_rules so it processes
    rules_with_notifications._rules["notification_rules"]["revisao_cliente"] = {
        "notify_roles": ["account"],
        "message": "foi enviada para aprovacao do cliente",
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        eventbridge_bus_name="approval-events",
        aws_region="us-east-1",
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "aprovado"},
            "after": {"status": "revisao_cliente"},
            "user": {"id": 301, "username": "Account Manager A"},
        }],
    }
    from unittest.mock import patch
    with patch(
        "src.integrations.eventbridge.send_task_status_event",
        return_value=True,
    ) as mock_eb:
        await h.handle_event(event)
        import asyncio
        await asyncio.sleep(0.05)
        mock_eb.assert_called_once_with(
            "approval-events", "t1",
            status="client_approval", region="us-east-1",
        )


@pytest.mark.asyncio
async def test_revisao_cliente_no_bus_skips(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """Without eventbridge_bus_name, revisao_cliente doesn't fire EventBridge."""
    rules_with_notifications._rules["notification_rules"]["revisao_cliente"] = {
        "notify_roles": ["account"],
        "message": "foi enviada para aprovacao do cliente",
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        eventbridge_bus_name="",  # not configured
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "aprovado"},
            "after": {"status": "revisao_cliente"},
            "user": {"id": 301, "username": "Account Manager A"},
        }],
    }
    from unittest.mock import patch
    with patch(
        "src.integrations.eventbridge.send_task_status_event",
    ) as mock_eb:
        await h.handle_event(event)
        import asyncio
        await asyncio.sleep(0.05)
        mock_eb.assert_not_called()


@pytest.mark.asyncio
async def test_client_alteration_cycle_increments(
    mock_bot, rules_with_notifications, mock_clickup,
):
    """revisao_cliente → alteracao_cliente triggers alteration counter."""
    rules_with_notifications._rules["notification_rules"]["alteracao_cliente"] = {
        "notify_roles": ["designer", "account"],
        "message": "precisa de alteracao (solicitado pelo cliente)",
    }
    mock_clickup.get_task.return_value = {
        "id": "t1",
        "assignees": [{"id": 101}],
        "custom_fields": [{"id": "cf_alt", "value": 1}],
    }
    h = WebhookHandler(
        bot=mock_bot, rules_engine=rules_with_notifications,
        webhook_secret="", clickup_client=mock_clickup,
        alteration_field_id="cf_alt",
    )
    event = {
        "event": "taskStatusUpdated",
        "task_id": "t1",
        "history_items": [{
            "field": "status",
            "before": {"status": "revisao_cliente"},
            "after": {"status": "alteracao_cliente"},
            "user": {"id": 301, "username": "Account Manager A"},
        }],
    }
    await h.handle_event(event)
    import asyncio
    await asyncio.sleep(0.05)
    mock_clickup.set_custom_field.assert_awaited_once_with("t1", "cf_alt", 2)
