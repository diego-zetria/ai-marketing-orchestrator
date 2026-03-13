"""Portal API Lambda handler.

REST API backend for the client approval portal (Next.js frontend).

Routes:
- GET  /api/auth/validate?token=...      Magic-link validation -> JWT + asset detail
- GET  /api/health                        Health check
- GET  /api/assets/{assetId}              Asset detail with pre-signed URLs
- POST /api/assets/{assetId}/approve      Record approval decision
- POST /api/assets/{assetId}/request-changes  Record change-request decision
- POST /api/assets/{assetId}/comments     Add client comment
- OPTIONS *                               CORS preflight
"""

import asyncio
import base64
import json
import logging
import os
import re
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.approval.repository import (
    add_comment,
    get_asset_with_relations,
    log_event,
    save_decision,
    update_asset_status,
    validate_magic_link,
)
from src.approval.schemas import (
    AddCommentRequest,
    ApproveRequest,
    AssetDetailResponse,
    AssetResponse,
    CommentResponse,
    DecisionResponse,
    DecisionResultResponse,
    RequestChangesRequest,
    VersionResponse,
)
from src.approval.services.auth import create_jwt, verify_jwt
from src.approval.services.media import MediaService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CLICKUP_API_BASE = "https://api.clickup.com/api/v2"

# ---------------------------------------------------------------------------
# Global singletons (Lambda container reuse pattern)
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None
_media_service: MediaService | None = None


def _init_services() -> None:
    """Lazy-initialise shared services on first invocation."""
    global _engine, _session_factory, _media_service

    if _session_factory is not None:
        return

    database_url = os.environ["DATABASE_URL"]
    _engine = create_async_engine(database_url, echo=False)
    _session_factory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    _media_service = MediaService(bucket=os.environ["MEDIA_BUCKET"])


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def _cors_headers() -> dict[str, str]:
    """Build CORS headers from PORTAL_DOMAIN env var (testable, no module-level cache)."""
    origin = f"https://{os.environ.get('PORTAL_DOMAIN', 'approvals.example.com')}"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Vary": "Origin",
    }


def _decode_body(event: dict) -> str:
    """Decode the request body, handling API Gateway base64 encoding.

    API Gateway may base64-encode the body when it contains non-ASCII bytes
    (e.g. accented characters in Portuguese). This helper transparently
    decodes such bodies so handlers can always call ``json.loads`` safely.

    Fallback strategy: if ``isBase64Encoded`` is not set but ``json.loads``
    would fail, attempt base64 decoding as a last resort.
    """
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    else:
        # API Gateway REST API may pass base64 without flagging it
        try:
            json.loads(body)
        except (json.JSONDecodeError, ValueError):
            try:
                body = base64.b64decode(body).decode("utf-8")
                logger.info("Body was base64-encoded without isBase64Encoded flag")
            except Exception:
                pass  # Return the original body; let the caller handle errors
    return body


def _response(status: int, body: dict) -> dict:
    """Create an API Gateway proxy response with CORS headers."""
    return {
        "statusCode": status,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def _get_jwt_claims(event: dict) -> dict | None:
    """Extract and verify JWT from the Authorization header.

    Returns decoded claims dict on success, None on failure.
    """
    headers = event.get("headers") or {}
    # API Gateway may lowercase header names
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        secret = os.environ["JWT_SECRET"]
        return verify_jwt(secret=secret, token=token)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Build version response with pre-signed URLs
# ---------------------------------------------------------------------------
def _build_version_response(version, media_service: MediaService) -> VersionResponse:
    """Convert an ORM AssetVersion to a VersionResponse with pre-signed URLs."""
    media_url = None
    thumbnail_url = None

    if version.original_url:
        if version.original_url.startswith("s3://"):
            # Extract key from s3://bucket/key → generate pre-signed URL
            parts = version.original_url.split("/", 3)
            key = parts[3] if len(parts) > 3 else ""
            if key:
                media_url = media_service.generate_presigned_url(key)
        elif version.original_url.startswith("http"):
            # External URL (e.g. Google Drive link) — pass through as-is
            media_url = version.original_url

    if version.thumbnail_url:
        if version.thumbnail_url.startswith("s3://"):
            key = (
                version.thumbnail_url.split("/", 3)[3]
                if version.thumbnail_url.count("/") >= 3
                else ""
            )
            if key:
                thumbnail_url = media_service.generate_presigned_url(key)
        elif version.thumbnail_url.startswith("http"):
            thumbnail_url = version.thumbnail_url

    return VersionResponse(
        id=version.id,
        version_number=version.version_number,
        file_type=version.file_type,
        file_format=version.file_format,
        media_url=media_url,
        thumbnail_url=thumbnail_url,
        file_size_bytes=version.file_size_bytes,
        width=version.width,
        height=version.height,
        duration_seconds=version.duration_seconds,
        uploaded_by=version.uploaded_by,
        created_at=version.created_at,
    )


def _build_asset_detail(asset, media_service: MediaService) -> AssetDetailResponse:
    """Build a full AssetDetailResponse from an ORM asset with loaded relations."""
    from src.approval.schemas import AssetResponse, ClientResponse, CommentResponse

    versions = [_build_version_response(v, media_service) for v in asset.versions]
    current = next(
        (v for v in versions if v.version_number == asset.current_version),
        None,
    )
    comments = [
        CommentResponse.model_validate(c, from_attributes=True)
        for c in asset.comments
    ]
    decisions = [
        DecisionResponse.model_validate(d, from_attributes=True)
        for d in asset.decisions
    ]

    return AssetDetailResponse(
        asset=AssetResponse.model_validate(asset, from_attributes=True),
        client=ClientResponse.model_validate(asset.client, from_attributes=True),
        current_version=current,
        versions=versions,
        comments=comments,
        decisions=decisions,
    )


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------
async def _handle_auth_validate(event: dict) -> dict:
    """Validate a magic-link token, create JWT, return asset detail."""
    _init_services()
    assert _session_factory is not None
    assert _media_service is not None

    params = event.get("queryStringParameters") or {}
    token = params.get("token")
    if not token:
        return _response(400, {"error": "Missing token parameter"})

    async with _session_factory() as session:
        magic_link = await validate_magic_link(session, token)
        if magic_link is None:
            return _response(401, {"error": "Invalid or expired token"})

        asset = await get_asset_with_relations(session, magic_link.asset_id)
        if asset is None:
            return _response(404, {"error": "Asset not found"})

        # Create JWT
        jwt_secret = os.environ["JWT_SECRET"]
        jwt_token = create_jwt(
            secret=jwt_secret,
            asset_id=asset.id,
            client_id=magic_link.client_id,
            client_slug=asset.client.slug or asset.client.name,
        )

        # Log access event
        await log_event(
            session,
            asset_id=asset.id,
            event_type="magic_link_validated",
            actor=f"client:{asset.client.slug or asset.client.name}",
            metadata={"token_prefix": token[:8]},
        )
        await session.commit()

    detail = _build_asset_detail(asset, _media_service)
    from src.approval.schemas import AuthValidateResponse

    resp = AuthValidateResponse(jwt=jwt_token, asset=detail)
    return _response(200, resp.model_dump(mode="json"))


async def _handle_get_asset(event: dict, asset_id: str) -> dict:
    """Return full asset detail with pre-signed URLs."""
    _init_services()
    assert _session_factory is not None
    assert _media_service is not None

    claims = _get_jwt_claims(event)
    if claims is None:
        return _response(401, {"error": "Unauthorized"})

    # Verify the JWT asset_id matches the requested asset
    if claims.get("asset_id") != asset_id:
        return _response(403, {"error": "Forbidden"})

    try:
        uid = UUID(asset_id)
    except ValueError:
        return _response(400, {"error": "Invalid asset ID"})

    async with _session_factory() as session:
        asset = await get_asset_with_relations(session, uid)
        if asset is None:
            return _response(404, {"error": "Asset not found"})

    detail = _build_asset_detail(asset, _media_service)
    return _response(200, detail.model_dump(mode="json"))


async def _handle_approve(event: dict, asset_id: str) -> dict:
    """Record an approval decision for the asset."""
    _init_services()
    assert _session_factory is not None
    assert _media_service is not None

    claims = _get_jwt_claims(event)
    if claims is None:
        return _response(401, {"error": "Unauthorized"})

    if claims.get("asset_id") != asset_id:
        return _response(403, {"error": "Forbidden"})

    try:
        uid = UUID(asset_id)
    except ValueError:
        return _response(400, {"error": "Invalid asset ID"})

    # Parse optional body
    body = json.loads(_decode_body(event))
    try:
        req = ApproveRequest(**body)
    except ValidationError as exc:
        return _response(422, {"error": "Validation error", "detail": exc.errors()})

    async with _session_factory() as session:
        asset = await get_asset_with_relations(session, uid)
        if asset is None:
            return _response(404, {"error": "Asset not found"})

        # Find the current version
        current_ver = next(
            (v for v in asset.versions if v.version_number == asset.current_version),
            None,
        )
        if current_ver is None:
            return _response(404, {"error": "No current version found"})

        decided_by = claims.get("sub", "client")

        decision = await save_decision(
            session,
            asset_id=uid,
            version_id=current_ver.id,
            decision="approved",
            decided_by=decided_by,
            comment=req.comment,
        )

        await update_asset_status(session, uid, "approved")

        await log_event(
            session,
            asset_id=uid,
            event_type="asset_approved",
            actor=decided_by,
            metadata={"version": asset.current_version, "comment": req.comment},
        )

        await session.commit()

        # Refresh asset for response
        asset = await get_asset_with_relations(session, uid)

    # W6: Fire-and-forget ClickUp sync with enriched client feedback
    client_label = asset.client.slug or asset.client.name if asset.client else ""  # type: ignore[union-attr]
    approve_comment = req.comment or ""
    approve_msg = (
        f"APROVADO PELO CLIENTE via Portal de Aprovacao\n"
        f"========================================\n\n"
        f"Versao: {asset.current_version}\n"  # type: ignore[union-attr]
        + (f"Cliente: {client_label}\n" if client_label else "")
        + "\nCliente aprovou esta versao."
        + (f"\n\nComentario do cliente:\n{approve_comment}" if approve_comment else "")
        + "\n\n========================================\n"
        + "Comentario gerado automaticamente pelo Portal de Aprovacao."
    )
    await _sync_clickup_decision(
        asset.clickup_task_id,  # type: ignore[union-attr]
        status="aprovado_cliente",
        message=approve_msg,
    )

    resp = DecisionResultResponse(
        decision=DecisionResponse.model_validate(decision, from_attributes=True),
        asset=AssetResponse.model_validate(asset, from_attributes=True),
    )
    return _response(200, resp.model_dump(mode="json"))


async def _handle_request_changes(event: dict, asset_id: str) -> dict:
    """Record a change-request decision for the asset."""
    _init_services()
    assert _session_factory is not None
    assert _media_service is not None

    claims = _get_jwt_claims(event)
    if claims is None:
        return _response(401, {"error": "Unauthorized"})

    if claims.get("asset_id") != asset_id:
        return _response(403, {"error": "Forbidden"})

    try:
        uid = UUID(asset_id)
    except ValueError:
        return _response(400, {"error": "Invalid asset ID"})

    body = json.loads(_decode_body(event))
    try:
        req = RequestChangesRequest(**body)
    except ValidationError as exc:
        return _response(422, {"error": "Validation error", "detail": exc.errors()})

    async with _session_factory() as session:
        asset = await get_asset_with_relations(session, uid)
        if asset is None:
            return _response(404, {"error": "Asset not found"})

        current_ver = next(
            (v for v in asset.versions if v.version_number == asset.current_version),
            None,
        )
        if current_ver is None:
            return _response(404, {"error": "No current version found"})

        decided_by = claims.get("sub", "client")

        decision = await save_decision(
            session,
            asset_id=uid,
            version_id=current_ver.id,
            decision="changes_requested",
            decided_by=decided_by,
            comment=req.comment,
        )

        await update_asset_status(session, uid, "changes_requested")

        await log_event(
            session,
            asset_id=uid,
            event_type="changes_requested",
            actor=decided_by,
            metadata={"version": asset.current_version, "comment": req.comment},
        )

        await session.commit()

        asset = await get_asset_with_relations(session, uid)

    # W6: Fire-and-forget ClickUp sync with enriched client feedback
    client_label = asset.client.slug or asset.client.name if asset.client else ""  # type: ignore[union-attr]
    changes_msg = (
        f"FEEDBACK DO CLIENTE via Portal de Aprovacao\n"
        f"========================================\n\n"
        f"Versao: {asset.current_version}\n"  # type: ignore[union-attr]
        + (f"Cliente: {client_label}\n" if client_label else "")
        + f"\nAlteracoes solicitadas:\n{req.comment}\n"
        + "\n========================================\n"
        + "Comentario gerado automaticamente pelo Portal de Aprovacao."
    )
    await _sync_clickup_decision(
        asset.clickup_task_id,  # type: ignore[union-attr]
        status="alteracao_cliente",
        message=changes_msg,
    )

    resp = DecisionResultResponse(
        decision=DecisionResponse.model_validate(decision, from_attributes=True),
        asset=AssetResponse.model_validate(asset, from_attributes=True),
    )
    return _response(200, resp.model_dump(mode="json"))


async def _handle_add_comment(event: dict, asset_id: str) -> dict:
    """Add a client comment to the asset."""
    _init_services()
    assert _session_factory is not None

    claims = _get_jwt_claims(event)
    if claims is None:
        return _response(401, {"error": "Unauthorized"})

    if claims.get("asset_id") != asset_id:
        return _response(403, {"error": "Forbidden"})

    try:
        uid = UUID(asset_id)
    except ValueError:
        return _response(400, {"error": "Invalid asset ID"})

    body = json.loads(_decode_body(event))
    try:
        req = AddCommentRequest(**body)
    except ValidationError as exc:
        return _response(422, {"error": "Validation error", "detail": exc.errors()})

    async with _session_factory() as session:
        asset = await get_asset_with_relations(session, uid)
        if asset is None:
            return _response(404, {"error": "Asset not found"})

        author_name = claims.get("sub", "client")

        comment = await add_comment(
            session,
            asset_id=uid,
            version_id=None,
            author_type="client",
            author_name=author_name,
            content=req.content,
        )

        await log_event(
            session,
            asset_id=uid,
            event_type="comment_added",
            actor=author_name,
            metadata={"content_preview": req.content[:100]},
        )

        await session.commit()

    resp = CommentResponse.model_validate(comment, from_attributes=True)
    return _response(201, resp.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# ClickUp sync (fire-and-forget)
# ---------------------------------------------------------------------------
async def _sync_clickup_decision(task_id: str, *, status: str, message: str) -> None:
    """Sync decision to ClickUp: update status + add comment.

    Errors are logged but never propagated to the caller.
    """
    try:
        token = os.environ.get("CLICKUP_API_TOKEN", "")
        if not token:
            logger.warning("CLICKUP_API_TOKEN not set — skipping ClickUp sync")
            return

        headers = {"Authorization": token, "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            # Update task status
            await client.put(
                f"{CLICKUP_API_BASE}/task/{task_id}",
                headers=headers,
                json={"status": status},
            )

            # Add comment
            await client.post(
                f"{CLICKUP_API_BASE}/task/{task_id}/comment",
                headers=headers,
                json={"comment_text": message},
            )

        logger.info("ClickUp sync OK for task %s (status=%s)", task_id, status)
    except Exception:
        logger.exception("ClickUp sync failed for task %s", task_id)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
# Path patterns for asset routes
_ASSET_ID_RE = re.compile(
    r"^/api/assets/([0-9a-fA-F-]{36})(?:/(approve|request-changes|comments))?$"
)


async def _route(event: dict) -> dict:
    """Dispatch incoming API Gateway event to the appropriate handler."""
    method = (event.get("httpMethod") or "").upper()
    path = event.get("path") or ""

    # CORS preflight
    if method == "OPTIONS":
        return _response(200, {"message": "OK"})

    # Health check
    if method == "GET" and path == "/api/health":
        return _response(200, {"status": "healthy"})

    # Auth validate
    if method == "GET" and path == "/api/auth/validate":
        return await _handle_auth_validate(event)

    # Asset routes
    match = _ASSET_ID_RE.match(path)
    if match:
        asset_id = match.group(1)
        action = match.group(2)  # None, "approve", "request-changes", or "comments"

        if method == "GET" and action is None:
            return await _handle_get_asset(event, asset_id)
        if method == "POST" and action == "approve":
            return await _handle_approve(event, asset_id)
        if method == "POST" and action == "request-changes":
            return await _handle_request_changes(event, asset_id)
        if method == "POST" and action == "comments":
            return await _handle_add_comment(event, asset_id)

    return _response(404, {"error": "Not found"})


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------
def api_handler(event: dict, context: object) -> dict:
    """AWS Lambda handler -- synchronous entry point."""
    return asyncio.get_event_loop().run_until_complete(_route(event))
