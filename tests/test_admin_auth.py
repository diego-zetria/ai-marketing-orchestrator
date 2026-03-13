from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import bcrypt as _bcrypt
import jwt
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


def _mock_settings():
    return SimpleNamespace(
        admin_password=_ADMIN_PASSWORD,
        admin_jwt_secret=_JWT_SECRET,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
async def client(db_session_factory):
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(client):
    resp = await client.post(
        "/api/admin/auth/login",
        json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
    )
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post(
        "/api/admin/auth/login",
        json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert isinstance(data["token"], str)
    assert len(data["token"]) > 0
    assert "user" in data
    assert data["user"]["email"] == _ADMIN_EMAIL


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post(
        "/api/admin/auth/login",
        json={"email": _ADMIN_EMAIL, "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Email ou senha invalidos"


@pytest.mark.asyncio
async def test_protected_endpoint_no_token(client):
    resp = await client.get("/api/admin/test-auth")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_protected_endpoint_with_token(authenticated_client):
    resp = await authenticated_client.get("/api/admin/test-auth")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True


@pytest.mark.asyncio
async def test_login_token_is_valid_jwt(client):
    resp = await client.post(
        "/api/admin/auth/login",
        json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
    )
    token = resp.json()["token"]
    payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    # sub is now the user UUID, not "admin"
    assert "sub" in payload
    assert "exp" in payload
    assert payload["email"] == _ADMIN_EMAIL


@pytest.mark.asyncio
async def test_expired_token_rejected(client):
    expired_payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, _JWT_SECRET, algorithm="HS256")
    client.headers["Authorization"] = f"Bearer {expired_token}"
    resp = await client.get("/api/admin/test-auth")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    client.headers["Authorization"] = "Bearer not-a-valid-token"
    resp = await client.get("/api/admin/test-auth")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_wrong_secret_token_rejected(client):
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
    client.headers["Authorization"] = "Bearer " + token
    resp = await client.get("/api/admin/test-auth")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_still_works(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
