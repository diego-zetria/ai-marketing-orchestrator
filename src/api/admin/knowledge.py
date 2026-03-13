"""Admin API endpoints for Knowledge Documents."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import KnowledgeDocument

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class KnowledgeDocumentCreate(BaseModel):
    title: str
    category: str
    content: str
    agent_access: list[str] = []


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    agent_access: list[str] | None = None
    is_active: bool | None = None


class KnowledgeDocumentResponse(BaseModel):
    id: str
    title: str
    category: str
    content: str
    file_key: str | None
    file_name: str | None
    file_type: str | None
    file_size: int | None
    agent_access: list
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@knowledge_router.get("", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("knowledge", "read")),
):
    result = await session.execute(select(KnowledgeDocument))
    return [_to_response(d) for d in result.scalars().all()]


@knowledge_router.get("/{doc_id}", response_model=KnowledgeDocumentResponse)
async def get_knowledge_document(
    doc_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("knowledge", "read")),
):
    doc = await _get_doc_or_404(session, doc_id)
    return _to_response(doc)


@knowledge_router.post("", response_model=KnowledgeDocumentResponse, status_code=201)
async def create_knowledge_document(
    payload: KnowledgeDocumentCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("knowledge", "create")),
):
    doc = KnowledgeDocument(
        title=payload.title,
        category=payload.category,
        content=payload.content,
        agent_access=payload.agent_access,
        is_active=True,
    )
    session.add(doc)
    await session.flush()
    await log_activity(
        session, action="create", entity_type="knowledge_document",
        entity_id=str(doc.id), details={"title": doc.title}, user=_user.name,
    )
    await session.commit()
    await session.refresh(doc)
    return _to_response(doc)


@knowledge_router.post("/upload", response_model=KnowledgeDocumentResponse, status_code=201)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("geral"),
    agent_access: str = Form("[]"),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("knowledge", "create")),
):
    """Upload a file, extract text, store in S3, save to DB."""
    from src.config.settings import Settings
    from src.integrations.extraction.text_extractor import extract_text
    from src.integrations.s3.client import S3Client

    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    # Extract text content
    try:
        text_content = extract_text(file_bytes, filename, content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Upload to S3 (if configured)
    settings = Settings()
    file_key = None
    if settings.s3_bucket_name:
        s3 = S3Client(
            bucket=settings.s3_bucket_name,
            region=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
        )
        file_key = s3.upload(file_bytes, filename, content_type, category)

    # Parse agent_access from form data
    try:
        parsed_access = json.loads(agent_access)
    except json.JSONDecodeError:
        parsed_access = []

    doc = KnowledgeDocument(
        title=title,
        category=category,
        content=text_content,
        file_key=file_key,
        file_name=filename,
        file_type=content_type,
        file_size=len(file_bytes),
        agent_access=parsed_access,
        is_active=True,
    )
    session.add(doc)
    await session.flush()
    await log_activity(
        session, action="create", entity_type="knowledge_document",
        entity_id=str(doc.id), details={"title": title, "file_name": filename}, user=_user.name,
    )
    await session.commit()
    await session.refresh(doc)
    return _to_response(doc)


@knowledge_router.put("/{doc_id}", response_model=KnowledgeDocumentResponse)
async def update_knowledge_document(
    doc_id: str,
    payload: KnowledgeDocumentUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("knowledge", "update")),
):
    doc = await _get_doc_or_404(session, doc_id)

    changes = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(doc, field) != value:
            changes[field] = value
            setattr(doc, field, value)

    if changes:
        await log_activity(
            session, action="update", entity_type="knowledge_document",
            entity_id=str(doc.id), details=changes, user=_user.name,
        )
    await session.commit()
    await session.refresh(doc)
    return _to_response(doc)


@knowledge_router.delete("/{doc_id}", status_code=204)
async def delete_knowledge_document(
    doc_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("knowledge", "delete")),
):
    doc = await _get_doc_or_404(session, doc_id)

    # Delete from S3 if file exists
    if doc.file_key:
        try:
            from src.config.settings import Settings
            from src.integrations.s3.client import S3Client

            settings = Settings()
            if settings.s3_bucket_name:
                s3 = S3Client(
                    bucket=settings.s3_bucket_name,
                    region=settings.s3_region,
                    access_key_id=settings.s3_access_key_id,
                    secret_access_key=settings.s3_secret_access_key,
                    endpoint_url=settings.s3_endpoint_url,
                )
                s3.delete(doc.file_key)
        except Exception:
            pass  # Don't fail delete if S3 cleanup fails

    await log_activity(
        session, action="delete", entity_type="knowledge_document",
        entity_id=str(doc.id), details={"title": doc.title}, user=_user.name,
    )
    await session.delete(doc)
    await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_doc_or_404(session: AsyncSession, doc_id: str) -> KnowledgeDocument:
    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uid)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _to_response(doc: KnowledgeDocument) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=str(doc.id),
        title=doc.title,
        category=doc.category,
        content=doc.content,
        file_key=doc.file_key,
        file_name=doc.file_name,
        file_type=doc.file_type,
        file_size=doc.file_size,
        agent_access=doc.agent_access,
        is_active=doc.is_active,
    )
