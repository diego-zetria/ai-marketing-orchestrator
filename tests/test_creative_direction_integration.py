"""Integration tests for Creative Director in the briefing flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.schemas import (
    BriefingAnalysis,
    ContentTheme,
    CreativeDirection,
    PostSchedule,
    ScheduledPost,
)
from src.bot.handlers import BriefingHandler
from src.bot.keyboards import creative_direction_keyboard


def test_creative_direction_keyboard():
    kb = creative_direction_keyboard()
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].callback_data == "creative_use"
    assert buttons[1].callback_data == "creative_skip"


def _make_handler(creative_director_agent=None):
    """Create a BriefingHandler with mocked dependencies."""
    mock_agent = MagicMock()
    mock_clickup = MagicMock(spec=["create_task", "get_filtered_team_tasks"])
    mock_clickup.create_task = AsyncMock(return_value={"id": "parent123"})
    mock_clickup.get_filtered_team_tasks = AsyncMock(return_value=[])

    mock_rules = MagicMock()
    mock_rules.get_assignment.return_value = MagicMock(
        assignees=["123"], tags=["design"], list_id="list123",
    )
    mock_rules.get_client_config.return_value = {"list_id": "list123"}
    mock_rules.get_client_designer.return_value = "123"

    return BriefingHandler(
        agent=mock_agent,
        clickup_client=mock_clickup,
        rules_engine=mock_rules,
        allowed_user_ids=[111],
        schedule_agent=MagicMock(),
        creative_director_agent=creative_director_agent,
    )


@pytest.mark.asyncio
async def test_briefing_flow_shows_creative_direction_when_agent_available():
    mock_cd_agent = MagicMock()
    handler = _make_handler(creative_director_agent=mock_cd_agent)

    mock_analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="ClientAlpha",
        social_network="instagram",
        month="marco",
        year="2026",
        project_summary="Campanha marco",
        posts=[],
    )

    mock_direction = CreativeDirection(
        client_name="ClientAlpha",
        period="Marco 2026",
        resumo_estrategico="Foco em conteudo premium.",
        themes=[
            ContentTheme(
                name="Premium", description="d", pillar="inspiracional",
                subtopics=["s"], recommended_formats=["carrossel"],
                platforms=["instagram"], rationale="r",
            ),
        ],
        format_mix={"carrossel": 4},
        tone_guidance="Tom premium",
        avoid=[],
    )

    update = MagicMock()
    update.effective_user.id = 111
    update.message.text = "Briefing ClientAlpha marco 2026 Instagram 5 posts"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    with (
        patch(
            "src.bot.handlers.analyze_briefing",
            new_callable=AsyncMock, return_value=mock_analysis,
        ),
        patch.object(
            handler, "_generate_creative_direction",
            new_callable=AsyncMock, return_value=mock_direction,
        ),
    ):
        await handler._process_briefing(
            update, context, "Briefing ClientAlpha marco 2026",
        )

    assert "creative_direction" in context.user_data
    reply_calls = update.message.reply_text.call_args_list
    creative_call_found = any(
        "creative_use" in str(call) or "creative_skip" in str(call)
        for call in reply_calls
    )
    assert creative_call_found


@pytest.mark.asyncio
async def test_briefing_flow_skips_creative_when_no_agent():
    handler = _make_handler(creative_director_agent=None)

    mock_analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="ClientAlpha",
        social_network="instagram",
        month="marco",
        year="2026",
        project_summary="Campanha",
        posts=[],
    )

    update = MagicMock()
    update.effective_user.id = 111
    update.message.text = "Briefing ClientAlpha marco"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    with patch(
        "src.bot.handlers.analyze_briefing",
        new_callable=AsyncMock, return_value=mock_analysis,
    ):
        await handler._process_briefing(
            update, context, "Briefing ClientAlpha marco",
        )

    assert "creative_direction" not in context.user_data


@pytest.mark.asyncio
async def test_creative_use_callback_enriches_briefing():
    handler = _make_handler(creative_director_agent=MagicMock())

    mock_direction = CreativeDirection(
        client_name="ClientAlpha",
        period="Marco 2026",
        resumo_estrategico="Foco premium.",
        themes=[
            ContentTheme(
                name="T", description="d", pillar="educativo",
                subtopics=["s"], recommended_formats=["post"],
                platforms=["instagram"], rationale="r",
            ),
        ],
        format_mix={"post": 3},
        tone_guidance="Premium",
        avoid=[],
    )

    mock_schedule = PostSchedule(
        posts=[ScheduledPost(date="03/03", post_type="POST", title="Test", platform="instagram")],
        month="marco",
        year="2026",
        platform="instagram",
        observations="",
    )

    query = MagicMock()
    query.data = "creative_use"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    context = MagicMock()
    context.user_data = {
        "creative_direction": mock_direction,
        "analysis": BriefingAnalysis(
            is_valid_briefing=True,
            client_name="ClientAlpha",
            social_network="instagram",
            month="marco",
            year="2026",
            project_summary="Campanha",
            posts=[],
        ),
        "briefing_text": "Briefing ClientAlpha",
    }

    update = MagicMock()
    update.callback_query = query

    with patch(
        "src.bot.handlers.generate_schedule",
        new_callable=AsyncMock, return_value=mock_schedule,
    ):
        await handler.handle_creative_callback(update, context)

    # The briefing_text should now contain creative direction
    assert "DIRECAO CRIATIVA" in context.user_data["briefing_text"]


@pytest.mark.asyncio
async def test_creative_skip_callback_shows_schedule():
    handler = _make_handler(creative_director_agent=MagicMock())

    mock_schedule = PostSchedule(
        posts=[ScheduledPost(date="03/03", post_type="POST", title="Test", platform="instagram")],
        month="marco",
        year="2026",
        platform="instagram",
        observations="",
    )

    query = MagicMock()
    query.data = "creative_skip"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    context = MagicMock()
    context.user_data = {
        "analysis": BriefingAnalysis(
            is_valid_briefing=True,
            client_name="ClientAlpha",
            social_network="instagram",
            month="marco",
            year="2026",
            project_summary="Campanha",
            posts=[],
        ),
        "briefing_text": "Briefing ClientAlpha",
    }

    update = MagicMock()
    update.callback_query = query

    with patch(
        "src.bot.handlers.generate_schedule",
        new_callable=AsyncMock, return_value=mock_schedule,
    ):
        await handler.handle_creative_callback(update, context)

    query.edit_message_text.assert_called()
