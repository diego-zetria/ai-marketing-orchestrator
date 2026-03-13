"""Tests for the Instagram Graph API client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.integrations.instagram.client import InstagramClient


@pytest.fixture
def client():
    return InstagramClient()


@pytest.mark.asyncio
async def test_get_media_list(client):
    mock_response = httpx.Response(
        200,
        json={
            "data": [
                {
                    "id": "17895695668004550",
                    "caption": "Dica da semana #5",
                    "media_type": "CAROUSEL_ALBUM",
                    "permalink": "https://www.instagram.com/p/ABC123/",
                    "timestamp": "2026-03-03T12:00:00+0000",
                    "like_count": 45,
                    "comments_count": 12,
                },
                {
                    "id": "17895695668004551",
                    "caption": "Bastidores producao",
                    "media_type": "VIDEO",
                    "permalink": "https://www.instagram.com/p/DEF456/",
                    "timestamp": "2026-03-05T14:00:00+0000",
                    "like_count": 30,
                    "comments_count": 5,
                },
            ],
            "paging": {"cursors": {"after": "abc123"}},
        },
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/123/media"),
    )
    with patch.object(
        client._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_media_list("123", "token123", limit=25)
    assert len(result) == 2
    assert result[0]["id"] == "17895695668004550"
    assert result[0]["media_type"] == "CAROUSEL_ALBUM"


@pytest.mark.asyncio
async def test_get_media_insights(client):
    mock_response = httpx.Response(
        200,
        json={
            "data": [
                {"name": "reach", "values": [{"value": 1250}]},
                {"name": "views", "values": [{"value": 3420}]},
                {"name": "saved", "values": [{"value": 47}]},
                {"name": "shares", "values": [{"value": 15}]},
                {"name": "likes", "values": [{"value": 200}]},
                {"name": "comments", "values": [{"value": 35}]},
                {"name": "total_interactions", "values": [{"value": 297}]},
            ],
        },
        request=httpx.Request(
            "GET", "https://graph.facebook.com/v21.0/media1/insights"
        ),
    )
    with patch.object(
        client._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_media_insights("media1", "token123")
    assert result["reach"] == 1250
    assert result["views"] == 3420
    assert result["saves"] == 47
    assert result["total_interactions"] == 297


@pytest.mark.asyncio
async def test_get_media_insights_reels(client):
    mock_response = httpx.Response(
        200,
        json={
            "data": [
                {"name": "reach", "values": [{"value": 800}]},
                {"name": "views", "values": [{"value": 2000}]},
                {"name": "saved", "values": [{"value": 20}]},
                {"name": "shares", "values": [{"value": 10}]},
                {"name": "likes", "values": [{"value": 100}]},
                {"name": "comments", "values": [{"value": 15}]},
                {"name": "total_interactions", "values": [{"value": 145}]},
                {"name": "ig_reels_avg_watch_time", "values": [{"value": 8.5}]},
            ],
        },
        request=httpx.Request(
            "GET", "https://graph.facebook.com/v21.0/media2/insights"
        ),
    )
    with patch.object(
        client._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_media_insights(
            "media2", "token123", media_type="VIDEO"
        )
    assert result["reach"] == 800
    assert result["avg_watch_time_s"] == 8.5


@pytest.mark.asyncio
async def test_get_account_insights(client):
    # First call: day-period metrics (reach, follower_count)
    day_response = httpx.Response(
        200,
        json={
            "data": [
                {
                    "name": "reach",
                    "period": "day",
                    "values": [
                        {"value": 1200, "end_time": "2026-03-01T08:00:00+0000"},
                        {"value": 1350, "end_time": "2026-03-02T08:00:00+0000"},
                    ],
                },
                {
                    "name": "follower_count",
                    "period": "day",
                    "values": [
                        {"value": 5000, "end_time": "2026-03-01T08:00:00+0000"},
                        {"value": 5010, "end_time": "2026-03-02T08:00:00+0000"},
                    ],
                },
            ],
        },
        request=httpx.Request(
            "GET", "https://graph.facebook.com/v21.0/123/insights"
        ),
    )
    # Second call: total_value metrics (views)
    total_response = httpx.Response(
        200,
        json={
            "data": [
                {
                    "name": "views",
                    "period": "day",
                    "values": [
                        {"value": 3000, "end_time": "2026-03-01T08:00:00+0000"},
                        {"value": 3200, "end_time": "2026-03-02T08:00:00+0000"},
                    ],
                },
            ],
        },
        request=httpx.Request(
            "GET", "https://graph.facebook.com/v21.0/123/insights"
        ),
    )
    since = datetime(2026, 3, 1, tzinfo=timezone.utc)
    until = datetime(2026, 3, 3, tzinfo=timezone.utc)
    with patch.object(
        client._client, "get", new_callable=AsyncMock,
        side_effect=[day_response, total_response],
    ):
        result = await client.get_account_insights("123", "token123", since, until)
    assert len(result) == 3  # reach, follower_count + views
    assert result[0]["name"] == "reach"


@pytest.mark.asyncio
async def test_refresh_token(client):
    mock_response = httpx.Response(
        200,
        json={
            "access_token": "new_long_lived_token",
            "token_type": "bearer",
            "expires_in": 5184000,
        },
        request=httpx.Request(
            "GET", "https://graph.instagram.com/refresh_access_token"
        ),
    )
    with patch.object(
        client._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.refresh_token("old_token")
    assert result["access_token"] == "new_long_lived_token"
    assert result["expires_in"] == 5184000


@pytest.mark.asyncio
async def test_get_media_list_api_error(client):
    mock_response = httpx.Response(
        400,
        json={"error": {"message": "Invalid token", "code": 190}},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/123/media"),
    )
    with patch.object(
        client._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_media_list("123", "bad_token")


@pytest.mark.asyncio
async def test_parse_rate_limit_header(client):
    usage = {
        "123": [
            {"type": "IG_INSIGHTS", "call_count": 28, "acc_id_util_pct": 14.0}
        ]
    }
    pct = client.parse_rate_limit_usage(usage, "123")
    assert pct == 14.0


def test_parse_rate_limit_header_missing(client):
    pct = client.parse_rate_limit_usage({}, "unknown")
    assert pct == 0.0
