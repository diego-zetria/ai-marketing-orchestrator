from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.schedule_generator import generate_schedule
from src.agents.schemas import PostSchedule, ScheduledPost


@pytest.mark.asyncio
async def test_generate_schedule_returns_post_schedule():
    mock_schedule = PostSchedule(
        posts=[
            ScheduledPost(date="03/03", post_type="POST", title="Post 1", platform="instagram"),
            ScheduledPost(
                date="06/03", post_type="CARROSSEL",
                title="Post 2", platform="instagram",
            ),
        ],
        month="marco",
        year="2026",
        platform="instagram",
        observations="Cronograma otimizado.",
    )
    mock_response = MagicMock()
    mock_response.content = mock_schedule

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await generate_schedule(
        agent=mock_agent,
        briefing_text="Briefing: 2 posts Instagram marco.",
        client_name="Loja Bella",
        social_network="instagram",
        month="marco",
        year="2026",
    )

    assert isinstance(result, PostSchedule)
    assert len(result.posts) == 2
    assert result.posts[0].task_name == "03/03 - POST Post 1"
    mock_agent.arun.assert_called_once()


@pytest.mark.asyncio
async def test_generate_schedule_passes_context_to_agent():
    mock_schedule = PostSchedule(
        posts=[
            ScheduledPost(date="01/04", post_type="STORY", title="Story 1", platform="tiktok"),
        ],
        month="abril",
        year="2026",
        platform="tiktok",
        observations="",
    )
    mock_response = MagicMock()
    mock_response.content = mock_schedule

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    await generate_schedule(
        agent=mock_agent,
        briefing_text="Briefing TikTok abril",
        client_name="Loja X",
        social_network="tiktok",
        month="abril",
        year="2026",
    )

    call_args = mock_agent.arun.call_args[0][0]
    assert "Loja X" in call_args
    assert "tiktok" in call_args
    assert "abril" in call_args
    assert "2026" in call_args
    assert "Briefing TikTok abril" in call_args
