"""Tests for DbRulesEngine -- database-backed rules engine."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.admin_models import AssignmentRule, Client, NotificationRule, SystemConfig
from src.db.models import Base, TeamMember
from src.engine.db_rules import DbRulesEngine

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
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def seeded_factory(session_factory):
    """Seed the DB with representative data and return the session factory."""
    async with session_factory() as session:
        # Team members
        designer1_id = uuid.uuid4()
        designer2_id = uuid.uuid4()
        reviewer1_id = uuid.uuid4()
        reviewer2_id = uuid.uuid4()
        account_id = uuid.uuid4()

        session.add_all([
            TeamMember(
                id=designer1_id,
                name="Designer A",
                clickup_user_id="89340000",
                role="designer",
                telegram_chat_id=111111,
                active=True,
            ),
            TeamMember(
                id=designer2_id,
                name="Pedro",
                clickup_user_id="95324421",
                role="designer",
                telegram_chat_id=222222,
                active=True,
            ),
            TeamMember(
                id=reviewer1_id,
                name="Luis",
                clickup_user_id="96270997",
                role="strategy_reviewer",
                telegram_chat_id=333333,
                active=True,
            ),
            TeamMember(
                id=reviewer2_id,
                name="Content Lead",
                clickup_user_id="89317548",
                role="content_reviewer",
                telegram_chat_id=444444,
                active=True,
            ),
            TeamMember(
                id=account_id,
                name="Account Manager A",
                clickup_user_id="89347146",
                role="account",
                telegram_chat_id=555555,
                active=True,
            ),
            # Inactive member -- should be excluded
            TeamMember(
                name="Inactive Person",
                clickup_user_id="00000000",
                role="designer",
                telegram_chat_id=999999,
                active=False,
            ),
        ])
        await session.flush()

        # Clients
        session.add_all([
            Client(
                name="client_alpha",
                display_name="ClientAlpha",
                clickup_list_id="list_client_alpha",
                designer_id=designer1_id,
                account_id=account_id,
                is_active=True,
            ),
            Client(
                name="client_delta",
                display_name="ClientDelta",
                clickup_list_id="list_client_delta",
                designer_id=designer2_id,
                is_active=True,
            ),
            Client(
                name="inactive_client",
                display_name="Inactive Client",
                clickup_list_id="list_inactive",
                is_active=False,
            ),
        ])

        # Assignment rules
        session.add_all([
            AssignmentRule(
                service_type="design",
                default_assignee_ids=["89340000"],
                tags=["design"],
            ),
            AssignmentRule(
                service_type="copy",
                default_assignee_ids=["YOUR_CLICKUP_USER_ID"],
                tags=["copy", "redacao"],
            ),
            AssignmentRule(
                service_type="design+copy",
                default_assignee_ids=["89340000", "YOUR_CLICKUP_USER_ID"],
                tags=["design", "copy"],
            ),
        ])

        # Notification rules
        session.add_all([
            NotificationRule(
                status="revisao",
                notify_roles=["strategy_reviewer", "content_reviewer"],
                message_template="precisa de revisao",
                is_active=True,
            ),
            NotificationRule(
                status="alteracao",
                notify_roles=["designer"],
                message_template="voltou para alteracao",
                is_active=True,
            ),
            NotificationRule(
                status="disabled_status",
                notify_roles=["admin"],
                message_template="should not appear",
                is_active=False,
            ),
        ])

        # System config
        session.add_all([
            SystemConfig(
                key="default_list_id",
                value={"value": "list_default_123"},
            ),
            SystemConfig(
                key="initial_status",
                value={"value": "planejamento"},
            ),
        ])

        await session.commit()

    return session_factory


@pytest.fixture
async def engine(seeded_factory):
    """Return a loaded DbRulesEngine."""
    db_engine = DbRulesEngine()
    await db_engine.reload(seeded_factory)
    return db_engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetAssignment:
    @pytest.mark.asyncio
    async def test_basic(self, engine):
        result = engine.get_assignment("design", client_name="unknown")
        assert result.assignees == ["89340000"]
        assert result.tags == ["design"]
        assert result.list_id == "list_default_123"

    @pytest.mark.asyncio
    async def test_with_client_override_designer(self, engine):
        result = engine.get_assignment("design", client_name="client_alpha")
        # ClientAlpha has designer=89340000 (Designer A), which is the same as default
        assert "89340000" in result.assignees
        assert result.list_id == "list_client_alpha"

    @pytest.mark.asyncio
    async def test_with_client_override_different_designer(self, engine):
        result = engine.get_assignment("design", client_name="client_delta")
        # ClientDelta has designer=95324421 (Pedro), default design assignee is 89340000
        assert "95324421" in result.assignees
        assert result.list_id == "list_client_delta"

    @pytest.mark.asyncio
    async def test_unknown_service_type(self, engine):
        result = engine.get_assignment("unknown_service", client_name="any")
        assert result.assignees == []
        assert result.tags == []
        assert result.list_id == "list_default_123"


class TestGetClientByListId:
    @pytest.mark.asyncio
    async def test_found(self, engine):
        assert engine.get_client_by_list_id("list_client_alpha") == "client_alpha"

    @pytest.mark.asyncio
    async def test_not_found(self, engine):
        assert engine.get_client_by_list_id("nonexistent") == "default"


class TestGetTelegramChatId:
    @pytest.mark.asyncio
    async def test_known_user(self, engine):
        assert engine.get_telegram_chat_id("89340000") == 111111

    @pytest.mark.asyncio
    async def test_unknown_user(self, engine):
        assert engine.get_telegram_chat_id("nonexistent") is None


class TestGetClickupUserId:
    @pytest.mark.asyncio
    async def test_known_telegram(self, engine):
        assert engine.get_clickup_user_id(111111) == "89340000"

    @pytest.mark.asyncio
    async def test_unknown_telegram(self, engine):
        assert engine.get_clickup_user_id(999) is None


class TestGetUsersByRole:
    @pytest.mark.asyncio
    async def test_designers(self, engine):
        designers = engine.get_users_by_role("designer")
        assert len(designers) == 2
        names = {d["name"] for d in designers}
        assert "Designer A" in names
        assert "Pedro" in names

    @pytest.mark.asyncio
    async def test_nonexistent_role(self, engine):
        assert engine.get_users_by_role("nonexistent") == []

    @pytest.mark.asyncio
    async def test_inactive_members_excluded(self, engine):
        """Inactive members should not appear in any role query."""
        all_users = engine.get_all_mapped_users()
        assert "00000000" not in all_users


class TestGetNotificationRules:
    @pytest.mark.asyncio
    async def test_existing(self, engine):
        rules = engine.get_notification_rules("revisao")
        assert rules["notify_roles"] == ["strategy_reviewer", "content_reviewer"]
        assert rules["message"] == "precisa de revisao"

    @pytest.mark.asyncio
    async def test_nonexistent(self, engine):
        assert engine.get_notification_rules("nonexistent") == {}

    @pytest.mark.asyncio
    async def test_inactive_excluded(self, engine):
        assert engine.get_notification_rules("disabled_status") == {}


class TestGetReviewers:
    @pytest.mark.asyncio
    async def test_reviewers(self, engine):
        reviewers = engine.get_reviewers()
        assert reviewers.get("strategy") == "96270997"
        assert reviewers.get("content") == "89317548"


class TestGetAllClients:
    @pytest.mark.asyncio
    async def test_returns_active_clients(self, engine):
        clients = engine.get_all_clients()
        assert "client_alpha" in clients
        assert "client_delta" in clients
        assert "inactive_client" not in clients

    @pytest.mark.asyncio
    async def test_returns_copy(self, engine):
        clients = engine.get_all_clients()
        clients["new"] = {}
        assert "new" not in engine.get_all_clients()


class TestGetDefaultListId:
    @pytest.mark.asyncio
    async def test_from_system_config(self, engine):
        assert engine.get_default_list_id() == "list_default_123"

    @pytest.mark.asyncio
    async def test_missing_config(self, session_factory):
        """Empty DB -> returns empty string."""
        empty_engine = DbRulesEngine()
        await empty_engine.reload(session_factory)
        assert empty_engine.get_default_list_id() == ""


class TestGetClientConfig:
    @pytest.mark.asyncio
    async def test_known_client(self, engine):
        config = engine.get_client_config("client_alpha")
        assert config["list_id"] == "list_client_alpha"
        assert config["designer"] == "89340000"
        assert config["account"] == "89347146"

    @pytest.mark.asyncio
    async def test_unknown_client(self, engine):
        assert engine.get_client_config("nonexistent") == {}


class TestGetClientDesigner:
    @pytest.mark.asyncio
    async def test_known(self, engine):
        assert engine.get_client_designer("client_alpha") == "89340000"

    @pytest.mark.asyncio
    async def test_unknown(self, engine):
        assert engine.get_client_designer("nonexistent") is None


class TestGetAllMappedUsers:
    @pytest.mark.asyncio
    async def test_returns_all_active(self, engine):
        users = engine.get_all_mapped_users()
        assert len(users) == 5
        assert "89340000" in users
        assert "00000000" not in users  # inactive excluded


class TestReload:
    @pytest.mark.asyncio
    async def test_reload_updates_data(self, seeded_factory):
        """Modify data, reload, verify new data is picked up."""
        db_engine = DbRulesEngine()
        await db_engine.reload(seeded_factory)

        # Initially: list_client_alpha
        assert db_engine.get_client_config("client_alpha")["list_id"] == "list_client_alpha"

        # Modify the client's list_id in DB
        async with seeded_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Client).where(Client.name == "client_alpha")
            )
            client = result.scalar_one()
            client.clickup_list_id = "list_client_alpha_v2"
            await session.commit()

        # Before reload: still old
        assert db_engine.get_client_config("client_alpha")["list_id"] == "list_client_alpha"

        # After reload: new
        await db_engine.reload(seeded_factory)
        assert db_engine.get_client_config("client_alpha")["list_id"] == "list_client_alpha_v2"


class TestSystemConfigFormats:
    @pytest.mark.asyncio
    async def test_bare_string_value(self, session_factory):
        """system_config value stored as plain string (not dict)."""
        async with session_factory() as session:
            session.add(
                SystemConfig(key="default_list_id", value="bare_list_id")
            )
            await session.commit()

        eng = DbRulesEngine()
        await eng.reload(session_factory)
        assert eng.get_default_list_id() == "bare_list_id"

    @pytest.mark.asyncio
    async def test_dict_with_value_key(self, session_factory):
        """system_config value stored as {"value": "xxx"}."""
        async with session_factory() as session:
            session.add(
                SystemConfig(key="default_list_id", value={"value": "dict_list_id"})
            )
            await session.commit()

        eng = DbRulesEngine()
        await eng.reload(session_factory)
        assert eng.get_default_list_id() == "dict_list_id"
