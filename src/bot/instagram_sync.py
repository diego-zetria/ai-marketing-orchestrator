"""F5.2: Instagram data sync jobs -- media insights, account insights, token refresh."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from telegram.ext import ContextTypes

from src.integrations.instagram.client import InstagramClient

logger = logging.getLogger(__name__)

SCHEMA = "marketing_bot"

_QUERY_CONNECTED_ACCOUNTS = f"""
SELECT client_name, ig_user_id, access_token, token_expires_at, ig_username, page_id
FROM {SCHEMA}.instagram_accounts
"""

_QUERY_EXPIRING_TOKENS = f"""
SELECT client_name, access_token, token_expires_at
FROM {SCHEMA}.instagram_accounts
WHERE token_expires_at < :threshold
"""

_UPSERT_MEDIA = f"""
INSERT INTO {SCHEMA}.media_insights (
    ig_media_id, client_name, media_type, caption, permalink,
    published_at, reach, views, likes, comments, saves, shares,
    total_interactions, avg_watch_time_s, clickup_task_id, synced_at
) VALUES (
    :ig_media_id, :client_name, :media_type, :caption, :permalink,
    :published_at, :reach, :views, :likes, :comments, :saves, :shares,
    :total_interactions, :avg_watch_time_s, :clickup_task_id, NOW()
)
ON CONFLICT (ig_media_id) DO UPDATE SET
    reach = EXCLUDED.reach,
    views = EXCLUDED.views,
    likes = EXCLUDED.likes,
    comments = EXCLUDED.comments,
    saves = EXCLUDED.saves,
    shares = EXCLUDED.shares,
    total_interactions = EXCLUDED.total_interactions,
    avg_watch_time_s = EXCLUDED.avg_watch_time_s,
    clickup_task_id = COALESCE(EXCLUDED.clickup_task_id, {SCHEMA}.media_insights.clickup_task_id),
    synced_at = NOW()
"""

_UPSERT_ACCOUNT = f"""
INSERT INTO {SCHEMA}.account_insights (
    client_name, date, reach, views, follower_count, synced_at
) VALUES (
    :client_name, :date, :reach, :views, :follower_count, NOW()
)
ON CONFLICT (client_name, date) DO UPDATE SET
    reach = EXCLUDED.reach,
    views = EXCLUDED.views,
    follower_count = EXCLUDED.follower_count,
    synced_at = NOW()
"""

_UPDATE_TOKEN = f"""
UPDATE {SCHEMA}.instagram_accounts
SET access_token = :new_token, token_expires_at = :new_expires, updated_at = NOW()
WHERE client_name = :client_name
"""


async def _get_connected_accounts(session_factory):
    """Fetch all connected Instagram accounts from DB."""
    async with session_factory() as session:
        result = await session.execute(text(_QUERY_CONNECTED_ACCOUNTS))
        return result.fetchall()


async def _upsert_media_insights(session_factory, rows: list[dict]) -> None:
    """Upsert media insights rows into DB."""
    if not rows:
        return
    async with session_factory() as session:
        for row in rows:
            await session.execute(text(_UPSERT_MEDIA), row)
        await session.commit()


async def _upsert_account_insights(session_factory, rows: list[dict]) -> None:
    """Upsert account insights rows into DB."""
    if not rows:
        return
    async with session_factory() as session:
        for row in rows:
            await session.execute(text(_UPSERT_ACCOUNT), row)
        await session.commit()


def auto_match_posts(
    clickup_tasks: list[dict], ig_posts: list[dict]
) -> dict[str, str]:
    """Match IG posts to ClickUp tasks by date (+-1 day tolerance).

    Returns {ig_media_id: clickup_task_id} for matched posts.
    Prefers exact date matches over +-1 day.
    """
    matches: dict[str, str] = {}

    for post in ig_posts:
        pub_dt = post["published_at"]
        if isinstance(pub_dt, str):
            pub_dt = datetime.fromisoformat(pub_dt)
        pub_date = pub_dt.date()

        best_task_id = None
        best_diff = None

        for task in clickup_tasks:
            due_ms = task.get("due_date")
            if not due_ms:
                continue
            due_dt = datetime.fromtimestamp(int(due_ms) / 1000, tz=timezone.utc)
            diff = abs((pub_date - due_dt.date()).days)
            if diff <= 1:
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_task_id = task["id"]

        if best_task_id:
            matches[post["ig_media_id"]] = best_task_id

    return matches


async def sync_instagram_media(
    ig_client: InstagramClient,
    session_factory,
    clickup_client=None,
    rules_engine=None,
    team_id: str = "",
) -> int:
    """Sync media + insights for all connected accounts. Returns count of posts synced."""
    accounts = await _get_connected_accounts(session_factory)
    total_synced = 0

    for acct in accounts:
        try:
            media_list = await ig_client.get_media_list(
                acct.ig_user_id,
                acct.access_token,
                limit=50,
            )

            rows = []
            for media in media_list:
                media_type = media.get("media_type", "IMAGE")
                try:
                    insights = await ig_client.get_media_insights(
                        media["id"],
                        acct.access_token,
                        media_type=media_type,
                    )
                except Exception:
                    logger.warning(
                        "Failed to fetch insights for media %s", media["id"]
                    )
                    insights = {}

                published_at = datetime.fromisoformat(
                    media["timestamp"].replace("+0000", "+00:00")
                )

                rows.append(
                    {
                        "ig_media_id": media["id"],
                        "client_name": acct.client_name,
                        "media_type": media_type,
                        "caption": media.get("caption", ""),
                        "permalink": media.get("permalink", ""),
                        "published_at": published_at,
                        "reach": insights.get("reach", 0),
                        "views": insights.get("views", 0),
                        "likes": insights.get("likes", 0),
                        "comments": insights.get("comments", 0),
                        "saves": insights.get("saves", 0),
                        "shares": insights.get("shares", 0),
                        "total_interactions": insights.get("total_interactions", 0),
                        "avg_watch_time_s": insights.get("avg_watch_time_s"),
                        "clickup_task_id": None,
                    }
                )

            # Auto-match to ClickUp tasks
            if clickup_client and rules_engine and team_id:
                try:
                    now = datetime.now(tz=timezone.utc)
                    three_months_ago_ms = int(
                        (now - timedelta(days=90)).timestamp() * 1000
                    )
                    now_ms = int(now.timestamp() * 1000)
                    tasks = await clickup_client.get_filtered_team_tasks(
                        team_id=team_id,
                        date_done_gt=three_months_ago_ms,
                        date_done_lt=now_ms,
                    )
                    client_list_ids = set()
                    for cn in rules_engine.get_all_clients():
                        cfg = rules_engine.get_client_config(cn)
                        if (
                            cfg.get("list_id")
                            and cn.lower() == acct.client_name.lower()
                        ):
                            client_list_ids.add(cfg["list_id"])

                    client_tasks = [
                        t
                        for t in tasks
                        if t.get("list", {}).get("id", "") in client_list_ids
                    ]
                    matches = auto_match_posts(client_tasks, rows)
                    for row in rows:
                        mid = row["ig_media_id"]
                        if mid in matches:
                            row["clickup_task_id"] = matches[mid]
                except Exception:
                    logger.exception(
                        "Failed to auto-match IG posts for %s", acct.client_name
                    )

            await _upsert_media_insights(session_factory, rows)
            total_synced += len(rows)
            logger.info(
                "Synced %d media insights for %s",
                len(rows),
                acct.client_name,
            )
        except Exception:
            logger.exception("Failed to sync media for %s", acct.client_name)

    return total_synced


async def sync_account_insights(
    ig_client: InstagramClient,
    session_factory,
) -> int:
    """Sync daily account insights for all connected accounts. Returns count synced."""
    accounts = await _get_connected_accounts(session_factory)
    total_synced = 0

    for acct in accounts:
        try:
            now = datetime.now(tz=timezone.utc)
            since = now - timedelta(days=2)

            raw_data = await ig_client.get_account_insights(
                acct.ig_user_id,
                acct.access_token,
                since,
                now,
            )

            # Parse the nested response into flat rows per date
            date_metrics: dict[str, dict] = {}
            for metric in raw_data:
                name = metric["name"]
                for val in metric.get("values", []):
                    end_time = val.get("end_time", "")
                    if end_time:
                        dt = datetime.fromisoformat(
                            end_time.replace("+0000", "+00:00")
                        )
                        date_key = dt.date().isoformat()
                        date_metrics.setdefault(date_key, {})[name] = val["value"]

            rows = []
            for date_str, metrics in date_metrics.items():
                rows.append(
                    {
                        "client_name": acct.client_name,
                        "date": datetime.fromisoformat(date_str).date(),
                        "reach": metrics.get("reach", 0),
                        "views": metrics.get("views", 0),
                        "follower_count": metrics.get("follower_count", 0),
                    }
                )

            await _upsert_account_insights(session_factory, rows)
            total_synced += len(rows)
            logger.info(
                "Synced %d account insight days for %s",
                len(rows),
                acct.client_name,
            )
        except Exception:
            logger.exception(
                "Failed to sync account insights for %s", acct.client_name
            )

    return total_synced


async def refresh_expired_tokens(
    ig_client: InstagramClient,
    session_factory,
    days_threshold: int = 10,
) -> int:
    """Refresh tokens expiring within days_threshold days. Returns count refreshed."""
    threshold = datetime.now(tz=timezone.utc) + timedelta(days=days_threshold)
    refreshed = 0

    async with session_factory() as session:
        result = await session.execute(
            text(_QUERY_EXPIRING_TOKENS),
            {"threshold": threshold},
        )
        expiring = result.fetchall()

        for acct in expiring:
            try:
                data = await ig_client.refresh_token(acct.access_token)
                new_expires = datetime.now(tz=timezone.utc) + timedelta(
                    seconds=data["expires_in"]
                )
                await session.execute(
                    text(_UPDATE_TOKEN),
                    {
                        "new_token": data["access_token"],
                        "new_expires": new_expires,
                        "client_name": acct.client_name,
                    },
                )
                refreshed += 1
                logger.info("Refreshed Instagram token for %s", acct.client_name)
            except Exception:
                logger.exception(
                    "Failed to refresh token for %s", acct.client_name
                )

        if refreshed > 0:
            await session.commit()

    return refreshed


# --- JobQueue callbacks (registered in main.py) ---


async def sync_media_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: sync Instagram media for all connected accounts."""
    data = context.job.data
    try:
        count = await sync_instagram_media(
            ig_client=data["ig_client"],
            session_factory=data["session_factory"],
            clickup_client=data.get("clickup_client"),
            rules_engine=data.get("rules_engine"),
            team_id=data.get("team_id", ""),
        )
        logger.info("Instagram media sync complete: %d posts", count)
    except Exception:
        logger.exception("Instagram media sync failed")


async def sync_account_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: sync Instagram account insights daily."""
    data = context.job.data
    try:
        count = await sync_account_insights(
            ig_client=data["ig_client"],
            session_factory=data["session_factory"],
        )
        logger.info("Instagram account sync complete: %d days", count)
    except Exception:
        logger.exception("Instagram account sync failed")


async def refresh_tokens_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: refresh tokens expiring within 10 days."""
    data = context.job.data
    try:
        count = await refresh_expired_tokens(
            ig_client=data["ig_client"],
            session_factory=data["session_factory"],
        )
        if count > 0:
            logger.info("Refreshed %d Instagram token(s)", count)
    except Exception:
        logger.exception("Instagram token refresh failed")
