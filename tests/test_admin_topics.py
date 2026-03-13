"""Tests for the Telegram Topics admin API."""

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
    import src.db.workflow_models  # noqa: F401

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
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_TOPIC = {
    "name": "client_delta_general",
    "label": "ClientDelta - General",
    "topic_id": 12345,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_topics_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/topics")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_topic(authenticated_client):
    resp = await authenticated_client.post("/api/admin/topics", json=_SAMPLE_TOPIC)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "client_delta_general"
    assert data["label"] == "ClientDelta - General"
    assert data["topic_id"] == 12345
    assert data["client_id"] is None
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_topic_duplicate(authenticated_client):
    resp1 = await authenticated_client.post("/api/admin/topics", json=_SAMPLE_TOPIC)
    assert resp1.status_code == 201

    resp2 = await authenticated_client.post("/api/admin/topics", json=_SAMPLE_TOPIC)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_update_topic(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/topics", json=_SAMPLE_TOPIC)
    topic_id = create_resp.json()["id"]

    resp = await authenticated_client.put(
        f"/api/admin/topics/{topic_id}",
        json={"label": "ClientDelta - Updated", "topic_id": 99999},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "ClientDelta - Updated"
    assert data["topic_id"] == 99999
    assert data["name"] == "client_delta_general"


@pytest.mark.asyncio
async def test_delete_topic(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/topics", json=_SAMPLE_TOPIC)
    topic_id = create_resp.json()["id"]

    resp = await authenticated_client.delete(f"/api/admin/topics/{topic_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_create_topic_with_client_id(authenticated_client):
    # First create a client to reference
    client_resp = await authenticated_client.post(
        "/api/admin/clients",
        json={"name": "client_alpha", "display_name": "ClientAlpha"},
    )
    assert client_resp.status_code == 201
    client_id = client_resp.json()["id"]

    payload = {
        **_SAMPLE_TOPIC,
        "name": "client_alpha_entregas",
        "client_id": client_id,
    }
    resp = await authenticated_client.post("/api/admin/topics", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["client_id"] == client_id
    assert data["name"] == "client_alpha_entregas"
