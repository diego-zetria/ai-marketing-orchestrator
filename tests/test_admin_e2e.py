"""End-to-end integration tests that exercise complete flows across multiple
admin API endpoints.  Each test function represents a realistic workflow that
a front-end admin user would perform, verifying that the data flows correctly
through the system and that side-effects (activity log, dashboard counters)
are kept consistent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import bcrypt as _bcrypt
import jwt
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
async def app_instance(db_session_factory):
    """Create a FastAPI app wired to the in-memory SQLite engine."""
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
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(app_instance):
    """HTTP client with a valid JWT already set."""
    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/admin/auth/login",
            json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        )
        token = resp.json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture
async def unauthenticated_client(app_instance):
    """HTTP client with NO Authorization header."""
    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_team_member(
    client: AsyncClient, *, clickup_user_id: str, name: str, role: str, telegram_chat_id: int = 100
) -> dict:
    resp = await client.post(
        "/api/admin/team-members",
        json={
            "clickup_user_id": clickup_user_id,
            "name": name,
            "role": role,
            "telegram_chat_id": telegram_chat_id,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _items(resp_json):
    """Extract items list from paginated or plain list responses."""
    if isinstance(resp_json, list):
        return resp_json
    return resp_json.get("items", resp_json)


async def _create_client(
    client: AsyncClient,
    *,
    name: str,
    display_name: str,
    clickup_list_id: str = "list_001",
    designer_id: str | None = None,
    account_id: str | None = None,
) -> dict:
    payload: dict = {
        "name": name,
        "display_name": display_name,
        "clickup_list_id": clickup_list_id,
    }
    if designer_id is not None:
        payload["designer_id"] = designer_id
    if account_id is not None:
        payload["account_id"] = account_id
    resp = await client.post("/api/admin/clients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Flow 1 -- Full Team Member Lifecycle + Activity Log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow1_team_member_lifecycle(authenticated_client, db_session):
    """Create -> verify in list -> update -> verify -> check activity log
    -> delete -> verify soft-delete -> final activity log check."""

    # 1. Create a team member
    member = await _create_team_member(
        authenticated_client,
        clickup_user_id="tm_001",
        name="Alice",
        role="designer",
        telegram_chat_id=111,
    )
    member_id = member["id"]
    assert member["name"] == "Alice"
    assert member["role"] == "designer"
    assert member["active"] is True

    # 2. Verify member appears in the list
    resp = await authenticated_client.get("/api/admin/team-members")
    assert resp.status_code == 200
    members_list = _items(resp.json())
    assert len(members_list) == 1
    assert members_list[0]["id"] == member_id

    # 3. Update the member's role
    resp = await authenticated_client.put(
        f"/api/admin/team-members/{member_id}",
        json={"name": "Alice Updated", "role": "account"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == "Alice Updated"
    assert updated["role"] == "account"
    assert updated["clickup_user_id"] == "tm_001"  # unchanged

    # 4. Verify the update is reflected when fetching the list
    resp = await authenticated_client.get("/api/admin/team-members")
    assert _items(resp.json())[0]["role"] == "account"

    # 5. Check activity log for create + update entries (via DB)
    result = await db_session.execute(
        select(ActivityLog)
        .where(
            ActivityLog.entity_type == "team_member",
            ActivityLog.entity_id == member_id,
        )
        .order_by(ActivityLog.created_at)
    )
    logs = result.scalars().all()
    actions = [log.action for log in logs]
    assert "create" in actions
    assert "update" in actions

    # 6. Delete the member (soft-delete)
    resp = await authenticated_client.delete(f"/api/admin/team-members/{member_id}")
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    # 7. Default list should be empty now
    resp = await authenticated_client.get("/api/admin/team-members")
    assert len(_items(resp.json())) == 0

    # 8. With include_inactive the member still exists
    resp = await authenticated_client.get(
        "/api/admin/team-members?include_inactive=true"
    )
    assert len(_items(resp.json())) == 1
    assert _items(resp.json())[0]["active"] is False

    # 9. Activity log should now also contain a "delete" entry
    result = await db_session.execute(
        select(ActivityLog)
        .where(
            ActivityLog.entity_type == "team_member",
            ActivityLog.entity_id == member_id,
        )
        .order_by(ActivityLog.created_at)
    )
    logs = result.scalars().all()
    actions = [log.action for log in logs]
    assert "create" in actions
    assert "update" in actions
    assert "delete" in actions
    assert len(actions) == 3


# ---------------------------------------------------------------------------
# Flow 2 -- Full Client Lifecycle with FK Relations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow2_client_lifecycle_with_fk_relations(
    authenticated_client, db_session
):
    """Create team members -> create client linked to them -> update FK
    -> delete client -> verify activity log."""

    # 1. Create a designer
    designer = await _create_team_member(
        authenticated_client,
        clickup_user_id="des_001",
        name="Designer A",
        role="designer",
    )

    # 2. Create an account manager
    account = await _create_team_member(
        authenticated_client,
        clickup_user_id="acc_001",
        name="Account Manager A",
        role="account",
    )

    # 3. Create client linked to designer and account
    client_data = await _create_client(
        authenticated_client,
        name="hotel10",
        display_name="ClientBeta",
        clickup_list_id="list_h10",
        designer_id=designer["id"],
        account_id=account["id"],
    )
    client_id = client_data["id"]
    assert client_data["designer_id"] == designer["id"]
    assert client_data["account_id"] == account["id"]

    # 4. Verify client appears in list with correct FK references
    resp = await authenticated_client.get("/api/admin/clients")
    assert resp.status_code == 200
    clients = _items(resp.json())
    assert len(clients) == 1
    assert clients[0]["designer_id"] == designer["id"]
    assert clients[0]["account_id"] == account["id"]

    # 5. Create another designer and re-assign the client
    new_designer = await _create_team_member(
        authenticated_client,
        clickup_user_id="des_002",
        name="Pedro",
        role="designer",
        telegram_chat_id=222,
    )
    resp = await authenticated_client.put(
        f"/api/admin/clients/{client_id}",
        json={"designer_id": new_designer["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["designer_id"] == new_designer["id"]
    assert resp.json()["account_id"] == account["id"]  # unchanged

    # 6. Verify the update is reflected in list
    resp = await authenticated_client.get("/api/admin/clients")
    assert _items(resp.json())[0]["designer_id"] == new_designer["id"]

    # 7. Delete the client (soft-delete)
    resp = await authenticated_client.delete(f"/api/admin/clients/{client_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Default list is empty
    resp = await authenticated_client.get("/api/admin/clients")
    assert len(_items(resp.json())) == 0

    # With flag, still visible
    resp = await authenticated_client.get("/api/admin/clients?include_inactive=true")
    assert len(_items(resp.json())) == 1

    # 8. Activity log should contain create + update + delete for the client
    result = await db_session.execute(
        select(ActivityLog)
        .where(
            ActivityLog.entity_type == "client",
            ActivityLog.entity_id == client_id,
        )
        .order_by(ActivityLog.created_at)
    )
    logs = result.scalars().all()
    actions = [log.action for log in logs]
    assert "create" in actions
    assert "update" in actions
    assert "delete" in actions


# ---------------------------------------------------------------------------
# Flow 3 -- Assignment Rules + Notification Rules Configuration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow3_rules_configuration(authenticated_client):
    """Create and update assignment and notification rules end-to-end."""

    # 1. Create a team member (will be referenced conceptually)
    member = await _create_team_member(
        authenticated_client,
        clickup_user_id="rule_user_001",
        name="Gus",
        role="ads",
    )

    # 2. Create an assignment rule for "design"
    resp = await authenticated_client.put(
        "/api/admin/rules/assignment/design",
        json={
            "default_assignee_ids": [member["clickup_user_id"]],
            "tags": ["logo"],
        },
    )
    assert resp.status_code == 200
    rule = resp.json()
    assert rule["service_type"] == "design"
    assert rule["default_assignee_ids"] == [member["clickup_user_id"]]
    assert rule["tags"] == ["logo"]
    rule_id = rule["id"]

    # 3. Verify the rule is saved correctly via GET
    resp = await authenticated_client.get("/api/admin/rules/assignment")
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 1
    assert rules[0]["id"] == rule_id
    assert rules[0]["tags"] == ["logo"]

    # 4. Update the rule to add more tags
    resp = await authenticated_client.put(
        "/api/admin/rules/assignment/design",
        json={"tags": ["logo", "instagram", "banner"]},
    )
    assert resp.status_code == 200
    updated_rule = resp.json()
    assert updated_rule["tags"] == ["logo", "instagram", "banner"]
    # Assignees unchanged
    assert updated_rule["default_assignee_ids"] == [member["clickup_user_id"]]

    # 5. Create a notification rule for "revisao" status
    resp = await authenticated_client.post(
        "/api/admin/rules/notification",
        json={
            "status": "revisao",
            "notify_roles": ["designer", "account"],
            "message_template": "Task {task_name} needs review",
        },
    )
    assert resp.status_code == 201
    notif_rule = resp.json()
    assert notif_rule["status"] == "revisao"
    assert notif_rule["notify_roles"] == ["designer", "account"]
    assert notif_rule["is_active"] is True

    # 6. Verify the notification rule in the list
    resp = await authenticated_client.get("/api/admin/rules/notification")
    assert resp.status_code == 200
    notif_rules = _items(resp.json())
    assert len(notif_rules) == 1
    assert notif_rules[0]["status"] == "revisao"

    # 7. Update notification rule's is_active to false
    resp = await authenticated_client.put(
        "/api/admin/rules/notification/revisao",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    # message_template unchanged
    assert resp.json()["message_template"] == "Task {task_name} needs review"

    # 8. Verify the toggle worked via list
    resp = await authenticated_client.get("/api/admin/rules/notification")
    assert _items(resp.json())[0]["is_active"] is False


# ---------------------------------------------------------------------------
# Flow 4 -- Agent Config + Brand Guidelines + System Config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow4_agent_brand_system_config(authenticated_client):
    """Upsert agent config, brand guidelines (default + client-specific),
    and system config entries, verifying list endpoints along the way."""

    # 1. Upsert an agent config for "briefing_analyzer"
    resp = await authenticated_client.put(
        "/api/admin/agents/briefing_analyzer",
        json={
            "model_id": "openrouter/anthropic/claude-sonnet-4",
            "instructions": ["Analyze briefings", "Extract tasks"],
            "is_active": True,
        },
    )
    assert resp.status_code == 200
    agent = resp.json()
    assert agent["agent_name"] == "briefing_analyzer"
    assert agent["model_id"] == "openrouter/anthropic/claude-sonnet-4"

    # 2. Verify it appears in the list
    resp = await authenticated_client.get("/api/admin/agents")
    assert resp.status_code == 200
    assert len(_items(resp.json())) == 1
    assert _items(resp.json())[0]["agent_name"] == "briefing_analyzer"

    # 3. Update the model_id
    resp = await authenticated_client.put(
        "/api/admin/agents/briefing_analyzer",
        json={"model_id": "openrouter/openai/gpt-4o"},
    )
    assert resp.status_code == 200
    assert resp.json()["model_id"] == "openrouter/openai/gpt-4o"
    # Instructions unchanged
    assert resp.json()["instructions"] == ["Analyze briefings", "Extract tasks"]

    # 4. Create default brand guideline
    resp = await authenticated_client.put(
        "/api/admin/brands/default",
        json={"content": "Use formal Portuguese. Blue and white color palette."},
    )
    assert resp.status_code == 200
    default_brand = resp.json()
    assert default_brand["client_id"] is None
    assert "Blue and white" in default_brand["content"]

    # 5. Create a client
    client_data = await _create_client(
        authenticated_client,
        name="client_delta",
        display_name="ClientDelta",
        clickup_list_id="list_client_delta",
    )
    client_id = client_data["id"]

    # 6. Create client-specific brand guideline
    resp = await authenticated_client.put(
        f"/api/admin/brands/{client_id}",
        json={"content": "ClientDelta: Modern and tech-forward tone. Green palette."},
    )
    assert resp.status_code == 200
    client_brand = resp.json()
    assert client_brand["client_id"] == client_id
    assert "ClientDelta" in client_brand["content"]

    # 7. Verify both guidelines in the list
    resp = await authenticated_client.get("/api/admin/brands")
    assert resp.status_code == 200
    brands = resp.json()
    assert len(brands) == 2
    # One is default (client_id=None), one is client-specific
    client_ids = [b["client_id"] for b in brands]
    assert None in client_ids
    assert client_id in client_ids

    # 8. Upsert a system config key
    resp = await authenticated_client.put(
        "/api/admin/system-config/default_list_id",
        json={
            "value": "list_main_001",
            "description": "Default ClickUp list for new tasks",
        },
    )
    assert resp.status_code == 200
    config = resp.json()
    assert config["key"] == "default_list_id"
    assert config["value"] == "list_main_001"
    assert config["description"] == "Default ClickUp list for new tasks"

    # 9. Verify it appears in the system config list
    resp = await authenticated_client.get("/api/admin/system-config")
    assert resp.status_code == 200
    configs = resp.json()
    assert len(configs) == 1
    assert configs[0]["key"] == "default_list_id"

    # 10. Verify individual GET works
    resp = await authenticated_client.get(
        "/api/admin/system-config/default_list_id"
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "list_main_001"


# ---------------------------------------------------------------------------
# Flow 5 -- Dashboard Stats Reflect Changes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow5_dashboard_stats_reflect_changes(authenticated_client):
    """Verify dashboard counters change as entities are created."""

    # 1. Get initial dashboard stats (all zeros)
    resp = await authenticated_client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 200
    initial = resp.json()
    assert initial["total_team_members"] == 0
    assert initial["total_clients"] == 0
    assert initial["total_rules"] == 0
    assert initial["total_agents"] == 0
    assert initial["recent_activity_count"] == 0

    # 2. Create 2 team members
    await _create_team_member(
        authenticated_client,
        clickup_user_id="dash_001",
        name="Member One",
        role="designer",
    )
    await _create_team_member(
        authenticated_client,
        clickup_user_id="dash_002",
        name="Member Two",
        role="account",
        telegram_chat_id=222,
    )

    # 3. Create 1 client
    await _create_client(
        authenticated_client,
        name="client_alpha",
        display_name="ClientAlpha",
    )

    # 4. Create an agent config and a rule to test those counters too
    await authenticated_client.put(
        "/api/admin/agents/summary_gen",
        json={
            "model_id": "openrouter/openai/gpt-4o-mini",
            "instructions": ["Summarize daily tasks"],
        },
    )
    await authenticated_client.put(
        "/api/admin/rules/assignment/social_media",
        json={"default_assignee_ids": ["dash_001"], "tags": ["instagram"]},
    )

    # 5. Get dashboard stats again
    resp = await authenticated_client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["total_team_members"] == 2
    assert updated["total_clients"] == 1
    assert updated["total_agents"] == 1
    assert updated["total_rules"] == 1  # 1 assignment rule
    # Activity log should have entries for all creates
    assert updated["recent_activity_count"] >= 5

    # 6. Verify dashboard activity returns recent entries
    resp = await authenticated_client.get("/api/admin/dashboard/activity")
    assert resp.status_code == 200
    activity = resp.json()
    assert len(activity) >= 5
    # Each entry should have required fields
    for entry in activity:
        assert "id" in entry
        assert "action" in entry
        assert "entity_type" in entry
        assert "user" in entry
        assert "created_at" in entry

    # 7. Verify activity-log pagination works across the accumulated entries
    resp = await authenticated_client.get(
        "/api/admin/activity-log?page=1&per_page=2"
    )
    assert resp.status_code == 200
    paginated = resp.json()
    assert paginated["page"] == 1
    assert paginated["per_page"] == 2
    assert len(paginated["items"]) == 2
    assert paginated["total"] >= 5


# ---------------------------------------------------------------------------
# Flow 6 -- Auth Protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow6_auth_protection(unauthenticated_client):
    """Verify that protected endpoints reject unauthenticated requests and
    that the login flow works correctly end-to-end."""

    c = unauthenticated_client

    # 1. Try accessing several protected endpoints without a token
    protected_endpoints = [
        ("GET", "/api/admin/team-members"),
        ("GET", "/api/admin/clients"),
        ("GET", "/api/admin/rules/assignment"),
        ("GET", "/api/admin/rules/notification"),
        ("GET", "/api/admin/agents"),
        ("GET", "/api/admin/brands"),
        ("GET", "/api/admin/system-config"),
        ("GET", "/api/admin/dashboard/stats"),
        ("GET", "/api/admin/activity-log"),
        ("GET", "/api/admin/test-auth"),
    ]
    for method, url in protected_endpoints:
        if method == "GET":
            resp = await c.get(url)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for {method} {url}, got {resp.status_code}"
        )

    # 2. Login with wrong password
    resp = await c.post(
        "/api/admin/auth/login",
        json={"email": _ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Email ou senha invalidos"

    # 3. Login with correct password
    resp = await c.post(
        "/api/admin/auth/login",
        json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    token = data["token"]

    # 4. Access protected endpoint with valid token
    c.headers["Authorization"] = f"Bearer {token}"
    resp = await c.get("/api/admin/test-auth")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True

    # 5. Use an expired token
    expired_payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, _JWT_SECRET, algorithm="HS256")
    c.headers["Authorization"] = f"Bearer {expired_token}"
    resp = await c.get("/api/admin/test-auth")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"

    # 6. Use a completely invalid token
    c.headers["Authorization"] = "Bearer this-is-not-a-jwt"
    resp = await c.get("/api/admin/test-auth")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"

    # 7. Use a token signed with the wrong secret
    wrong_secret_payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    wrong_token = jwt.encode(
        wrong_secret_payload, "totally-wrong-secret", algorithm="HS256"
    )
    c.headers["Authorization"] = f"Bearer {wrong_token}"
    resp = await c.get("/api/admin/test-auth")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Flow 7 -- Cross-Entity Activity Log Filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow7_activity_log_filtering_across_entities(authenticated_client):
    """Perform operations on multiple entity types and verify that activity log
    filtering by entity_type and action works correctly."""

    # Create a team member
    member = await _create_team_member(
        authenticated_client,
        clickup_user_id="log_001",
        name="LogTest User",
        role="designer",
    )
    member_id = member["id"]

    # Create a client
    await _create_client(
        authenticated_client,
        name="logclient",
        display_name="Log Client",
    )

    # Create an assignment rule
    await authenticated_client.put(
        "/api/admin/rules/assignment/video",
        json={"default_assignee_ids": ["paul"], "tags": ["youtube"]},
    )

    # Update the team member (generates an "update" action)
    await authenticated_client.put(
        f"/api/admin/team-members/{member_id}",
        json={"name": "LogTest User Updated"},
    )

    # Delete the team member (generates a "delete" action)
    await authenticated_client.delete(f"/api/admin/team-members/{member_id}")

    # --- Filter by entity_type ---

    # Only team_member entries
    resp = await authenticated_client.get(
        "/api/admin/activity-log?entity_type=team_member"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3  # create + update + delete
    assert all(
        item["entity_type"] == "team_member" for item in data["items"]
    )

    # Only client entries
    resp = await authenticated_client.get(
        "/api/admin/activity-log?entity_type=client"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(item["entity_type"] == "client" for item in data["items"])

    # --- Filter by action ---

    # Only "create" actions
    resp = await authenticated_client.get(
        "/api/admin/activity-log?action=create"
    )
    assert resp.status_code == 200
    data = resp.json()
    # We have at least: team_member create + client create + rule create
    assert data["total"] >= 3
    assert all(item["action"] == "create" for item in data["items"])

    # Only "delete" actions
    resp = await authenticated_client.get(
        "/api/admin/activity-log?action=delete"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(item["action"] == "delete" for item in data["items"])

    # --- Combined filter ---
    resp = await authenticated_client.get(
        "/api/admin/activity-log?entity_type=team_member&action=update"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(
        item["entity_type"] == "team_member" and item["action"] == "update"
        for item in data["items"]
    )


# ---------------------------------------------------------------------------
# Flow 8 -- Multiple System Config + Agent Config Updates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow8_system_and_agent_config_updates(authenticated_client):
    """Create several system config keys and agent configs, update them,
    and verify idempotent upsert behavior."""

    # -- System config: create two keys --
    resp = await authenticated_client.put(
        "/api/admin/system-config/clickup_team_id",
        json={"value": "YOUR_CLICKUP_TEAM_ID", "description": "ClickUp team ID"},
    )
    assert resp.status_code == 200

    resp = await authenticated_client.put(
        "/api/admin/system-config/telegram_group_id",
        json={"value": -1001234567890, "description": "Main Telegram group"},
    )
    assert resp.status_code == 200

    # Verify both appear in the list
    resp = await authenticated_client.get("/api/admin/system-config")
    assert resp.status_code == 200
    assert len(_items(resp.json())) == 2

    # Update one of them (idempotent upsert)
    resp = await authenticated_client.put(
        "/api/admin/system-config/clickup_team_id",
        json={"value": "9017128591", "description": "ClickUp team ID (updated)"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "9017128591"
    assert resp.json()["description"] == "ClickUp team ID (updated)"

    # Still only 2 entries (upsert, not create duplicate)
    resp = await authenticated_client.get("/api/admin/system-config")
    assert len(_items(resp.json())) == 2

    # -- Agent configs: create two agents --
    resp = await authenticated_client.put(
        "/api/admin/agents/content_reviewer",
        json={
            "model_id": "openrouter/anthropic/claude-sonnet-4",
            "instructions": ["Review content quality"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["agent_name"] == "content_reviewer"
    assert resp.json()["is_active"] is True

    resp = await authenticated_client.put(
        "/api/admin/agents/schedule_generator",
        json={
            "model_id": "openrouter/openai/gpt-4o",
            "instructions": ["Generate post schedules"],
        },
    )
    assert resp.status_code == 200

    # Verify both in list
    resp = await authenticated_client.get("/api/admin/agents")
    assert len(_items(resp.json())) == 2

    # Deactivate one agent
    resp = await authenticated_client.put(
        "/api/admin/agents/content_reviewer",
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    # Instructions unchanged
    assert resp.json()["instructions"] == ["Review content quality"]

    # Still 2 agents (upsert)
    resp = await authenticated_client.get("/api/admin/agents")
    assert len(_items(resp.json())) == 2

    # Verify dashboard reflects agent count
    resp = await authenticated_client.get("/api/admin/dashboard/stats")
    assert resp.json()["total_agents"] == 2


# ---------------------------------------------------------------------------
# Flow 9 -- Error Handling Across Multiple Endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow9_error_handling_cross_endpoint(authenticated_client):
    """Verify that various error conditions are handled correctly across
    different endpoints, ensuring the system stays consistent."""

    fake_uuid = "00000000-0000-0000-0000-000000000099"

    # 1. Update a nonexistent team member -> 404
    resp = await authenticated_client.put(
        f"/api/admin/team-members/{fake_uuid}",
        json={"name": "Ghost"},
    )
    assert resp.status_code == 404

    # 2. Create a client with a non-existent designer_id -> 400
    resp = await authenticated_client.post(
        "/api/admin/clients",
        json={
            "name": "badclient",
            "display_name": "Bad Client",
            "designer_id": fake_uuid,
        },
    )
    assert resp.status_code == 400
    assert "designer_id" in resp.json()["detail"]

    # 3. Create a client with non-existent account_id -> 400
    resp = await authenticated_client.post(
        "/api/admin/clients",
        json={
            "name": "badclient2",
            "display_name": "Bad Client 2",
            "account_id": fake_uuid,
        },
    )
    assert resp.status_code == 400
    assert "account_id" in resp.json()["detail"]

    # 4. Create duplicate team member clickup_user_id -> 409
    await _create_team_member(
        authenticated_client,
        clickup_user_id="dup_001",
        name="Original",
        role="designer",
    )
    resp = await authenticated_client.post(
        "/api/admin/team-members",
        json={
            "clickup_user_id": "dup_001",
            "name": "Duplicate",
            "role": "designer",
            "telegram_chat_id": 999,
        },
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]

    # 5. Create duplicate client name -> 409
    await _create_client(
        authenticated_client,
        name="uniqueclient",
        display_name="Unique Client",
    )
    resp = await authenticated_client.post(
        "/api/admin/clients",
        json={"name": "uniqueclient", "display_name": "Duplicate"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]

    # 6. Create duplicate notification rule status -> 409
    await authenticated_client.post(
        "/api/admin/rules/notification",
        json={
            "status": "aprovado",
            "notify_roles": ["account"],
            "message_template": "Approved!",
        },
    )
    resp = await authenticated_client.post(
        "/api/admin/rules/notification",
        json={
            "status": "aprovado",
            "notify_roles": ["designer"],
            "message_template": "Also approved!",
        },
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]

    # 7. Update nonexistent notification rule -> 404
    resp = await authenticated_client.put(
        "/api/admin/rules/notification/nonexistent_status",
        json={"is_active": False},
    )
    assert resp.status_code == 404

    # 8. Get nonexistent system config key -> 404
    resp = await authenticated_client.get(
        "/api/admin/system-config/does_not_exist"
    )
    assert resp.status_code == 404

    # 9. Put brand guideline for nonexistent client -> 404
    resp = await authenticated_client.put(
        f"/api/admin/brands/{fake_uuid}",
        json={"content": "Should fail"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

    # 10. After all these errors, dashboard stats should still be consistent
    resp = await authenticated_client.get("/api/admin/dashboard/stats")
    assert resp.status_code == 200
    stats = resp.json()
    # We successfully created: 1 team member + 1 client + 1 notification rule
    assert stats["total_team_members"] == 1
    assert stats["total_clients"] == 1
    assert stats["total_rules"] == 1  # 1 notification rule
