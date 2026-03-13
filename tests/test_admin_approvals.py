"""Tests for the Approvals admin API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bcrypt as _bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.admin.auth import _get_settings
from src.api.admin.deps import get_db
from src.api.app import create_app
from src.approval.models import (
    ApprovalAsset,
    ApprovalEvent,
    AssetVersion,
    MagicLink,
)
from src.db.admin_models import ActivityLog, AdminRole, AdminUser, Client
from src.db.models import Base

_ADMIN_EMAIL = "admin@test.com"
_ADMIN_PASSWORD = "changeme"
_JWT_SECRET = "changeme-secret"

# ---------------------------------------------------------------------------
# SQLite compatibility
# ---------------------------------------------------------------------------

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):

    def _visit_jsonb(self, type_, **kw):
        return self.visit_JSON(type_, **kw)

    SQLiteTypeCompiler.visit_JSONB = _visit_jsonb

if not hasattr(SQLiteTypeCompiler, "visit_UUID"):

    def _visit_uuid(self, type_, **kw):
        return "VARCHAR(36)"

    SQLiteTypeCompiler.visit_UUID = _visit_uuid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_settings():
    return SimpleNamespace(
        admin_password=_ADMIN_PASSWORD,
        admin_jwt_secret=_JWT_SECRET,
    )


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///",
        echo=False,
        execution_options={"schema_translate_map": {"marketing_bot": None}},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        original_schemas: list[tuple[object, str | None]] = []
        for table in Base.metadata.tables.values():
            original_schemas.append((table, table.schema))
            table.schema = None

        await conn.run_sync(Base.metadata.create_all)

        for table, schema in original_schemas:
            table.schema = schema

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(db_session_factory):
    async with db_session_factory() as session:
        yield session


@pytest.fixture
async def authenticated_client(db_session_factory):
    # Seed admin role + user
    async with db_session_factory() as seed_session:
        role = AdminRole(
            name="super_admin",
            description="Full access",
            permissions={
                "team": ["create", "read", "update", "delete"],
                "clients": ["create", "read", "update", "delete"],
                "rules": ["create", "read", "update", "delete"],
                "agents": ["create", "read", "update", "delete"],
                "tools": ["create", "read", "update", "delete"],
                "models": ["create", "read", "update", "delete"],
                "brands": ["create", "read", "update", "delete"],
                "knowledge": ["create", "read", "update", "delete"],
                "system": ["create", "read", "update", "delete"],
                "approvals": ["create", "read", "update", "delete"],
                "activity": ["read"],
                "dashboard": ["read"],
                "workflows": ["create", "read", "update", "delete"],
                "automations": ["create", "read", "update", "delete"],
                "topics": ["create", "read", "update", "delete"],
                "notifications": ["create", "read", "update", "delete"],
                "media": ["create", "read", "update", "delete"],
                "webhooks": ["create", "read", "update", "delete"],
                "users": ["create", "read", "update", "delete"],
            },
        )
        seed_session.add(role)
        await seed_session.flush()

        user = AdminUser(
            email=_ADMIN_EMAIL,
            name="Test Admin",
            password_hash=_bcrypt.hashpw(_ADMIN_PASSWORD.encode(), _bcrypt.gensalt()).decode(),
            role_id=role.id,
        )
        seed_session.add(user)
        await seed_session.commit()

    app = create_app()

    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[_get_settings] = _mock_settings
    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        token = resp.json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def sample_client(db_session):
    client = Client(
        name="client_alpha",
        display_name="ClientAlpha",
        email="cliente@client_alpha.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest.fixture
async def sample_asset(db_session, sample_client):
    asset = ApprovalAsset(
        client_id=sample_client.id,
        clickup_task_id="abc123",
        title="Post Instagram Fevereiro",
        description="Post para campanha de fevereiro",
        status="pending_review",
        current_version=1,
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)
    return asset


@pytest.fixture
async def sample_version(db_session, sample_asset):
    version = AssetVersion(
        asset_id=sample_asset.id,
        version_number=1,
        file_type="image",
        file_format="png",
        original_url="s3://approval-media-bucket/assets/test.png",
        thumbnail_url="https://cdn.example.com/thumb.png",
        file_size_bytes=102400,
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)
    return version


@pytest.fixture
async def sample_magic_link(db_session, sample_asset, sample_client):
    link = MagicLink(
        token="test-magic-token-123",
        asset_id=sample_asset.id,
        client_id=sample_client.id,
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        is_active=True,
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)
    return link


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_approval_stats(authenticated_client, sample_asset):
    resp = await authenticated_client.get("/api/admin/approvals/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_assets"] == 1
    assert data["pending_review"] == 1
    assert data["approved"] == 0
    assert data["changes_requested"] == 0


@pytest.mark.asyncio
async def test_list_approvals_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/approvals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 20


@pytest.mark.asyncio
async def test_list_approvals_with_data(authenticated_client, sample_asset, sample_client):
    resp = await authenticated_client.get("/api/admin/approvals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Post Instagram Fevereiro"
    assert data["items"][0]["client_name"] == "ClientAlpha"
    assert data["items"][0]["status"] == "pending_review"


@pytest.mark.asyncio
async def test_list_approvals_filter_status(authenticated_client, sample_asset):
    resp = await authenticated_client.get("/api/admin/approvals?status=approved")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0

    resp = await authenticated_client.get("/api/admin/approvals?status=pending_review")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_approvals_filter_client(authenticated_client, sample_asset, sample_client):
    resp = await authenticated_client.get(f"/api/admin/approvals?client_id={sample_client.id}")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["total"] == 1

    fake_id = str(uuid.uuid4())
    resp = await authenticated_client.get(f"/api/admin/approvals?client_id={fake_id}")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_approval_detail(authenticated_client, sample_asset, sample_version):
    resp = await authenticated_client.get(f"/api/admin/approvals/{sample_asset.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Post Instagram Fevereiro"
    assert data["description"] == "Post para campanha de fevereiro"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert isinstance(data["comments"], list)
    assert isinstance(data["decisions"], list)


@pytest.mark.asyncio
async def test_get_approval_detail_not_found(authenticated_client):
    fake_id = str(uuid.uuid4())
    resp = await authenticated_client.get(f"/api/admin/approvals/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_events(authenticated_client, sample_asset, db_session):
    ev = ApprovalEvent(
        asset_id=sample_asset.id,
        event_type="asset_created",
        actor="system",
        metadata_={"source": "webhook"},
    )
    db_session.add(ev)
    await db_session.commit()

    resp = await authenticated_client.get(f"/api/admin/approvals/{sample_asset.id}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["event_type"] == "asset_created"
    assert data[0]["actor"] == "system"


@pytest.mark.asyncio
async def test_add_comment(authenticated_client, sample_asset, db_session):
    resp = await authenticated_client.post(
        f"/api/admin/approvals/{sample_asset.id}/comments",
        json={"content": "Precisa ajustar a fonte"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Precisa ajustar a fonte"
    assert data["author_type"] == "admin"

    # Verify activity log was created
    result = await db_session.execute(
        select(ActivityLog).where(
            ActivityLog.entity_type == "approval_asset",
            ActivityLog.entity_id == str(sample_asset.id),
            ActivityLog.action == "add_comment",
        )
    )
    log_entry = result.scalar_one_or_none()
    assert log_entry is not None


@pytest.mark.asyncio
async def test_add_comment_empty(authenticated_client, sample_asset):
    resp = await authenticated_client.post(
        f"/api/admin/approvals/{sample_asset.id}/comments",
        json={"content": ""},
    )
    # Empty string passes validation — content is a string field, not explicitly min_length
    # The endpoint should still create it. If we want validation, we'd add min_length to the schema.
    # For now, testing the 201 response.
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_resend_email(
    authenticated_client, sample_asset, sample_version, sample_magic_link, sample_client
):
    with patch("src.approval.services.email.EmailService") as mock_email_cls:
        mock_instance = mock_email_cls.return_value
        mock_instance.send_new_asset_email = AsyncMock(return_value={"MessageId": "test-123"})

        resp = await authenticated_client.post(
            f"/api/admin/approvals/{sample_asset.id}/resend-email"
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Email reenviado com sucesso"

        mock_instance.send_new_asset_email.assert_called_once()
        call_kwargs = mock_instance.send_new_asset_email.call_args.kwargs
        assert call_kwargs["to_email"] == "cliente@client_alpha.com"
        assert call_kwargs["asset_title"] == "Post Instagram Fevereiro"


@pytest.mark.asyncio
async def test_auth_required(db_session_factory):
    """All endpoints should return 401 without a token."""
    app = create_app()

    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[_get_settings] = _mock_settings
    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        endpoints = [
            ("GET", "/api/admin/approvals/stats"),
            ("GET", "/api/admin/approvals"),
            ("GET", f"/api/admin/approvals/{uuid.uuid4()}"),
            ("GET", f"/api/admin/approvals/{uuid.uuid4()}/events"),
            ("GET", f"/api/admin/approvals/{uuid.uuid4()}/media-url/{uuid.uuid4()}"),
            ("POST", f"/api/admin/approvals/{uuid.uuid4()}/comments"),
            ("POST", f"/api/admin/approvals/{uuid.uuid4()}/resend-email"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = await client.get(path)
            else:
                resp = await client.post(path, json={"content": "test"})
            assert resp.status_code == 401, f"{method} {path} should require auth"

    app.dependency_overrides.clear()
