"""Admin API endpoints for System Health Monitoring."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.config.settings import Settings
from src.db.admin_models import ActivityLog, WebhookDelivery

logger = logging.getLogger(__name__)

health_router = APIRouter(prefix="/health", tags=["health"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SERVICE_TIMEOUT_SECONDS = 5.0


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ServiceHealth(BaseModel):
    name: str
    status: str  # "healthy" | "degraded" | "down" | "unknown"
    latency_ms: int
    message: str | None = None
    checked_at: str  # ISO format


class SystemHealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "down"
    services: list[ServiceHealth]
    checked_at: str  # ISO format


class SystemMetricsResponse(BaseModel):
    errors_24h: int
    requests_today: int
    active_admins_1h: int
    webhook_deliveries_24h: int
    checked_at: str  # ISO format


# ---------------------------------------------------------------------------
# Internal health check functions
# ---------------------------------------------------------------------------


async def _check_database(session: AsyncSession) -> ServiceHealth:
    """Check database connectivity with a simple SELECT 1 query."""
    start = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        result = await asyncio.wait_for(
            session.execute(text("SELECT 1")),
            timeout=_SERVICE_TIMEOUT_SECONDS,
        )
        _ = result.scalar()
        latency_ms = int((time.monotonic() - start) * 1000)

        status = "healthy" if latency_ms < 2000 else "degraded"
        message = None if status == "healthy" else f"Slow response: {latency_ms}ms"

        return ServiceHealth(
            name="database",
            status=status,
            latency_ms=latency_ms,
            message=message,
            checked_at=checked_at,
        )
    except asyncio.TimeoutError:
        return ServiceHealth(
            name="database",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="Query timed out after 5s",
            checked_at=checked_at,
        )
    except Exception as exc:
        return ServiceHealth(
            name="database",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message=f"Connection failed: {str(exc)[:200]}",
            checked_at=checked_at,
        )


async def _check_s3(settings: Settings) -> ServiceHealth:
    """Check S3 bucket accessibility via head_bucket."""
    start = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat()
    bucket_name = settings.s3_bucket_name or "approval-media-bucket"

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

        loop = asyncio.get_running_loop()

        def _head_bucket() -> None:
            client_kwargs: dict = {"service_name": "s3", "region_name": settings.s3_region}
            if settings.s3_access_key_id:
                client_kwargs["aws_access_key_id"] = settings.s3_access_key_id
                client_kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
            if settings.s3_endpoint_url:
                client_kwargs["endpoint_url"] = settings.s3_endpoint_url
            s3_client = boto3.client(**client_kwargs)
            s3_client.head_bucket(Bucket=bucket_name)

        await asyncio.wait_for(
            loop.run_in_executor(None, _head_bucket),
            timeout=_SERVICE_TIMEOUT_SECONDS,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        return ServiceHealth(
            name="s3",
            status="healthy",
            latency_ms=latency_ms,
            message=f"Bucket: {bucket_name}",
            checked_at=checked_at,
        )
    except ImportError:
        return ServiceHealth(
            name="s3",
            status="unknown",
            latency_ms=0,
            message="boto3 not installed",
            checked_at=checked_at,
        )
    except (NoCredentialsError, BotoCoreError):
        return ServiceHealth(
            name="s3",
            status="unknown",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="AWS not configured",
            checked_at=checked_at,
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("403", "AccessDenied"):
            # Bucket exists but we lack permissions -- still reachable
            return ServiceHealth(
                name="s3",
                status="degraded",
                latency_ms=int((time.monotonic() - start) * 1000),
                message=f"Access denied to bucket {bucket_name}",
                checked_at=checked_at,
            )
        return ServiceHealth(
            name="s3",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message=f"S3 error: {error_code}",
            checked_at=checked_at,
        )
    except asyncio.TimeoutError:
        return ServiceHealth(
            name="s3",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="S3 check timed out after 5s",
            checked_at=checked_at,
        )
    except Exception:
        return ServiceHealth(
            name="s3",
            status="unknown",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="AWS not configured",
            checked_at=checked_at,
        )


async def _check_ses(settings: Settings) -> ServiceHealth:
    """Check SES availability by listing verified identities."""
    start = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, NoCredentialsError

        loop = asyncio.get_running_loop()

        def _list_identities() -> list:
            client_kwargs: dict = {"service_name": "ses", "region_name": settings.s3_region}
            if settings.s3_access_key_id:
                client_kwargs["aws_access_key_id"] = settings.s3_access_key_id
                client_kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
            ses_client = boto3.client(**client_kwargs)
            response = ses_client.list_identities(IdentityType="EmailAddress", MaxItems=5)
            return response.get("Identities", [])

        identities = await asyncio.wait_for(
            loop.run_in_executor(None, _list_identities),
            timeout=_SERVICE_TIMEOUT_SECONDS,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        return ServiceHealth(
            name="ses",
            status="healthy",
            latency_ms=latency_ms,
            message=f"Verified identities: {len(identities)}",
            checked_at=checked_at,
        )
    except ImportError:
        return ServiceHealth(
            name="ses",
            status="unknown",
            latency_ms=0,
            message="boto3 not installed",
            checked_at=checked_at,
        )
    except (NoCredentialsError, BotoCoreError):
        return ServiceHealth(
            name="ses",
            status="unknown",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="AWS not configured",
            checked_at=checked_at,
        )
    except asyncio.TimeoutError:
        return ServiceHealth(
            name="ses",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="SES check timed out after 5s",
            checked_at=checked_at,
        )
    except Exception:
        return ServiceHealth(
            name="ses",
            status="unknown",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="AWS not configured",
            checked_at=checked_at,
        )


async def _check_clickup(settings: Settings) -> ServiceHealth:
    """Check ClickUp API reachability by fetching teams."""
    start = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat()

    if not settings.clickup_api_token:
        return ServiceHealth(
            name="clickup",
            status="unknown",
            latency_ms=0,
            message="ClickUp API token not configured",
            checked_at=checked_at,
        )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_SERVICE_TIMEOUT_SECONDS)
        ) as client:
            resp = await client.get(
                "https://api.clickup.com/api/v2/team",
                headers={"Authorization": settings.clickup_api_token},
            )
        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code == 200:
            teams = resp.json().get("teams", [])
            return ServiceHealth(
                name="clickup",
                status="healthy",
                latency_ms=latency_ms,
                message=f"Teams: {len(teams)}",
                checked_at=checked_at,
            )
        elif resp.status_code == 401:
            return ServiceHealth(
                name="clickup",
                status="degraded",
                latency_ms=latency_ms,
                message="Invalid API token (401)",
                checked_at=checked_at,
            )
        else:
            return ServiceHealth(
                name="clickup",
                status="degraded",
                latency_ms=latency_ms,
                message=f"Unexpected status: {resp.status_code}",
                checked_at=checked_at,
            )
    except httpx.TimeoutException:
        return ServiceHealth(
            name="clickup",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="ClickUp API timed out after 5s",
            checked_at=checked_at,
        )
    except httpx.RequestError as exc:
        return ServiceHealth(
            name="clickup",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message=f"Connection error: {str(exc)[:200]}",
            checked_at=checked_at,
        )


async def _check_telegram(settings: Settings) -> ServiceHealth:
    """Check Telegram Bot API reachability by calling getMe."""
    start = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat()

    if not settings.telegram_bot_token:
        return ServiceHealth(
            name="telegram",
            status="unknown",
            latency_ms=0,
            message="Telegram bot token not configured",
            checked_at=checked_at,
        )

    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_SERVICE_TIMEOUT_SECONDS)
        ) as client:
            resp = await client.get(url)
        latency_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code == 200 and resp.json().get("ok"):
            bot_info = resp.json().get("result", {})
            bot_username = bot_info.get("username", "unknown")
            return ServiceHealth(
                name="telegram",
                status="healthy",
                latency_ms=latency_ms,
                message=f"Bot: @{bot_username}",
                checked_at=checked_at,
            )
        elif resp.status_code == 401:
            return ServiceHealth(
                name="telegram",
                status="degraded",
                latency_ms=latency_ms,
                message="Invalid bot token (401)",
                checked_at=checked_at,
            )
        else:
            return ServiceHealth(
                name="telegram",
                status="degraded",
                latency_ms=latency_ms,
                message=f"Unexpected response: {resp.status_code}",
                checked_at=checked_at,
            )
    except httpx.TimeoutException:
        return ServiceHealth(
            name="telegram",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message="Telegram API timed out after 5s",
            checked_at=checked_at,
        )
    except httpx.RequestError as exc:
        return ServiceHealth(
            name="telegram",
            status="down",
            latency_ms=int((time.monotonic() - start) * 1000),
            message=f"Connection error: {str(exc)[:200]}",
            checked_at=checked_at,
        )


def _compute_overall_status(services: list[ServiceHealth]) -> str:
    """Derive overall system status from individual service statuses.

    - "healthy" if all services are healthy or unknown
    - "degraded" if any service is degraded (but none down)
    - "down" if any service is down
    """
    statuses = {s.status for s in services}
    if "down" in statuses:
        return "down"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@health_router.get("", response_model=SystemHealthResponse)
async def get_system_health(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("dashboard", "read")),
):
    """Overall system health check. Probes all external services in parallel."""
    settings = Settings()

    results = await asyncio.gather(
        _check_database(session),
        _check_s3(settings),
        _check_ses(settings),
        _check_clickup(settings),
        _check_telegram(settings),
        return_exceptions=True,
    )

    services: list[ServiceHealth] = []
    service_names = ["database", "s3", "ses", "clickup", "telegram"]
    for idx, result in enumerate(results):
        if isinstance(result, BaseException):
            services.append(
                ServiceHealth(
                    name=service_names[idx],
                    status="down",
                    latency_ms=0,
                    message=f"Unexpected error: {str(result)[:200]}",
                    checked_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        else:
            services.append(result)

    overall = _compute_overall_status(services)

    return SystemHealthResponse(
        status=overall,
        services=services,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@health_router.get("/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("dashboard", "read")),
):
    """System metrics summary from activity logs and webhook deliveries."""
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    one_hour_ago = now - timedelta(hours=1)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Errors in last 24h: activity logs where action contains "error" or "failed"
    errors_24h_result = await session.execute(
        select(func.count())
        .select_from(ActivityLog)
        .where(
            ActivityLog.created_at >= twenty_four_hours_ago,
            or_(
                ActivityLog.action.ilike("%error%"),
                ActivityLog.action.ilike("%failed%"),
            ),
        )
    )
    errors_24h = errors_24h_result.scalar() or 0

    # Total API requests today (all activity logs for today)
    requests_today_result = await session.execute(
        select(func.count())
        .select_from(ActivityLog)
        .where(ActivityLog.created_at >= start_of_today)
    )
    requests_today = requests_today_result.scalar() or 0

    # Active admin users in last 1h (distinct users in activity logs)
    active_admins_result = await session.execute(
        select(func.count(func.distinct(ActivityLog.user)))
        .select_from(ActivityLog)
        .where(ActivityLog.created_at >= one_hour_ago)
    )
    active_admins_1h = active_admins_result.scalar() or 0

    # Webhook deliveries in last 24h
    deliveries_result = await session.execute(
        select(func.count())
        .select_from(WebhookDelivery)
        .where(WebhookDelivery.created_at >= twenty_four_hours_ago)
    )
    webhook_deliveries_24h = deliveries_result.scalar() or 0

    return SystemMetricsResponse(
        errors_24h=errors_24h,
        requests_today=requests_today,
        active_admins_1h=active_admins_1h,
        webhook_deliveries_24h=webhook_deliveries_24h,
        checked_at=now.isoformat(),
    )
