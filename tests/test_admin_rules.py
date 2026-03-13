"""Tests for the Assignment Rules and Notification Rules admin API."""

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
# Assignment Rule Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_assignment_rules_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/rules/assignment")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_put_assignment_rule_creates(authenticated_client):
    """PUT on a non-existent service_type should upsert (create)."""
    resp = await authenticated_client.put(
        "/api/admin/rules/assignment/social_media",
        json={"default_assignee_ids": ["user1", "user2"], "tags": ["instagram"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_type"] == "social_media"
    assert data["default_assignee_ids"] == ["user1", "user2"]
    assert data["tags"] == ["instagram"]
    assert "id" in data

    # Verify it shows up in the list
    resp = await authenticated_client.get("/api/admin/rules/assignment")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_put_assignment_rule_updates(authenticated_client):
    """PUT on an existing service_type should update it."""
    # Create
    await authenticated_client.put(
        "/api/admin/rules/assignment/design",
        json={"default_assignee_ids": ["designer1"], "tags": ["logo"]},
    )

    # Update
    resp = await authenticated_client.put(
        "/api/admin/rules/assignment/design",
        json={"default_assignee_ids": ["designer1", "designer2"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_assignee_ids"] == ["designer1", "designer2"]
    # Tags unchanged because not sent in update
    assert data["tags"] == ["logo"]


# ---------------------------------------------------------------------------
# Notification Rule Tests
# ---------------------------------------------------------------------------

_SAMPLE_NOTIFICATION = {
    "status": "em criacao",
    "notify_roles": ["designer", "account"],
    "message_template": "Task moved to {status}",
}


@pytest.mark.asyncio
async def test_list_notification_rules_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/rules/notification")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_notification_rule(authenticated_client):
    resp = await authenticated_client.post(
        "/api/admin/rules/notification", json=_SAMPLE_NOTIFICATION
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "em criacao"
    assert data["notify_roles"] == ["designer", "account"]
    assert data["message_template"] == "Task moved to {status}"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_notification_rule_duplicate_status(authenticated_client):
    resp1 = await authenticated_client.post(
        "/api/admin/rules/notification", json=_SAMPLE_NOTIFICATION
    )
    assert resp1.status_code == 201

    resp2 = await authenticated_client.post(
        "/api/admin/rules/notification", json=_SAMPLE_NOTIFICATION
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_update_notification_rule(authenticated_client):
    # Create first
    await authenticated_client.post("/api/admin/rules/notification", json=_SAMPLE_NOTIFICATION)

    # Update
    resp = await authenticated_client.put(
        "/api/admin/rules/notification/em criacao",
        json={"notify_roles": ["designer"], "is_active": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notify_roles"] == ["designer"]
    assert data["is_active"] is False
    # Unchanged field
    assert data["message_template"] == "Task moved to {status}"


@pytest.mark.asyncio
async def test_update_notification_rule_not_found(authenticated_client):
    resp = await authenticated_client.put(
        "/api/admin/rules/notification/nonexistent",
        json={"is_active": False},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Activity Log Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_log_on_rule_change(authenticated_client, db_session):
    # Create an assignment rule via upsert
    resp = await authenticated_client.put(
        "/api/admin/rules/assignment/video",
        json={"default_assignee_ids": ["paul"], "tags": ["youtube"]},
    )
    assert resp.status_code == 200
    rule_id = resp.json()["id"]

    # Query activity log directly from the DB
    result = await db_session.execute(
        select(ActivityLog).where(
            ActivityLog.entity_type == "assignment_rule",
            ActivityLog.entity_id == rule_id,
            ActivityLog.action == "create",
        )
    )
    log_entry = result.scalar_one_or_none()
    assert log_entry is not None
    assert log_entry.details["service_type"] == "video"
    assert log_entry.user == "Test Admin"
