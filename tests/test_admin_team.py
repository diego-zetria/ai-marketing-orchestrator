"""Tests for the Team Members CRUD admin API."""

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
        # Translate PG schema names to None for SQLite
        execution_options={"schema_translate_map": {"marketing_bot": None}},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        # SQLite doesn't support schemas - temporarily remove them for DDL
        original_schemas: list[tuple[object, str | None]] = []
        for table in Base.metadata.tables.values():
            original_schemas.append((table, table.schema))
            table.schema = None

        await conn.run_sync(Base.metadata.create_all)

        # Restore original schemas so the model definitions stay correct
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

_SAMPLE_MEMBER = {
    "clickup_user_id": "12345",
    "name": "Alice",
    "role": "designer",
    "telegram_chat_id": 100,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_team_members_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/team-members")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 20


@pytest.mark.asyncio
async def test_create_team_member(authenticated_client):
    resp = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["clickup_user_id"] == "12345"
    assert data["role"] == "designer"
    assert data["telegram_chat_id"] == 100
    assert data["active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_team_member_duplicate_clickup_id(authenticated_client):
    resp1 = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    assert resp1.status_code == 201

    resp2 = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_update_team_member(authenticated_client):
    resp = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    member_id = resp.json()["id"]

    resp = await authenticated_client.put(
        f"/api/admin/team-members/{member_id}",
        json={"name": "Alice Updated", "role": "account"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice Updated"
    assert data["role"] == "account"
    # Unchanged fields stay the same
    assert data["clickup_user_id"] == "12345"
    assert data["telegram_chat_id"] == 100


@pytest.mark.asyncio
async def test_delete_team_member(authenticated_client):
    resp = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    member_id = resp.json()["id"]

    resp = await authenticated_client.delete(f"/api/admin/team-members/{member_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False


@pytest.mark.asyncio
async def test_list_includes_inactive(authenticated_client):
    # Create and soft-delete a member
    resp = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    member_id = resp.json()["id"]
    await authenticated_client.delete(f"/api/admin/team-members/{member_id}")

    # Default listing should not include inactive
    resp = await authenticated_client.get("/api/admin/team-members")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert len(resp.json()["items"]) == 0

    # With flag, inactive members appear
    resp = await authenticated_client.get("/api/admin/team-members?include_inactive=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["active"] is False


@pytest.mark.asyncio
async def test_update_nonexistent(authenticated_client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await authenticated_client.put(
        f"/api/admin/team-members/{fake_id}",
        json={"name": "Ghost"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Team member not found"


@pytest.mark.asyncio
async def test_activity_log_on_create(authenticated_client, db_session):
    resp = await authenticated_client.post("/api/admin/team-members", json=_SAMPLE_MEMBER)
    assert resp.status_code == 201
    member_id = resp.json()["id"]

    # Query activity log directly from the DB
    result = await db_session.execute(
        select(ActivityLog).where(
            ActivityLog.entity_type == "team_member",
            ActivityLog.entity_id == member_id,
            ActivityLog.action == "create",
        )
    )
    log_entry = result.scalar_one_or_none()
    assert log_entry is not None
    assert log_entry.details["name"] == "Alice"
    assert log_entry.user == "Test Admin"
