"""Load agent configurations and brand guidelines from the database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker


async def load_agent_config(
    session_factory: async_sessionmaker, agent_name: str
) -> dict | None:
    """Load agent config from DB. Returns {model_id, instructions} or None if not found."""
    from src.db.admin_models import AgentConfig

    async with session_factory() as session:
        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.agent_name == agent_name,
                AgentConfig.is_active.is_(True),
            )
        )
        config = result.scalar_one_or_none()
        if config:
            return {
                "model_id": config.model_id,
                "instructions": config.instructions,
            }
        return None


async def load_brand_guidelines_from_db(
    session_factory: async_sessionmaker, client_name: str
) -> str | None:
    """Load brand guidelines from DB. Returns content or None if not found."""
    from src.db.admin_models import BrandGuideline, Client

    async with session_factory() as session:
        # Try client-specific first
        client_result = await session.execute(
            select(Client).where(Client.name == client_name, Client.is_active.is_(True))
        )
        client = client_result.scalar_one_or_none()
        if client:
            guideline_result = await session.execute(
                select(BrandGuideline).where(BrandGuideline.client_id == client.id)
            )
            guideline = guideline_result.scalar_one_or_none()
            if guideline:
                return guideline.content

        # Fall back to default (client_id IS NULL)
        default_result = await session.execute(
            select(BrandGuideline).where(BrandGuideline.client_id.is_(None))
        )
        default = default_result.scalar_one_or_none()
        return default.content if default else None
