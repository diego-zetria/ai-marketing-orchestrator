"""Tests for the Dashboard and Activity Log admin APIs."""

from __future__ import annotations

from types import SimpleNamespace

import bcrypt as _bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.admin.auth import _get_settings
from src.api.admin.deps import get_db
from src.api.app import create_app
from src.db.admin_models import AdminRole, AdminUser
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
# Dashboard Stats Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_stats_empty(authenticated_client):
    """Empty DB should return all zeros."""
    resp = await authenticated_client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_team_members"] == 0
    assert data["total_clients"] == 0
    assert data["total_rules"] == 0
    assert data["total_agents"] == 0
    assert data["recent_activity_count"] == 0


@pytest.mark.asyncio
async def test_dashboard_stats_with_data(authenticated_client):
    """After creating records, stats should reflect the counts."""
    # Create a team member
    await authenticated_client.post(
        "/api/admin/team-members",
        json={
            "clickup_user_id": "99999",
            "name": "Test User",
            "role": "designer",
            "telegram_chat_id": 100,
        },
    )

    # Create a client
    await authenticated_client.post(
        "/api/admin/clients",
        json={"name": "hotel10", "display_name": "ClientBeta"},
    )

    # Create an assignment rule
    await authenticated_client.put(
        "/api/admin/rules/assignment/social_media",
        json={"default_assignee_ids": ["user1"], "tags": ["instagram"]},
    )

    # Create a notification rule
    await authenticated_client.post(
        "/api/admin/rules/notification",
        json={
            "status": "em criacao",
            "notify_roles": ["designer"],
            "message_template": "Task moved to {status}",
        },
    )

    # Create an agent config
    await authenticated_client.put(
        "/api/admin/agents/briefing_analyzer",
        json={
            "model_id": "anthropic/claude-3.5-sonnet",
            "instructions": ["Analyze briefings"],
        },
    )

    resp = await authenticated_client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_team_members"] == 1
    assert data["total_clients"] == 1
    assert data["total_rules"] == 2  # 1 assignment + 1 notification
    assert data["total_agents"] == 1
    # Activity log entries from all the creates above
    assert data["recent_activity_count"] >= 4


@pytest.mark.asyncio
async def test_dashboard_activity(authenticated_client):
    """GET /dashboard/activity should return recent activity entries."""
    # Create a client to generate activity
    await authenticated_client.post(
        "/api/admin/clients",
        json={"name": "client_delta", "display_name": "ClientDelta"},
    )

    resp = await authenticated_client.get("/api/admin/dashboard/activity")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    entry = data[0]
    assert "id" in entry
    assert "action" in entry
    assert "entity_type" in entry
    assert "user" in entry
    assert "created_at" in entry


# ---------------------------------------------------------------------------
# Activity Log (Paginated) Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_log_paginated(authenticated_client):
    """GET /activity-log should return paginated activity logs."""
    # Generate several activity entries
    for i in range(5):
        await authenticated_client.post(
            "/api/admin/clients",
            json={"name": f"client{i}", "display_name": f"Client {i}"},
        )

    resp = await authenticated_client.get("/api/admin/activity-log?page=1&per_page=3")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert data["page"] == 1
    assert data["per_page"] == 3
    assert len(data["items"]) == 3
    assert data["total"] >= 5  # At least 5 creates

    # Get page 2
    resp = await authenticated_client.get("/api/admin/activity-log?page=2&per_page=3")
    data = resp.json()
    assert data["page"] == 2
    assert len(data["items"]) >= 2  # Remaining items


@pytest.mark.asyncio
async def test_activity_log_filtered(authenticated_client):
    """GET /activity-log with entity_type and action filters."""
    # Create a client (logs entity_type=client, action=create)
    await authenticated_client.post(
        "/api/admin/clients",
        json={"name": "filterclient", "display_name": "Filter Client"},
    )

    # Create an assignment rule (logs entity_type=assignment_rule, action=create)
    await authenticated_client.put(
        "/api/admin/rules/assignment/design",
        json={"default_assignee_ids": ["user1"], "tags": ["logo"]},
    )

    # Filter by entity_type
    resp = await authenticated_client.get("/api/admin/activity-log?entity_type=client")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["entity_type"] == "client" for item in data["items"])
    assert data["total"] >= 1

    # Filter by action
    resp = await authenticated_client.get("/api/admin/activity-log?action=create")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["action"] == "create" for item in data["items"])
    assert data["total"] >= 2  # At least the client + rule

    # Filter by both
    resp = await authenticated_client.get(
        "/api/admin/activity-log?entity_type=assignment_rule&action=create"
    )
    data = resp.json()
    assert all(
        item["entity_type"] == "assignment_rule" and item["action"] == "create"
        for item in data["items"]
    )
