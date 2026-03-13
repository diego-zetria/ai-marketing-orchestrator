"""Instagram Graph API v21.0 async client."""

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.facebook.com/v21.0"

# Metrics available per media type (April 2025+: 'views' replaces 'impressions')
_POST_METRICS = "reach,views,saved,shares,likes,comments,total_interactions"
_REELS_METRICS = _POST_METRICS + ",ig_reels_avg_watch_time"
_ACCOUNT_METRICS = "reach,follower_count"
_ACCOUNT_METRICS_TOTAL = "views"


class InstagramClient:
    """Async client for the Instagram Graph API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    async def get_media_list(
        self,
        ig_user_id: str,
        access_token: str,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch recent media with basic metadata.

        Returns list of media dicts with id, caption, media_type, permalink,
        timestamp, like_count, comments_count.
        """
        response = await self._client.get(
            f"{BASE_URL}/{ig_user_id}/media",
            params={
                "fields": (
                    "id,caption,media_type,media_url,permalink,"
                    "timestamp,like_count,comments_count"
                ),
                "limit": limit,
                "access_token": access_token,
            },
        )
        if response.status_code >= 400:
            logger.error(
                "Instagram API error %s fetching media for %s: %s",
                response.status_code,
                ig_user_id,
                response.text,
            )
        response.raise_for_status()
        return response.json().get("data", [])

    async def get_media_insights(
        self,
        media_id: str,
        access_token: str,
        media_type: str = "IMAGE",
    ) -> dict:
        """Fetch insights for a specific media item.

        Returns a flat dict: {"reach": 1250, "views": 3420, "saves": 47, ...}
        For VIDEO (Reels), includes "avg_watch_time_s".
        """
        metrics = _REELS_METRICS if media_type == "VIDEO" else _POST_METRICS
        response = await self._client.get(
            f"{BASE_URL}/{media_id}/insights",
            params={
                "metric": metrics,
                "access_token": access_token,
            },
        )
        if response.status_code >= 400:
            logger.error(
                "Instagram API error %s fetching insights for media %s: %s",
                response.status_code,
                media_id,
                response.text,
            )
        response.raise_for_status()

        result: dict = {}
        for item in response.json().get("data", []):
            name = item["name"]
            value = item["values"][0]["value"] if item.get("values") else 0
            if name == "saved":
                result["saves"] = value
            elif name == "ig_reels_avg_watch_time":
                result["avg_watch_time_s"] = value
            else:
                result[name] = value
        return result

    async def get_account_insights(
        self,
        ig_user_id: str,
        access_token: str,
        since: datetime,
        until: datetime,
    ) -> list[dict]:
        """Fetch account-level daily insights for a date range.

        Returns raw API response data list (reach, views, follower_count with
        daily values).
        """
        # Fetch day-period metrics (reach, follower_count)
        resp1 = await self._client.get(
            f"{BASE_URL}/{ig_user_id}/insights",
            params={
                "metric": _ACCOUNT_METRICS,
                "period": "day",
                "since": int(since.timestamp()),
                "until": int(until.timestamp()),
                "access_token": access_token,
            },
        )
        if resp1.status_code >= 400:
            logger.error(
                "Instagram API error %s fetching account insights for %s: %s",
                resp1.status_code, ig_user_id, resp1.text,
            )
        resp1.raise_for_status()
        data = resp1.json().get("data", [])

        # Fetch total_value metrics (views) separately
        try:
            resp2 = await self._client.get(
                f"{BASE_URL}/{ig_user_id}/insights",
                params={
                    "metric": _ACCOUNT_METRICS_TOTAL,
                    "metric_type": "total_value",
                    "period": "day",
                    "since": int(since.timestamp()),
                    "until": int(until.timestamp()),
                    "access_token": access_token,
                },
            )
            if resp2.status_code < 400:
                data.extend(resp2.json().get("data", []))
        except Exception:
            logger.warning("Failed to fetch total_value metrics for %s", ig_user_id)

        return data

    async def refresh_token(self, access_token: str) -> dict:
        """Refresh a long-lived token. Must be >24h old and <60 days.

        Returns {"access_token": "...", "token_type": "bearer", "expires_in": 5184000}.
        """
        response = await self._client.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": access_token,
            },
        )
        if response.status_code >= 400:
            logger.error(
                "Instagram API error %s refreshing token: %s",
                response.status_code,
                response.text,
            )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def parse_rate_limit_usage(
        usage_header: dict,
        ig_user_id: str,
    ) -> float:
        """Parse X-Business-Use-Case-Usage header.

        Returns acc_id_util_pct (0-100) for the given account.
        """
        entries = usage_header.get(ig_user_id, [])
        for entry in entries:
            if entry.get("type") == "IG_INSIGHTS":
                return entry.get("acc_id_util_pct", 0.0)
        return 0.0
