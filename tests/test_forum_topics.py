"""Tests for A9: Forum topics per client."""
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from src.engine.rules import RulesEngine


@pytest.fixture
def rules_with_topics(tmp_path):
    rules = {
        "assignment_rules": {"design": {"default_assignees": ["101"], "tags": []}},
        "reviewers": {},
        "client_overrides": {
            "client_delta": {"list_id": "list_client_delta", "designer": "101"},
            "client_alpha": {"list_id": "list_hp", "designer": "102"},
        },
        "default_config": {"list_id": "list1", "initial_status": "planejamento"},
        "team_mapping": {
            "101": {"telegram_chat_id": 1001, "name": "Pedro", "role": "designer"},
        },
        "notification_rules": {
            "revisao": {
                "notify_roles": ["designer"],
                "message": "precisa de revisao",
            },
        },
        "telegram_topics": {
            "client_delta": {"topic_id": 12345, "label": "ClientDelta"},
            "client_alpha": {"topic_id": 0, "label": "ClientAlpha"},
            "geral": {"topic_id": 99999, "label": "Geral"},
        },
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


@pytest.fixture
def rules_without_topics(tmp_path):
    rules = {
        "assignment_rules": {},
        "reviewers": {},
        "client_overrides": {},
        "default_config": {"list_id": "list1"},
        "team_mapping": {},
        "notification_rules": {},
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


class TestGetClientTopicId:
    def test_returns_topic_id_for_known_client(self, rules_with_topics):
        assert rules_with_topics.get_client_topic_id("client_delta") == 12345

    def test_returns_none_for_placeholder_zero(self, rules_with_topics):
        assert rules_with_topics.get_client_topic_id("client_alpha") is None

    def test_returns_none_for_unknown_client(self, rules_with_topics):
        assert rules_with_topics.get_client_topic_id("unknown") is None

    def test_returns_none_when_no_topics_section(self, rules_without_topics):
        assert rules_without_topics.get_client_topic_id("client_delta") is None


class TestGetTopicId:
    def test_returns_topic_id_by_name(self, rules_with_topics):
        assert rules_with_topics.get_topic_id("geral") == 99999

    def test_returns_none_for_placeholder_zero(self, rules_with_topics):
        assert rules_with_topics.get_topic_id("client_alpha") is None

    def test_returns_none_for_unknown_topic(self, rules_with_topics):
        assert rules_with_topics.get_topic_id("nonexistent") is None


class TestWebhookHandlerTopicIntegration:
    @pytest.mark.asyncio
    async def test_sends_with_topic_id_when_configured(self, rules_with_topics):
        """A9: send_message includes message_thread_id when topic configured."""
        from src.bot.webhook_handler import WebhookHandler

        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1",
            "name": "Post ClientDelta",
            "assignees": [{"id": 101}],
            "custom_fields": [],
        })
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_with_topics,
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
        kwargs = mock_bot.send_message.call_args[1]
        assert kwargs["message_thread_id"] == 12345

    @pytest.mark.asyncio
    async def test_no_topic_id_when_placeholder(self, rules_with_topics):
        """A9: No message_thread_id when topic_id is 0 (placeholder)."""
        from src.bot.webhook_handler import WebhookHandler

        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1",
            "name": "Post ClientAlpha",
            "assignees": [{"id": 101}],
            "custom_fields": [],
        })
        h = WebhookHandler(
            bot=mock_bot, rules_engine=rules_with_topics,
            webhook_secret="", clickup_client=mock_clickup,
        )
        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list_hp",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 101, "username": "Pedro"},
            }],
        }
        await h.handle_event(event)
        kwargs = mock_bot.send_message.call_args[1]
        assert "message_thread_id" not in kwargs


class TestReviewHandlerTopicIntegration:
    @pytest.mark.asyncio
    async def test_review_sends_with_topic_id(self, rules_with_topics):
        """A9: ReviewHandler sends to client topic."""
        from src.agents.schemas import ContentReview
        from src.bot.review_handler import ReviewHandler

        mock_review = ContentReview(
            checklist=["ok"], issues=[], suggestions=[],
            overall_score=9, summary="Bom.", approved=True,
        )
        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1", "name": "Post ClientDelta",
        })
        mock_clickup.get_comments = AsyncMock(return_value=[])

        review_agent = AsyncMock()
        review_agent.arun = AsyncMock(
            return_value=MagicMock(content=mock_review),
        )

        handler = ReviewHandler(
            review_agent=review_agent,
            clickup_client=mock_clickup,
            rules_engine=rules_with_topics,
            bot=mock_bot,
            group_chat_id=123,
            create_checklist=False,
        )
        # Patch review_content to return our mock
        from unittest.mock import patch
        with patch(
            "src.bot.review_handler.review_content",
            new_callable=AsyncMock,
            return_value=mock_review,
        ):
            await handler.trigger_review("t1", "list_client_delta")

        kwargs = mock_bot.send_message.call_args[1]
        assert kwargs["message_thread_id"] == 12345


class TestSummaryJobTopicIntegration:
    @pytest.mark.asyncio
    async def test_summary_uses_geral_topic(self, rules_with_topics):
        """A9: Summary job sends to 'geral' topic."""
        from unittest.mock import MagicMock, patch

        from src.agents.schemas import DailySummary

        mock_summary = DailySummary(
            resumo="Resumo do dia",
            total_ativas=5,
            total_concluidas=3,
            total_atrasadas=1,
        )
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_context.job = MagicMock()
        mock_context.job.data = {
            "clickup_client": AsyncMock(),
            "rules_engine": rules_with_topics,
            "summary_agent": AsyncMock(),
            "group_chat_id": 123,
        }

        with patch(
            "src.bot.summary_job.collect_task_data",
            new_callable=AsyncMock,
            return_value="data",
        ), patch(
            "src.bot.summary_job.generate_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ):
            from src.bot.summary_job import daily_summary_callback
            await daily_summary_callback(mock_context)

        kwargs = mock_context.bot.send_message.call_args[1]
        assert kwargs["message_thread_id"] == 99999
