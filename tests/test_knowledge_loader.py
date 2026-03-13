from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.knowledge_loader import load_agent_knowledge


@pytest.mark.asyncio
async def test_load_agent_knowledge_filters_by_access():
    doc1 = MagicMock()
    doc1.title = "Manual"
    doc1.category = "marca"
    doc1.content = "Content 1"
    doc1.agent_access = ["content_reviewer"]
    doc1.is_active = True

    doc2 = MagicMock()
    doc2.title = "Other"
    doc2.category = "geral"
    doc2.content = "Content 2"
    doc2.agent_access = ["briefing_analyzer"]
    doc2.is_active = True

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [doc1, doc2]
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute.return_value = mock_result

    result = await load_agent_knowledge(session, "content_reviewer")
    assert "Manual" in result
    assert "Content 1" in result
    assert "Other" not in result


@pytest.mark.asyncio
async def test_load_agent_knowledge_empty():
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute.return_value = mock_result

    result = await load_agent_knowledge(session, "content_reviewer")
    assert result == ""


@pytest.mark.asyncio
async def test_load_agent_knowledge_formats_sections():
    doc = MagicMock()
    doc.title = "Brand Guide"
    doc.category = "marca"
    doc.content = "Be professional"
    doc.agent_access = ["agent1"]
    doc.is_active = True

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [doc]
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute.return_value = mock_result

    result = await load_agent_knowledge(session, "agent1")
    assert "## Brand Guide [marca]" in result
    assert "Be professional" in result
