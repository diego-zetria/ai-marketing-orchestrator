"""Tests for the Workflow Definitions admin API."""

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

_SAMPLE_WORKFLOW = {
    "name": "default_workflow",
    "display_name": "Default Workflow",
    "description": "Standard agency workflow",
    "statuses": ["planejamento", "desenvolvimento", "em_criacao", "revisao", "aprovado"],
    "transitions": {
        "planejamento": ["desenvolvimento"],
        "desenvolvimento": ["em_criacao"],
        "em_criacao": ["revisao"],
        "revisao": ["aprovado", "em_criacao"],
    },
    "transition_actions": {},
    "is_default": False,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_workflows_empty(authenticated_client):
    resp = await authenticated_client.get("/api/admin/workflows")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_workflow(authenticated_client):
    resp = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "default_workflow"
    assert data["display_name"] == "Default Workflow"
    assert data["description"] == "Standard agency workflow"
    assert data["statuses"] == _SAMPLE_WORKFLOW["statuses"]
    assert data["transitions"] == _SAMPLE_WORKFLOW["transitions"]
    assert data["is_default"] is False
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_workflow_duplicate_name(authenticated_client):
    resp1 = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    assert resp1.status_code == 201

    resp2 = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_get_workflow(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    workflow_id = create_resp.json()["id"]

    resp = await authenticated_client.get(f"/api/admin/workflows/{workflow_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "default_workflow"


@pytest.mark.asyncio
async def test_get_workflow_not_found(authenticated_client):
    resp = await authenticated_client.get(
        "/api/admin/workflows/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_workflow(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    workflow_id = create_resp.json()["id"]

    resp = await authenticated_client.put(
        f"/api/admin/workflows/{workflow_id}",
        json={"display_name": "Updated Workflow", "description": "Updated description"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Updated Workflow"
    assert data["description"] == "Updated description"
    assert data["name"] == "default_workflow"
    assert data["statuses"] == _SAMPLE_WORKFLOW["statuses"]


@pytest.mark.asyncio
async def test_update_workflow_not_found(authenticated_client):
    resp = await authenticated_client.put(
        "/api/admin/workflows/00000000-0000-0000-0000-000000000000",
        json={"display_name": "Does not matter"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_workflow(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    workflow_id = create_resp.json()["id"]

    resp = await authenticated_client.delete(f"/api/admin/workflows/{workflow_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False

    list_resp = await authenticated_client.get("/api/admin/workflows?is_active=true")
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_workflow_not_found(authenticated_client):
    resp = await authenticated_client.delete(
        "/api/admin/workflows/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_default_workflow(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    workflow_id = create_resp.json()["id"]

    resp = await authenticated_client.put(f"/api/admin/workflows/{workflow_id}/set-default")
    assert resp.status_code == 200
    assert resp.json()["is_default"] is True


@pytest.mark.asyncio
async def test_set_default_unmarks_others(authenticated_client):
    resp1 = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    id1 = resp1.json()["id"]

    second_workflow = {
        **_SAMPLE_WORKFLOW,
        "name": "second_workflow",
        "display_name": "Second Workflow",
    }
    resp2 = await authenticated_client.post("/api/admin/workflows", json=second_workflow)
    id2 = resp2.json()["id"]

    await authenticated_client.put(f"/api/admin/workflows/{id1}/set-default")
    await authenticated_client.put(f"/api/admin/workflows/{id2}/set-default")

    resp = await authenticated_client.get(f"/api/admin/workflows/{id1}")
    assert resp.json()["is_default"] is False

    resp = await authenticated_client.get(f"/api/admin/workflows/{id2}")
    assert resp.json()["is_default"] is True


@pytest.mark.asyncio
async def test_create_workflow_invalid_transitions(authenticated_client):
    payload = {
        **_SAMPLE_WORKFLOW,
        "name": "bad_transitions",
        "transitions": {
            "nonexistent_status": ["desenvolvimento"],
        },
    }
    resp = await authenticated_client.post("/api/admin/workflows", json=payload)
    assert resp.status_code == 422
    assert "nonexistent_status" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_workflow_invalid_transition_target(authenticated_client):
    payload = {
        **_SAMPLE_WORKFLOW,
        "name": "bad_target",
        "transitions": {
            "planejamento": ["nonexistent_target"],
        },
    }
    resp = await authenticated_client.post("/api/admin/workflows", json=payload)
    assert resp.status_code == 422
    assert "nonexistent_target" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_workflows_filter_active(authenticated_client):
    create_resp = await authenticated_client.post("/api/admin/workflows", json=_SAMPLE_WORKFLOW)
    workflow_id = create_resp.json()["id"]

    await authenticated_client.delete(f"/api/admin/workflows/{workflow_id}")

    resp_active = await authenticated_client.get("/api/admin/workflows?is_active=true")
    assert len(resp_active.json()) == 0

    resp_inactive = await authenticated_client.get("/api/admin/workflows?is_active=false")
    assert len(resp_inactive.json()) == 1
    assert resp_inactive.json()[0]["is_active"] is False

    resp_all = await authenticated_client.get("/api/admin/workflows")
    assert len(resp_all.json()) == 1
