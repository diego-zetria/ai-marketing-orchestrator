"""Load knowledge documents for agent context injection."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.admin_models import KnowledgeDocument


async def load_agent_knowledge(session: AsyncSession, agent_name: str) -> str:
    """Load all active knowledge documents accessible by the given agent.

    Returns concatenated text ready for prompt injection.
    """
    result = await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.is_active.is_(True)
        )
    )
    docs = result.scalars().all()

    # Filter by agent_access (JSONB array contains agent_name)
    relevant = [d for d in docs if agent_name in (d.agent_access or [])]

    if not relevant:
        return ""

    sections = []
    for doc in relevant:
        sections.append(f"## {doc.title} [{doc.category}]\n\n{doc.content}")

    return "\n\n---\n\n".join(sections)
