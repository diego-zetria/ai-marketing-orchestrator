"""Approval Reminder Lambda handler.

Triggered daily by EventBridge cron to send reminder emails for pending
approval assets that have exceeded the configured day thresholds (2 and 5 days).

Flow:
1. Initialize services (same Lambda reuse pattern)
2. Check for pending assets at 2-day and 5-day thresholds
3. For each asset:
   a. Check if reminder was already sent today (avoid duplicates)
   b. Find active magic link for the asset
   c. Get thumbnail URL from latest version
   d. Send reminder email via EmailService
   e. Log "reminder_sent" event
4. Commit and return count
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.approval.models import ApprovalAsset, ApprovalEvent, AssetVersion, MagicLink
from src.approval.repository import get_pending_assets_older_than, log_event
from src.approval.services.email import EmailService
from src.approval.services.media import MediaService
from src.approval.services.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REMINDER_THRESHOLDS = [2, 5]

# ---------------------------------------------------------------------------
# Global singletons (Lambda container reuse pattern)
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None
_email_service: EmailService | None = None
_media_service: MediaService | None = None
_whatsapp_service: WhatsAppService | None = None


def _init_services() -> None:
    """Lazy-initialise shared services on first invocation."""
    global _engine, _session_factory, _email_service, _media_service, _whatsapp_service

    if _session_factory is not None:
        return

    database_url = os.environ["DATABASE_URL"]
    _engine = create_async_engine(database_url, echo=False)
    _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    _email_service = EmailService(
        from_email=os.environ["SES_FROM_EMAIL"],
        portal_domain=os.environ["PORTAL_DOMAIN"],
    )

    _media_service = MediaService(bucket=os.environ["MEDIA_BUCKET"])

    wa_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    wa_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    if wa_phone_id and wa_token:
        _whatsapp_service = WhatsAppService(
            phone_number_id=wa_phone_id,
            access_token=wa_token,
            portal_domain=os.environ["PORTAL_DOMAIN"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _was_reminded_today(session: AsyncSession, asset_id: object) -> bool:
    """Check if a 'reminder_sent' event was already logged today for this asset."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(ApprovalEvent).where(
        ApprovalEvent.asset_id == asset_id,
        ApprovalEvent.event_type == "reminder_sent",
        ApprovalEvent.created_at >= today_start,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _find_active_magic_link(session: AsyncSession, asset_id: object) -> MagicLink | None:
    """Find an active, non-expired magic link for the given asset."""
    now = datetime.now(timezone.utc)
    stmt = select(MagicLink).where(
        MagicLink.asset_id == asset_id,
        MagicLink.is_active.is_(True),
        MagicLink.expires_at > now,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_latest_version(session: AsyncSession, asset_id: object) -> AssetVersion | None:
    """Get the latest version (by version_number) for an asset."""
    stmt = (
        select(AssetVersion)
        .where(AssetVersion.asset_id == asset_id)
        .order_by(AssetVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _get_thumbnail_presigned_url(version: AssetVersion | None) -> str:
    """Generate a presigned URL for the thumbnail, or return empty string."""
    assert _media_service is not None

    if version is None or not version.thumbnail_url:
        return ""

    # thumbnail_url is stored as s3://bucket/key — extract the key
    s3_url = version.thumbnail_url
    if s3_url.startswith("s3://"):
        parts = s3_url[5:]  # remove "s3://"
        # First part is bucket, rest is key
        slash_idx = parts.index("/")
        key = parts[slash_idx + 1 :]
        return _media_service.generate_presigned_url(key)

    return ""


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------
async def _check_reminders(event: dict) -> dict:
    """Check for pending assets and send reminder emails."""
    _init_services()
    assert _session_factory is not None
    assert _email_service is not None

    sent_count = 0

    async with _session_factory() as session:
        for threshold_days in REMINDER_THRESHOLDS:
            assets: list[ApprovalAsset] = await get_pending_assets_older_than(
                session, threshold_days
            )

            for asset in assets:
                # a. Check if reminder was already sent today
                if await _was_reminded_today(session, asset.id):
                    logger.info(
                        "Skipping asset %s — already reminded today", asset.id
                    )
                    continue

                # b. Find active magic link
                magic_link = await _find_active_magic_link(session, asset.id)
                if magic_link is None:
                    logger.info(
                        "Skipping asset %s — no active magic link", asset.id
                    )
                    continue

                # c. Get thumbnail URL from latest version
                latest_version = await _get_latest_version(session, asset.id)
                thumbnail_url = _get_thumbnail_presigned_url(latest_version)

                # d. Send reminder email
                client = asset.client
                await _email_service.send_reminder_email(
                    to_email=client.email or "",
                    client_name=client.display_name,
                    asset_title=asset.title,
                    thumbnail_url=thumbnail_url,
                    magic_link_token=magic_link.token,
                    days_pending=threshold_days,
                )

                # e. Log "reminder_sent" event
                await log_event(
                    session,
                    asset_id=asset.id,
                    event_type="reminder_sent",
                    metadata={"days_pending": threshold_days, "to": client.email},
                )

                # f. Send WhatsApp reminder (fire-and-forget — failure is non-fatal)
                if _whatsapp_service and client.whatsapp_phone:
                    try:
                        await _whatsapp_service.send_reminder_message(
                            to_phone=client.whatsapp_phone,
                            client_name=client.display_name,
                            asset_title=asset.title,
                            thumbnail_url=thumbnail_url,
                            magic_link_token=magic_link.token,
                            days_pending=threshold_days,
                        )
                        await log_event(
                            session,
                            asset_id=asset.id,
                            event_type="whatsapp_reminder_sent",
                            metadata={
                                "days_pending": threshold_days,
                                "to": client.whatsapp_phone,
                            },
                        )
                    except Exception:
                        logger.exception(
                            "WhatsApp reminder failed for asset %s — continuing",
                            asset.id,
                        )

                sent_count += 1
                logger.info(
                    "Reminder sent for asset %s (client=%s, days=%d)",
                    asset.id,
                    client.display_name,
                    threshold_days,
                )

        await session.commit()

    return {"status": "ok", "reminders_sent": sent_count}


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------
def check_reminders(event: dict, context: object) -> dict:
    """AWS Lambda handler — synchronous entry point."""
    return asyncio.get_event_loop().run_until_complete(_check_reminders(event))
