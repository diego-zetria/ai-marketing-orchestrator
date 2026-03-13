from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.schemas import DailySummary
from src.agents.summary_generator import create_summary_agent, generate_summary


def test_create_agent_returns_agent():
    agent = create_summary_agent(
        api_key="test-key",
        model_id="anthropic/claude-sonnet-4",
    )
    assert agent is not None
    assert agent.name == "summary_generator"


@pytest.mark.asyncio
async def test_generate_summary_returns_structured_output():
    mock_summary = DailySummary(
        resumo="Dia produtivo com 5 tasks ativas.",
        total_ativas=5,
        total_concluidas=2,
        total_atrasadas=1,
        gargalos=["Post ClientDelta parado em revisao ha 3 dias"],
        deadlines_proximos=["Instagram ClientGamma - prazo 23/02"],
    )

    mock_response = MagicMock()
    mock_response.content = mock_summary

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await generate_summary(
        agent=mock_agent,
        tasks_data="5 tasks ativas, 2 concluidas, 1 atrasada...",
    )

    assert result.total_ativas == 5
    assert result.total_concluidas == 2
    assert result.total_atrasadas == 1
    assert len(result.gargalos) == 1
    assert len(result.deadlines_proximos) == 1


@pytest.mark.asyncio
async def test_generate_summary_raises_on_invalid_response():
    mock_response = MagicMock()
    mock_response.content = "plain text instead of DailySummary"

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    with pytest.raises(ValueError, match="DailySummary"):
        await generate_summary(agent=mock_agent, tasks_data="some data")
