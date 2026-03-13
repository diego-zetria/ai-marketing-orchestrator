"""Tests for transition logger (A10 data collection)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.transition_logger import log_transition


@pytest.fixture
def mock_session_factory():
    """Create a mock async session factory."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    # Make the context manager work
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_factory, mock_session


class TestLogTransition:
    @pytest.mark.asyncio
    async def test_inserts_transition(self, mock_session_factory):
        factory, session = mock_session_factory

        await log_transition(
            factory,
            task_id="t1",
            task_name="Post Instagram",
            list_id="list1",
            client_name="ClientDelta",
            from_status="revisao",
            to_status="aprovado",
            changed_by_id="201",
            changed_by_name="Luis",
        )

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

        # Check the params passed to execute
        call_args = session.execute.call_args
        params = call_args[0][1]
        assert params["task_id"] == "t1"
        assert params["from_status"] == "revisao"
        assert params["to_status"] == "aprovado"
        assert params["changed_by_id"] == "201"

    @pytest.mark.asyncio
    async def test_handles_empty_optional_fields(self, mock_session_factory):
        factory, session = mock_session_factory

        await log_transition(
            factory,
            task_id="t2",
            from_status="em criacao",
            to_status="revisao",
        )

        session.execute.assert_awaited_once()
        params = session.execute.call_args[0][1]
        assert params["task_name"] == ""
        assert params["client_name"] == ""
        assert params["changed_by_id"] == ""

    @pytest.mark.asyncio
    async def test_db_error_doesnt_crash(self, mock_session_factory):
        factory, session = mock_session_factory
        session.execute.side_effect = Exception("DB connection failed")

        # Should not raise
        await log_transition(
            factory,
            task_id="t3",
            from_status="a",
            to_status="b",
        )

    @pytest.mark.asyncio
    async def test_commit_error_doesnt_crash(self, mock_session_factory):
        factory, session = mock_session_factory
        session.commit.side_effect = Exception("Commit failed")

        await log_transition(
            factory,
            task_id="t4",
            from_status="a",
            to_status="b",
        )


class TestWebhookTransitionLogging:
    """Test that WebhookHandler fires transition logging."""

    @pytest.mark.asyncio
    async def test_status_update_logs_transition(self):
        """WebhookHandler._handle_status_updated creates log task."""
        from src.bot.webhook_handler import WebhookHandler

        mock_bot = AsyncMock()
        mock_rules = MagicMock()
        mock_rules.get_notification_rules.return_value = None
        mock_rules.get_client_by_list_id.return_value = "ClientDelta"

        mock_factory = MagicMock()

        handler = WebhookHandler(
            bot=mock_bot,
            rules_engine=mock_rules,
            session_factory=mock_factory,
        )

        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list1",
            "history_items": [{
                "field": "status",
                "before": {"status": "em criacao"},
                "after": {"status": "revisao"},
                "user": {"id": 201, "username": "Luis"},
            }],
        }

        created_tasks = []

        with patch.object(handler, "_safe_log_transition", new_callable=AsyncMock) as mock_log:
            with patch("src.bot.webhook_handler.asyncio") as mock_asyncio:
                mock_asyncio.create_task = lambda coro: created_tasks.append(coro)
                await handler._handle_status_updated(event)

            # The coroutine was scheduled — run it now
            assert len(created_tasks) == 1
            await created_tasks[0]

            mock_log.assert_awaited_once()
            kwargs = mock_log.call_args[1]
            assert kwargs["task_id"] == "t1"
            assert kwargs["from_status"] == "em criacao"
            assert kwargs["to_status"] == "revisao"

    @pytest.mark.asyncio
    async def test_no_session_factory_skips_logging(self):
        """When session_factory is None, no logging is attempted."""
        from src.bot.webhook_handler import WebhookHandler

        mock_bot = AsyncMock()
        mock_rules = MagicMock()
        mock_rules.get_notification_rules.return_value = None

        handler = WebhookHandler(
            bot=mock_bot,
            rules_engine=mock_rules,
            session_factory=None,  # No DB
        )

        event = {
            "event": "taskStatusUpdated",
            "task_id": "t1",
            "list_id": "list1",
            "history_items": [{
                "field": "status",
                "before": {"status": "a"},
                "after": {"status": "b"},
                "user": {"id": 1},
            }],
        }

        # Should not raise, and no logging attempted
        await handler._handle_status_updated(event)
