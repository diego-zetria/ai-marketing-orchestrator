"""Tests for agent config_loader -- database-backed agent config and brand guidelines."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.agents.config_loader import load_agent_config, load_brand_guidelines_from_db
from src.db.admin_models import AgentConfig, BrandGuideline, Client
from src.db.models import Base

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


# ---------------------------------------------------------------------------
# Tests: load_agent_config
# ---------------------------------------------------------------------------


class TestLoadAgentConfig:
    @pytest.mark.asyncio
    async def test_found(self, session_factory):
        """Active agent config is returned with model_id and instructions."""
        async with session_factory() as session:
            session.add(
                AgentConfig(
                    agent_name="briefing_analyzer",
                    model_id="openai/gpt-4o",
                    instructions=["Instrucao 1", "Instrucao 2"],
                    is_active=True,
                )
            )
            await session.commit()

        result = await load_agent_config(session_factory, "briefing_analyzer")
        assert result is not None
        assert result["model_id"] == "openai/gpt-4o"
        assert result["instructions"] == ["Instrucao 1", "Instrucao 2"]

    @pytest.mark.asyncio
    async def test_not_found(self, session_factory):
        """Returns None when agent config does not exist."""
        result = await load_agent_config(session_factory, "nonexistent_agent")
        assert result is None

    @pytest.mark.asyncio
    async def test_inactive(self, session_factory):
        """Inactive agent config returns None."""
        async with session_factory() as session:
            session.add(
                AgentConfig(
                    agent_name="disabled_agent",
                    model_id="openai/gpt-4o",
                    instructions=["Instrucao"],
                    is_active=False,
                )
            )
            await session.commit()

        result = await load_agent_config(session_factory, "disabled_agent")
        assert result is None


# ---------------------------------------------------------------------------
# Tests: load_brand_guidelines_from_db
# ---------------------------------------------------------------------------


class TestLoadBrandGuidelinesFromDb:
    @pytest.mark.asyncio
    async def test_client_specific(self, session_factory):
        """Returns client-specific brand guidelines when available."""
        client_id = uuid.uuid4()
        async with session_factory() as session:
            session.add(
                Client(
                    id=client_id,
                    name="client_alpha",
                    display_name="ClientAlpha",
                    is_active=True,
                )
            )
            await session.flush()
            session.add(
                BrandGuideline(
                    client_id=client_id,
                    content="# ClientAlpha Guidelines\n- Tom profissional",
                )
            )
            await session.commit()

        result = await load_brand_guidelines_from_db(session_factory, "client_alpha")
        assert result is not None
        assert "ClientAlpha Guidelines" in result
        assert "Tom profissional" in result

    @pytest.mark.asyncio
    async def test_fallback_default(self, session_factory):
        """Falls back to default (client_id=NULL) when no client-specific guideline."""
        async with session_factory() as session:
            session.add(
                BrandGuideline(
                    client_id=None,
                    content="# Default Guidelines\n- Tom padrao",
                )
            )
            await session.commit()

        result = await load_brand_guidelines_from_db(session_factory, "nonexistent_client")
        assert result is not None
        assert "Default Guidelines" in result
        assert "Tom padrao" in result

    @pytest.mark.asyncio
    async def test_not_found(self, session_factory):
        """Returns None when no guidelines exist at all."""
        result = await load_brand_guidelines_from_db(session_factory, "any_client")
        assert result is None

    @pytest.mark.asyncio
    async def test_client_specific_over_default(self, session_factory):
        """Client-specific guidelines take priority over default."""
        client_id = uuid.uuid4()
        async with session_factory() as session:
            session.add(
                Client(
                    id=client_id,
                    name="client_delta",
                    display_name="ClientDelta",
                    is_active=True,
                )
            )
            await session.flush()
            session.add(
                BrandGuideline(
                    client_id=None,
                    content="# Default Guidelines",
                )
            )
            session.add(
                BrandGuideline(
                    client_id=client_id,
                    content="# ClientDelta Guidelines",
                )
            )
            await session.commit()

        result = await load_brand_guidelines_from_db(session_factory, "client_delta")
        assert result is not None
        assert "ClientDelta Guidelines" in result
        assert "Default" not in result

    @pytest.mark.asyncio
    async def test_inactive_client_falls_back_to_default(self, session_factory):
        """Inactive client falls back to default guidelines."""
        client_id = uuid.uuid4()
        async with session_factory() as session:
            session.add(
                Client(
                    id=client_id,
                    name="inactive_co",
                    display_name="Inactive Co",
                    is_active=False,
                )
            )
            await session.flush()
            session.add(
                BrandGuideline(
                    client_id=client_id,
                    content="# Inactive Client Guidelines",
                )
            )
            session.add(
                BrandGuideline(
                    client_id=None,
                    content="# Default Guidelines",
                )
            )
            await session.commit()

        result = await load_brand_guidelines_from_db(session_factory, "inactive_co")
        assert result is not None
        assert "Default Guidelines" in result
