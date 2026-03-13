"""Approval Processor Lambda handler.

Triggered by EventBridge when a ClickUp task status change event is received.

Flow:
1. Fetch ClickUp task
2. Extract Google Drive link from custom field (populated by A3)
3. Create/update DB records (asset, version, magic_link)
4. Send email notification to client with Drive link + portal approval link
"""

import asyncio
import logging
import os
import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.approval.repository import (
    create_asset,
    create_magic_link,
    create_version,
    deactivate_magic_links,
    get_asset_by_task_id,
    get_client_by_list_id,
    log_event,
    update_asset_status,
)
from src.approval.services.email import EmailService
from src.approval.services.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CLICKUP_API_BASE = "https://api.clickup.com/api/v2"

# Regex to detect Google Drive links
_DRIVE_LINK_RE = re.compile(r"https?://drive\.google\.com/\S+", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Global singletons (Lambda container reuse pattern)
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None
_email_service: EmailService | None = None
_whatsapp_service: WhatsAppService | None = None


def _init_services() -> None:
    """Lazy-initialise shared services on first invocation."""
    global _engine, _session_factory, _media_service, _email_service, _whatsapp_service

    if _session_factory is not None:
        return

    database_url = os.environ["DATABASE_URL"]
    _engine = create_async_engine(database_url, echo=False)
    _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    _email_service = EmailService(
        from_email=os.environ["SES_FROM_EMAIL"],
        portal_domain=os.environ["PORTAL_DOMAIN"],
    )

    wa_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    wa_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    if wa_phone_id and wa_token:
        _whatsapp_service = WhatsAppService(
            phone_number_id=wa_phone_id,
            access_token=wa_token,
            portal_domain=os.environ["PORTAL_DOMAIN"],
        )


# ---------------------------------------------------------------------------
# ClickUp helpers
# ---------------------------------------------------------------------------
async def _fetch_task(task_id: str) -> dict:
    """Fetch a ClickUp task by ID."""
    token = os.environ["CLICKUP_API_TOKEN"]
    headers = {"Authorization": token}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CLICKUP_API_BASE}/task/{task_id}",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_drive_link(task_data: dict) -> str:
    """Extract Google Drive link from task custom fields or description.

    Priority:
    1. Custom field with drive.google.com value (populated by A3)
    2. Drive link in task description (fallback)
    """
    # Check custom fields first (A3 saves Drive link here)
    for cf in task_data.get("custom_fields", []):
        value = cf.get("value", "")
        if isinstance(value, str) and "drive.google.com" in value:
            return value

    # Fallback: check task description
    description = task_data.get("description", "") or ""
    match = _DRIVE_LINK_RE.search(description)
    if match:
        return match.group(0)

    return ""


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------
async def _process(event: dict) -> dict:
    """Process a single EventBridge event for a ClickUp task status change.

    Extracts the Google Drive link from the task (saved by A3 automation)
    and creates an approval request with the Drive link as the media source.
    No S3 upload needed — the client views media directly via Drive.
    """
    _init_services()
    assert _session_factory is not None
    assert _email_service is not None

    detail = event.get("detail", {})
    task_id = detail["task_id"]

    # 1. Fetch ClickUp task (with retry — Drive link may be saved shortly after
    #    the status change by the CommentHandler A3 automation)
    task_data = await _fetch_task(task_id)

    # 2. Extract Drive link (from custom field or description)
    drive_link = _extract_drive_link(task_data)
    if not drive_link:
        logger.info("Task %s has no Drive link yet — retrying in 15s", task_id)
        await asyncio.sleep(15)
        task_data = await _fetch_task(task_id)
        drive_link = _extract_drive_link(task_data)

    if not drive_link:
        logger.warning("Task %s has no Drive link after retry — skipping", task_id)
        return {"status": "skipped", "reason": "no_drive_link", "task_id": task_id}

    # 3. Find client by list_id
    list_id = task_data.get("list", {}).get("id", "")

    async with _session_factory() as session:
        client = await get_client_by_list_id(session, list_id)
        if client is None:
            logger.warning("No client found for list_id=%s (task %s)", list_id, task_id)
            return {"status": "skipped", "reason": "client_not_found", "task_id": task_id}

        # 4. Create or update asset
        existing_asset = await get_asset_by_task_id(session, task_id)
        if existing_asset is not None:
            new_version = existing_asset.current_version + 1
            asset = existing_asset
        else:
            asset = await create_asset(
                session,
                client_id=client.id,
                clickup_task_id=task_id,
                title=task_data.get("name", f"Task {task_id}"),
                description=task_data.get("description"),
            )
            new_version = 1

        # 5. Create version record with Drive link as media URL
        await create_version(
            session,
            asset_id=asset.id,
            version_number=new_version,
            file_type="link",
            file_format="drive",
            original_url=drive_link,
            uploaded_by="system",
        )

        # 6. Update asset status, deactivate old magic links
        await update_asset_status(session, asset.id, "pending_review", version=new_version)
        await deactivate_magic_links(session, asset.id)

        # 7. Create new magic link
        magic_link = await create_magic_link(
            session,
            asset_id=asset.id,
            client_id=client.id,
        )

        # 8. Log events
        await log_event(
            session,
            asset_id=asset.id,
            event_type="asset_uploaded",
            metadata={
                "version": new_version,
                "drive_link": drive_link,
                "task_id": task_id,
            },
        )

        await log_event(
            session,
            asset_id=asset.id,
            event_type="magic_link_created",
            metadata={"token_prefix": magic_link.token[:8]},
        )

        # 9. Send email notification with Drive link
        await _email_service.send_new_asset_email(
            to_email=client.email or "",
            client_name=client.display_name,
            asset_title=asset.title,
            thumbnail_url=drive_link,
            magic_link_token=magic_link.token,
            version_number=new_version,
        )

        await log_event(
            session,
            asset_id=asset.id,
            event_type="email_sent",
            metadata={"to": client.email, "version": new_version},
        )

        # 11. Send WhatsApp notification (fire-and-forget — failure is non-fatal)
        if _whatsapp_service and client.whatsapp_phone:
            try:
                await _whatsapp_service.send_new_asset_message(
                    to_phone=client.whatsapp_phone,
                    client_name=client.display_name,
                    asset_title=asset.title,
                    thumbnail_url=drive_link,
                    magic_link_token=magic_link.token,
                    version_number=new_version,
                )
                await log_event(
                    session,
                    asset_id=asset.id,
                    event_type="whatsapp_sent",
                    metadata={"to": client.whatsapp_phone, "version": new_version},
                )
            except Exception:
                logger.exception("WhatsApp failed for asset %s — continuing", asset.id)

        await session.commit()

    return {"status": "ok", "asset_id": str(asset.id), "version": new_version}


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------
def process_webhook(event: dict, context: object) -> dict:
    """AWS Lambda handler — synchronous entry point."""
    return asyncio.get_event_loop().run_until_complete(_process(event))
