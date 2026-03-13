from __future__ import annotations

import asyncio
import io
import logging
import uuid
from functools import partial

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.api.admin.notification_helper import create_notification
from src.db.admin_models import Client
from src.db.models import TeamMember
from src.db.workflow_models import WorkflowDefinition

logger = logging.getLogger(__name__)

clients_router = APIRouter(prefix="/clients", tags=["clients"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    name: str
    display_name: str
    slug: str | None = None
    clickup_list_id: str | None = None
    designer_id: str | None = None  # UUID as string
    account_id: str | None = None  # UUID as string
    workflow_id: str | None = None  # UUID as string
    email: str | None = None
    whatsapp_phone: str | None = None
    logo_url: str | None = None


class ClientUpdate(BaseModel):
    display_name: str | None = None
    slug: str | None = None
    clickup_list_id: str | None = None
    designer_id: str | None = None
    account_id: str | None = None
    workflow_id: str | None = None
    email: str | None = None
    whatsapp_phone: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None


class ClientResponse(BaseModel):
    id: str
    name: str
    display_name: str
    slug: str | None
    clickup_list_id: str | None
    designer_id: str | None
    account_id: str | None
    workflow_id: str | None
    email: str | None
    whatsapp_phone: str | None
    logo_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class PaginatedClients(BaseModel):
    items: list[ClientResponse]
    total: int
    page: int
    per_page: int


# Allowed sort columns for client listing (validated explicitly for safety)
_CLIENT_SORT_COLUMNS: dict[str, object] = {
    "name": Client.name,
    "display_name": Client.display_name,
    "email": Client.email,
    "is_active": Client.is_active,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@clients_router.get("", response_model=PaginatedClients)
async def list_clients(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    search: str | None = Query(None),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc"),
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "read")),
):
    # Validate sort_by against allowed set
    if sort_by not in _CLIENT_SORT_COLUMNS:
        sort_by = "name"
    sort_col = _CLIENT_SORT_COLUMNS[sort_by]

    # Build base filters
    base = select(Client)
    count_base = select(func.count()).select_from(Client)

    if not include_inactive:
        base = base.where(Client.is_active.is_(True))
        count_base = count_base.where(Client.is_active.is_(True))

    if search:
        search_filter = or_(
            Client.name.ilike(f"%{search}%"),
            Client.display_name.ilike(f"%{search}%"),
        )
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)

    # Total count
    total = (await session.execute(count_base)).scalar() or 0

    # Sorting
    order = sort_col.asc() if sort_order != "desc" else sort_col.desc()

    # Paginated results
    offset = (page - 1) * per_page
    stmt = base.order_by(order).offset(offset).limit(per_page)
    result = await session.execute(stmt)
    clients = result.scalars().all()

    return PaginatedClients(
        items=[_to_response(c) for c in clients],
        total=total,
        page=page,
        per_page=per_page,
    )


@clients_router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "create")),
):
    # Validate FK references
    designer_uuid = await _validate_team_member_fk(session, payload.designer_id, "designer_id")
    account_uuid = await _validate_team_member_fk(session, payload.account_id, "account_id")
    workflow_uuid = await _validate_workflow_fk(session, payload.workflow_id)

    client = Client(
        name=payload.name,
        display_name=payload.display_name,
        slug=payload.slug,
        clickup_list_id=payload.clickup_list_id,
        designer_id=designer_uuid,
        account_id=account_uuid,
        workflow_id=workflow_uuid,
        email=payload.email,
        whatsapp_phone=payload.whatsapp_phone,
        logo_url=payload.logo_url,
    )
    session.add(client)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Client with name '{payload.name}' already exists",
        )

    await log_activity(
        session,
        action="create",
        entity_type="client",
        entity_id=str(client.id),
        details={"name": client.name, "display_name": client.display_name},
        user=_user.name,
    )
    await session.commit()

    await create_notification(
        session,
        title="Novo cliente",
        message=f"Cliente {client.display_name} foi adicionado.",
        link="/admin/clients",
        icon="client",
    )
    await session.commit()

    await session.refresh(client)
    return _to_response(client)


@clients_router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    payload: ClientUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "update")),
):
    client = await _get_client_or_404(session, client_id)

    update_data = payload.model_dump(exclude_unset=True)

    # Validate FK references if provided
    if "designer_id" in update_data:
        update_data["designer_id"] = await _validate_team_member_fk(
            session, update_data["designer_id"], "designer_id"
        )
    if "account_id" in update_data:
        update_data["account_id"] = await _validate_team_member_fk(
            session, update_data["account_id"], "account_id"
        )
    if "workflow_id" in update_data:
        update_data["workflow_id"] = await _validate_workflow_fk(
            session, update_data["workflow_id"]
        )

    changes: dict = {}
    for field, value in update_data.items():
        current = getattr(client, field)
        # Normalize UUIDs to compare properly
        if isinstance(current, uuid.UUID):
            current = str(current)
        if isinstance(value, uuid.UUID):
            value_cmp = str(value)
        else:
            value_cmp = value
        if current != value_cmp:
            changes[field] = value_cmp if isinstance(value, uuid.UUID) else value
            setattr(client, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="client",
            entity_id=str(client.id),
            details=changes,
            user=_user.name,
        )
        await session.commit()
        await session.refresh(client)

    return _to_response(client)


@clients_router.delete("/{client_id}", response_model=ClientResponse)
async def delete_client(
    client_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "delete")),
):
    client = await _get_client_or_404(session, client_id)
    client.is_active = False

    await log_activity(
        session,
        action="delete",
        entity_type="client",
        entity_id=str(client.id),
        details={"name": client.name},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(client)
    return _to_response(client)


# ---------------------------------------------------------------------------
# Logo Upload
# ---------------------------------------------------------------------------

LOGO_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
LOGO_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
LOGO_ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "gif"}
LOGO_MAGIC_BYTES = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG": "png",
    b"RIFF": "webp",
    b"GIF8": "gif",
}
LOGO_SIZES = {"original": 512, "thumb": 64}


@clients_router.post("/{client_id}/logo", response_model=ClientResponse)
async def upload_client_logo(
    client_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "update")),
):
    """Upload a client logo image. Validates, converts to WebP, generates thumb."""
    client = await _get_client_or_404(session, client_id)

    # --- 1. Validate MIME type ---
    content_type = file.content_type or ""
    if content_type not in LOGO_ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo nao permitido: {content_type}. Use JPEG, PNG, WebP ou GIF.",
        )

    # --- 2. Read bytes & validate size ---
    file_bytes = await file.read()
    if len(file_bytes) > LOGO_MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Arquivo muito grande ({len(file_bytes) // 1024}KB). "
                f"Maximo: {LOGO_MAX_SIZE // (1024 * 1024)}MB."
            ),
        )

    # --- 3. Magic bytes validation (security) ---
    detected = None
    for magic, fmt in LOGO_MAGIC_BYTES.items():
        if file_bytes[:len(magic)] == magic:
            detected = fmt
            break
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo nao e uma imagem valida.",
        )

    # --- 4. Re-encode through Pillow (strips metadata, validates content) ---
    loop = asyncio.get_running_loop()
    try:
        img = await loop.run_in_executor(None, partial(Image.open, io.BytesIO(file_bytes)))
        img.load()  # Force full decode to catch corrupted images
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Imagem corrompida ou formato invalido.",
        )

    # --- 5. Generate WebP variants ---
    s3, bucket = _get_s3_client()

    logo_urls = {}
    for label, max_dim in LOGO_SIZES.items():
        webp_bytes = await loop.run_in_executor(
            None, partial(_resize_to_webp, img, max_dim)
        )
        key = f"logos/{client.id}/{label}.webp"
        await loop.run_in_executor(
            None,
            partial(
                s3.put_object,
                Bucket=bucket,
                Key=key,
                Body=webp_bytes,
                ContentType="image/webp",
                CacheControl="public, max-age=31536000, immutable",
            ),
        )
        logo_urls[label] = f"s3://{bucket}/{key}"

    # --- 6. Update client.logo_url ---
    old_logo = client.logo_url
    client.logo_url = logo_urls["original"]

    await log_activity(
        session,
        action="update",
        entity_type="client",
        entity_id=str(client.id),
        details={"logo_url": logo_urls["original"], "old_logo_url": old_logo},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(client)

    logger.info("Logo uploaded for client %s (%s)", client.name, client.id)
    return _to_response(client)


@clients_router.get("/{client_id}/logo-url")
async def get_client_logo_url(
    client_id: str,
    size: str = Query("original", pattern="^(original|thumb)$"),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "read")),
):
    """Get a presigned URL for the client logo."""
    client = await _get_client_or_404(session, client_id)

    if not client.logo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente nao possui logo.",
        )

    s3, bucket = _get_s3_client()
    key = f"logos/{client.id}/{size}.webp"
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )
    return {"url": url, "size": size}


@clients_router.delete("/{client_id}/logo", response_model=ClientResponse)
async def delete_client_logo(
    client_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("clients", "update")),
):
    """Remove a client logo from S3 and clear logo_url."""
    client = await _get_client_or_404(session, client_id)

    if not client.logo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente nao possui logo.",
        )

    try:
        s3, bucket = _get_s3_client()
    except HTTPException:
        s3, bucket = None, None

    if s3:
        loop = asyncio.get_running_loop()
        for label in LOGO_SIZES:
            key = f"logos/{client.id}/{label}.webp"
            try:
                await loop.run_in_executor(
                    None,
                    partial(
                        s3.delete_object,
                        Bucket=bucket,
                        Key=key,
                    ),
                )
            except Exception:
                logger.warning("Failed to delete S3 key %s", key)

    old_logo = client.logo_url
    client.logo_url = None

    await log_activity(
        session,
        action="update",
        entity_type="client",
        entity_id=str(client.id),
        details={"logo_url": None, "old_logo_url": old_logo},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(client)
    return _to_response(client)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_s3_client():
    """Build a boto3 S3 client from settings."""
    from src.config.settings import Settings

    settings = Settings()
    if not settings.s3_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servico de armazenamento nao configurado.",
        )
    import boto3

    kwargs: dict = {"region_name": settings.s3_region}
    if settings.s3_access_key_id:
        kwargs["aws_access_key_id"] = settings.s3_access_key_id
        kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs), settings.s3_bucket_name


def _resize_to_webp(img: Image.Image, max_dim: int) -> bytes:
    """Resize image to fit within max_dim and encode as WebP."""
    thumb = img.copy()
    thumb.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    if thumb.mode in ("RGBA", "P"):
        thumb = thumb.convert("RGB")
    buf = io.BytesIO()
    thumb.save(buf, format="WEBP", quality=90)
    return buf.getvalue()


async def _get_client_or_404(session: AsyncSession, client_id: str) -> Client:
    try:
        uid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    result = await session.execute(select(Client).where(Client.id == uid))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


async def _validate_team_member_fk(
    session: AsyncSession, member_id: str | None, field_name: str
) -> uuid.UUID | None:
    """Validate that a team member FK exists. Returns the UUID or None."""
    if member_id is None:
        return None

    try:
        uid = uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID for {field_name}: '{member_id}'",
        )

    result = await session.execute(select(TeamMember).where(TeamMember.id == uid))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team member not found for {field_name}: '{member_id}'",
        )
    return uid


async def _validate_workflow_fk(
    session: AsyncSession, workflow_id: str | None
) -> uuid.UUID | None:
    """Validate that a workflow FK exists. Returns the UUID or None."""
    if workflow_id is None:
        return None

    try:
        uid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID for workflow_id: '{workflow_id}'",
        )

    result = await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == uid)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )
    return uid


def _to_response(client: Client) -> ClientResponse:
    return ClientResponse(
        id=str(client.id),
        name=client.name,
        display_name=client.display_name,
        slug=client.slug,
        clickup_list_id=client.clickup_list_id,
        designer_id=str(client.designer_id) if client.designer_id else None,
        account_id=str(client.account_id) if client.account_id else None,
        workflow_id=str(client.workflow_id) if client.workflow_id else None,
        email=client.email,
        whatsapp_phone=client.whatsapp_phone,
        logo_url=client.logo_url,
        is_active=client.is_active,
    )
