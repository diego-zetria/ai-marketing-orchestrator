from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.briefing_analyzer import analyze_briefing, create_briefing_agent
from src.agents.schemas import BriefingAnalysis, PostTask


def test_create_agent_returns_agent():
    agent = create_briefing_agent(
        api_key="test-key",
        model_id="anthropic/claude-sonnet-4",
    )
    assert agent is not None
    assert agent.name == "briefing_analyzer"


@pytest.mark.asyncio
async def test_analyze_briefing_returns_structured_output():
    mock_analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="Loja Bella",
        social_network="instagram",
        month="fevereiro",
        year="2026",
        project_summary="Campanha de verao",
        posts=[
            PostTask(
                title="Post 1 - Verao",
                description="Arte promocional",
                service_type="design+copy",
            ),
        ],
        urgency="urgent",
        observations="",
    )

    mock_response = MagicMock()
    mock_response.content = mock_analysis

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await analyze_briefing(
        agent=mock_agent,
        briefing_text="Briefing do cliente Loja Bella: 1 post instagram verao. Urgente.",
    )

    assert result.client_name == "Loja Bella"
    assert result.urgency == "urgent"
    assert len(result.posts) == 1
    assert result.is_valid_briefing is True


@pytest.mark.asyncio
async def test_analyze_briefing_invalid_returns_rejection():
    mock_analysis = BriefingAnalysis(
        is_valid_briefing=False,
        rejection_message="Essa mensagem nao parece ser um briefing de marketing.",
    )

    mock_response = MagicMock()
    mock_response.content = mock_analysis

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await analyze_briefing(agent=mock_agent, briefing_text="oi, tudo bem?")

    assert result.is_valid_briefing is False
    assert "briefing" in result.rejection_message.lower()
    assert result.client_name == ""
    assert result.posts == []


@pytest.mark.asyncio
async def test_analyze_briefing_parses_json_string():
    """When model returns JSON string instead of BriefingAnalysis, parse it."""
    json_str = (
        '{"is_valid_briefing": true, "client_name": "ClientAlpha", '
        '"social_network": "instagram", "month": "marco", "year": "2026", '
        '"project_summary": "Post skincare", '
        '"posts": [{"title": "Post 1", "description": "Desc", "service_type": "design"}], '
        '"urgency": "normal", "observations": ""}'
    )

    mock_response = MagicMock()
    mock_response.content = json_str

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await analyze_briefing(agent=mock_agent, briefing_text="briefing test")

    assert isinstance(result, BriefingAnalysis)
    assert result.client_name == "ClientAlpha"
    assert result.is_valid_briefing is True


@pytest.mark.asyncio
async def test_analyze_briefing_retries_on_invalid():
    """After retries with invalid responses, raises ValueError."""
    mock_response = MagicMock()
    mock_response.content = 12345  # Not a string, not a BriefingAnalysis

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    with pytest.raises(ValueError, match="resposta invalida"):
        await analyze_briefing(agent=mock_agent, briefing_text="test", max_retries=1)
