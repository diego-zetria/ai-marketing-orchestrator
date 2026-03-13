"""Tests for Instagram sync jobs."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.instagram_sync import (
    _get_connected_accounts,
    _upsert_account_insights,
    _upsert_media_insights,
    auto_match_posts,
    refresh_expired_tokens,
    sync_account_insights,
    sync_instagram_media,
)


def _make_session_factory(mock_session):
    """Build an async context-manager session factory from a mock session.

    session_factory() must be a regular call (not a coroutine) that returns
    an async context manager -- matching sqlalchemy async_sessionmaker behavior.
    """

    class _FakeCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    return MagicMock(side_effect=lambda: _FakeCtx())


@pytest.mark.asyncio
async def test_get_connected_accounts():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(
            client_name="ClientDelta",
            ig_user_id="123",
            access_token="token_client_delta",
            token_expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = _make_session_factory(mock_session)

    accounts = await _get_connected_accounts(mock_factory)
    assert len(accounts) == 1
    assert accounts[0].client_name == "ClientDelta"


@pytest.mark.asyncio
async def test_upsert_media_insights():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_factory = _make_session_factory(mock_session)

    media_rows = [
        {
            "ig_media_id": "m1",
            "client_name": "ClientDelta",
            "media_type": "IMAGE",
            "caption": "Test",
            "permalink": "https://instagram.com/p/123",
            "published_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
            "reach": 1000,
            "views": 2000,
            "likes": 100,
            "comments": 20,
            "saves": 30,
            "shares": 10,
            "total_interactions": 160,
            "avg_watch_time_s": None,
            "clickup_task_id": None,
        },
    ]
    await _upsert_media_insights(mock_factory, media_rows)
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_upsert_media_insights_empty_list():
    mock_factory = AsyncMock()
    await _upsert_media_insights(mock_factory, [])
    # Factory should never be called for empty list
    mock_factory.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_account_insights():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_factory = _make_session_factory(mock_session)

    rows = [
        {
            "client_name": "ClientDelta",
            "date": datetime(2026, 3, 1).date().isoformat(),
            "reach": 1200,
            "views": 3000,
            "follower_count": 5000,
        },
    ]
    await _upsert_account_insights(mock_factory, rows)
    assert mock_session.execute.called


def test_auto_match_posts_exact_date():
    clickup_tasks = [
        {
            "id": "task1",
            "name": "03/03 - POST Dica da semana",
            "due_date": str(
                int(datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp() * 1000)
            ),
            "status": {"status": "pronto"},
        },
    ]
    ig_posts = [
        {
            "ig_media_id": "m1",
            "published_at": datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc),
            "media_type": "IMAGE",
        },
    ]
    matches = auto_match_posts(clickup_tasks, ig_posts)
    assert matches == {"m1": "task1"}


def test_auto_match_posts_one_day_tolerance():
    clickup_tasks = [
        {
            "id": "task1",
            "name": "03/03 - POST Dica",
            "due_date": str(
                int(datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp() * 1000)
            ),
            "status": {"status": "pronto"},
        },
    ]
    ig_posts = [
        {
            "ig_media_id": "m1",
            "published_at": datetime(2026, 3, 4, 10, 0, tzinfo=timezone.utc),
            "media_type": "IMAGE",
        },
    ]
    matches = auto_match_posts(clickup_tasks, ig_posts)
    assert matches == {"m1": "task1"}


def test_auto_match_posts_no_match():
    clickup_tasks = [
        {
            "id": "task1",
            "name": "03/03 - POST Dica",
            "due_date": str(
                int(datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp() * 1000)
            ),
            "status": {"status": "pronto"},
        },
    ]
    ig_posts = [
        {
            "ig_media_id": "m1",
            "published_at": datetime(2026, 3, 10, tzinfo=timezone.utc),
            "media_type": "IMAGE",
        },
    ]
    matches = auto_match_posts(clickup_tasks, ig_posts)
    assert matches == {}


def test_auto_match_prefers_exact_date():
    clickup_tasks = [
        {
            "id": "task1",
            "name": "03/03 - POST A",
            "due_date": str(
                int(datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp() * 1000)
            ),
            "status": {"status": "pronto"},
        },
        {
            "id": "task2",
            "name": "04/03 - POST B",
            "due_date": str(
                int(datetime(2026, 3, 4, tzinfo=timezone.utc).timestamp() * 1000)
            ),
            "status": {"status": "pronto"},
        },
    ]
    ig_posts = [
        {
            "ig_media_id": "m1",
            "published_at": datetime(2026, 3, 3, 15, 0, tzinfo=timezone.utc),
            "media_type": "IMAGE",
        },
    ]
    matches = auto_match_posts(clickup_tasks, ig_posts)
    assert matches == {"m1": "task1"}


def test_auto_match_posts_string_date():
    """auto_match_posts handles published_at as an ISO string."""
    clickup_tasks = [
        {
            "id": "task1",
            "due_date": str(
                int(datetime(2026, 3, 3, tzinfo=timezone.utc).timestamp() * 1000)
            ),
        },
    ]
    ig_posts = [
        {
            "ig_media_id": "m1",
            "published_at": "2026-03-03T12:00:00+00:00",
            "media_type": "IMAGE",
        },
    ]
    matches = auto_match_posts(clickup_tasks, ig_posts)
    assert matches == {"m1": "task1"}


def test_auto_match_posts_no_due_date():
    """Tasks without due_date are skipped."""
    clickup_tasks = [{"id": "task1"}]
    ig_posts = [
        {
            "ig_media_id": "m1",
            "published_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
            "media_type": "IMAGE",
        },
    ]
    matches = auto_match_posts(clickup_tasks, ig_posts)
    assert matches == {}


@pytest.mark.asyncio
async def test_refresh_expired_tokens():
    now = datetime.now(tz=timezone.utc)
    mock_ig_client = MagicMock()
    mock_ig_client.refresh_token = AsyncMock(
        return_value={
            "access_token": "new_token",
            "expires_in": 5184000,
        }
    )

    mock_session = AsyncMock()
    # Simulate one account expiring in 5 days
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        MagicMock(
            client_name="ClientDelta",
            access_token="old_token",
            token_expires_at=now + timedelta(days=5),
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_factory = _make_session_factory(mock_session)

    refreshed = await refresh_expired_tokens(mock_ig_client, mock_factory)
    assert refreshed == 1
    mock_ig_client.refresh_token.assert_called_once_with("old_token")


@pytest.mark.asyncio
async def test_refresh_expired_tokens_none_expiring():
    mock_ig_client = MagicMock()
    mock_ig_client.refresh_token = AsyncMock()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_factory = _make_session_factory(mock_session)

    refreshed = await refresh_expired_tokens(mock_ig_client, mock_factory)
    assert refreshed == 0
    mock_ig_client.refresh_token.assert_not_called()
    # commit should NOT be called when nothing was refreshed
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_sync_instagram_media_basic():
    mock_ig_client = MagicMock()
    mock_ig_client.get_media_list = AsyncMock(
        return_value=[
            {
                "id": "m1",
                "media_type": "IMAGE",
                "caption": "Test post",
                "permalink": "https://instagram.com/p/abc",
                "timestamp": "2026-03-03T12:00:00+0000",
            },
        ]
    )
    mock_ig_client.get_media_insights = AsyncMock(
        return_value={
            "reach": 500,
            "views": 1000,
            "likes": 50,
            "comments": 10,
            "saves": 15,
            "shares": 5,
            "total_interactions": 80,
        }
    )

    # Session factory for _get_connected_accounts
    mock_session_accts = AsyncMock()
    mock_result_accts = MagicMock()
    mock_result_accts.fetchall.return_value = [
        MagicMock(
            client_name="ClientDelta",
            ig_user_id="123",
            access_token="token_client_delta",
            token_expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ig_username="client_delta_oficial",
            page_id="page1",
        ),
    ]
    mock_session_accts.execute = AsyncMock(return_value=mock_result_accts)

    # Session factory for _upsert_media_insights
    mock_session_upsert = AsyncMock()
    mock_session_upsert.execute = AsyncMock()
    mock_session_upsert.commit = AsyncMock()

    call_count = 0

    class _FakeCtx:
        async def __aenter__(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_session_accts
            return mock_session_upsert

        async def __aexit__(self, *args):
            pass

    mock_factory = MagicMock(side_effect=lambda: _FakeCtx())

    count = await sync_instagram_media(mock_ig_client, mock_factory)
    assert count == 1
    mock_ig_client.get_media_list.assert_called_once()
    mock_ig_client.get_media_insights.assert_called_once()


@pytest.mark.asyncio
async def test_sync_account_insights_basic():
    mock_ig_client = MagicMock()
    mock_ig_client.get_account_insights = AsyncMock(
        return_value=[
            {
                "name": "reach",
                "values": [
                    {"value": 1200, "end_time": "2026-03-01T08:00:00+0000"},
                ],
            },
            {
                "name": "views",
                "values": [
                    {"value": 3000, "end_time": "2026-03-01T08:00:00+0000"},
                ],
            },
            {
                "name": "follower_count",
                "values": [
                    {"value": 5000, "end_time": "2026-03-01T08:00:00+0000"},
                ],
            },
        ]
    )

    # Session factory for _get_connected_accounts
    mock_session_accts = AsyncMock()
    mock_result_accts = MagicMock()
    mock_result_accts.fetchall.return_value = [
        MagicMock(
            client_name="ClientDelta",
            ig_user_id="123",
            access_token="token_client_delta",
            token_expires_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ig_username="client_delta_oficial",
            page_id="page1",
        ),
    ]
    mock_session_accts.execute = AsyncMock(return_value=mock_result_accts)

    # Session factory for _upsert_account_insights
    mock_session_upsert = AsyncMock()
    mock_session_upsert.execute = AsyncMock()
    mock_session_upsert.commit = AsyncMock()

    call_count = 0

    class _FakeCtx:
        async def __aenter__(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_session_accts
            return mock_session_upsert

        async def __aexit__(self, *args):
            pass

    mock_factory = MagicMock(side_effect=lambda: _FakeCtx())

    count = await sync_account_insights(mock_ig_client, mock_factory)
    assert count == 1  # 1 date row
    mock_ig_client.get_account_insights.assert_called_once()
