"""Tests for the Brand Guidelines admin API."""

from __future__ import annotations

from types import SimpleNamespace

import bcrypt as _bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.admin.auth import _get_settings
from src.api.admin.deps import get_db
from src.api.app import create_app
from src.db.admin_models import ActivityLog, AdminRole, AdminUser
from src.db.models import Base

_ADMIN_EMAIL = "admin@test.com"
_ADMIN_PASSWORD = "changeme"
_JWT_SECRET = "changeme-secret"

# ---------------------------------------------------------------------------
# SQLite compatibility: register PG type visitors so DDL generation works
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CLIENT = {
    "name": "hotel10",
    "display_name": "ClientBeta",
    "clickup_list_id": "list_123",
}


async def _create_client(client: AsyncClient) -> dict:
    resp = await client.post("/api/admin/clients", json=_SAMPLE_CLIENT)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_brands_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/brands")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_put_default_guideline(authenticated_client):
    """PUT /brands/default should create default brand guideline (upsert)."""
    resp = await authenticated_client.put(
        "/api/admin/brands/default",
        json={"content": "Use blue and white colors. Formal tone."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] is None
    assert data["content"] == "Use blue and white colors. Formal tone."
    assert "id" in data

    # PUT again to update
    resp = await authenticated_client.put(
        "/api/admin/brands/default",
        json={"content": "Updated: Use blue and gold colors."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Updated: Use blue and gold colors."

    # Should still be only one brand guideline
    resp = await authenticated_client.get("/api/admin/brands")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_put_client_guideline(authenticated_client):
    """PUT /brands/{client_id} should create client-specific guideline (upsert)."""
    # Create a client first
    client_data = await _create_client(authenticated_client)
    client_id = client_data["id"]

    resp = await authenticated_client.put(
        f"/api/admin/brands/{client_id}",
        json={"content": "ClientBeta: Warm and welcoming tone."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == client_id
    assert data["content"] == "ClientBeta: Warm and welcoming tone."


@pytest.mark.asyncio
async def test_get_default_guideline(authenticated_client):
    """GET /brands/default should return the default brand guideline."""
    # 404 when no default exists
    resp = await authenticated_client.get("/api/admin/brands/default")
    assert resp.status_code == 404

    # Create default
    await authenticated_client.put(
        "/api/admin/brands/default",
        json={"content": "Default guideline content."},
    )

    # Now it should be found
    resp = await authenticated_client.get("/api/admin/brands/default")
    assert resp.status_code == 200
    assert resp.json()["content"] == "Default guideline content."


@pytest.mark.asyncio
async def test_get_client_guideline(authenticated_client):
    """GET /brands/{client_id} should return client-specific guideline."""
    client_data = await _create_client(authenticated_client)
    client_id = client_data["id"]

    # 404 when no guideline exists for this client
    resp = await authenticated_client.get(f"/api/admin/brands/{client_id}")
    assert resp.status_code == 404

    # Create guideline
    await authenticated_client.put(
        f"/api/admin/brands/{client_id}",
        json={"content": "Client-specific content."},
    )

    # Now it should be found
    resp = await authenticated_client.get(f"/api/admin/brands/{client_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == client_id
    assert data["content"] == "Client-specific content."


@pytest.mark.asyncio
async def test_put_client_guideline_invalid_client(authenticated_client):
    """PUT /brands/{client_id} with non-existent client should return 404."""
    fake_uuid = "00000000-0000-0000-0000-000000000099"
    resp = await authenticated_client.put(
        f"/api/admin/brands/{fake_uuid}",
        json={"content": "This should fail."},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_activity_log_on_brand_change(authenticated_client, db_session):
    """Creating a brand guideline should log activity."""
    resp = await authenticated_client.put(
        "/api/admin/brands/default",
        json={"content": "Activity test content."},
    )
    assert resp.status_code == 200
    guideline_id = resp.json()["id"]

    result = await db_session.execute(
        select(ActivityLog).where(
            ActivityLog.entity_type == "brand_guideline",
            ActivityLog.entity_id == guideline_id,
            ActivityLog.action == "create",
        )
    )
    log_entry = result.scalar_one_or_none()
    assert log_entry is not None
    assert log_entry.details["type"] == "default"
    assert log_entry.user == "Test Admin"
