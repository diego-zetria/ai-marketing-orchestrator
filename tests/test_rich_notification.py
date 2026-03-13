"""Tests for A6: Rich preview notification on revisao status."""
from unittest.mock import AsyncMock

import pytest
import yaml

from src.bot.webhook_handler import WebhookHandler
from src.engine.rules import RulesEngine


@pytest.fixture
def rules_engine(tmp_path):
    rules = {
        "assignment_rules": {"design": {"default_assignees": ["101"], "tags": []}},
        "reviewers": {"strategy": "201"},
        "client_overrides": {
            "client_delta": {"list_id": "list_client_delta", "designer": "101", "account": "301"},
        },
        "default_config": {"list_id": "list1", "initial_status": "planejamento"},
        "team_mapping": {
            "101": {"telegram_chat_id": 1001, "name": "Pedro", "role": "designer"},
            "201": {"telegram_chat_id": 2001, "name": "Luis", "role": "strategy_reviewer"},
            "301": {"telegram_chat_id": 3001, "name": "Account Manager A", "role": "account"},
        },
        "notification_rules": {
            "revisao": {
                "notify_roles": ["strategy_reviewer"],
                "message": "precisa de revisao",
            },
            "aprovado": {
                "notify_roles": ["designer"],
                "message": "foi aprovada!",
            },
        },
        "telegram_topics": {
            "client_delta": {"topic_id": 0, "label": "ClientDelta"},
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
def mock_clickup():
    client = AsyncMock()
    client.get_task = AsyncMock(return_value={
        "id": "t1",
        "name": "Post Instagram ClientDelta Marco",
        "assignees": [{"id": 201, "username": "Luis"}],
        "custom_fields": [
            {"id": "cf_drive", "value": "https://drive.google.com/file/d/abc123"},
        ],
    })
    return client


class TestRichNotification:
    @pytest.mark.asyncio
    async def test_revisao_includes_task_name(
        self, mock_bot, rules_engine, mock_clickup,
    ):
        """A6: Notification for revisao includes task name."""
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list_client_delta",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "Post Instagram ClientDelta Marco" in msg

    @pytest.mark.asyncio
    async def test_revisao_includes_client_name(
        self, mock_bot, rules_engine, mock_clickup,
    ):
        """A6: Notification for revisao includes client name."""
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list_client_delta",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "ClientDelta" in msg

    @pytest.mark.asyncio
    async def test_revisao_includes_drive_link(
        self, mock_bot, rules_engine, mock_clickup,
    ):
        """A6: Notification for revisao includes Drive link."""
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list_client_delta",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "drive.google.com" in msg
        assert "Link de Entrega" in msg

    @pytest.mark.asyncio
    async def test_revisao_without_drive_link(
        self, mock_bot, rules_engine, mock_clickup,
    ):
        """A6: Notification works without Drive link."""
        mock_clickup.get_task.return_value = {
            "id": "t1",
            "name": "Post ClientAlpha",
            "assignees": [{"id": 201}],
            "custom_fields": [],
        }
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list1",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "Link de Entrega" not in msg
        assert "Post ClientAlpha" in msg

    @pytest.mark.asyncio
    async def test_non_revisao_uses_standard_format(
        self, mock_bot, rules_engine, mock_clickup,
    ):
        """A6: Non-revisao notifications use standard format."""
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list_client_delta",
            "history_items": [{
                "field": "status",
                "before": {"status": "revisao"},
                "after": {"status": "aprovado"},
                "user": {"id": 201, "username": "Luis"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "foi aprovada!" in msg
        assert "Revisao necessaria" not in msg

    @pytest.mark.asyncio
    async def test_revisao_without_clickup_client(
        self, mock_bot, rules_engine,
    ):
        """A6: Without ClickUp client, falls back to standard format."""
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="",
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "precisa de revisao" in msg

    @pytest.mark.asyncio
    async def test_revisao_changed_by_name(
        self, mock_bot, rules_engine, mock_clickup,
    ):
        """A6: Notification includes who moved the task."""
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_engine,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list_client_delta",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "Pedro" in msg


class TestExtractDriveLink:
    def test_extracts_drive_link_from_custom_fields(self):
        task_data = {
            "custom_fields": [
                {"id": "cf1", "value": "https://drive.google.com/file/d/abc"},
            ],
        }
        assert WebhookHandler._extract_drive_link(task_data) == \
            "https://drive.google.com/file/d/abc"

    def test_returns_empty_when_no_drive_link(self):
        task_data = {"custom_fields": [{"id": "cf1", "value": "some other value"}]}
        assert WebhookHandler._extract_drive_link(task_data) == ""

    def test_returns_empty_when_no_custom_fields(self):
        assert WebhookHandler._extract_drive_link({}) == ""

    def test_skips_non_string_values(self):
        task_data = {"custom_fields": [{"id": "cf1", "value": 42}]}
        assert WebhookHandler._extract_drive_link(task_data) == ""
