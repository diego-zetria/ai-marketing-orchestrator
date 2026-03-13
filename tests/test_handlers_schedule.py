from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from src.agents.schemas import (
    BriefingAnalysis,
    PostSchedule,
    PostTask,
    ScheduledPost,
)
from src.bot.handlers import BriefingHandler
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

RULES = {
    "assignment_rules": {
        "design": {"default_assignees": ["101"], "tags": ["design"]},
        "copy": {"default_assignees": ["102"], "tags": ["copy"]},
        "design+copy": {"default_assignees": ["101", "102"], "tags": ["design", "copy"]},
    },
    "reviewers": {"strategy": "201", "content": "202"},
    "client_overrides": {
        "loja bella": {
            "designer": "301",
            "list_id": "list_bella",
        },
    },
    "default_config": {"list_id": "list_social", "initial_status": "planejamento"},
}


@pytest.fixture
def rules_engine(tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(yaml.dump(RULES))
    return RulesEngine(rules_file)


@pytest.fixture
def mock_analysis():
    return BriefingAnalysis(
        is_valid_briefing=True,
        client_name="Loja Bella",
        social_network="instagram",
        month="marco",
        year="2026",
        project_summary="Campanha de marco",
        posts=[
            PostTask(title="Post 1", description="Desc", service_type="design"),
        ],
        urgency="normal",
        observations="",
    )


@pytest.fixture
def mock_schedule():
    return PostSchedule(
        posts=[
            ScheduledPost(
                date="03/03", post_type="POST",
                title="Inauguracao", platform="instagram",
            ),
            ScheduledPost(
                date="06/03", post_type="CARROSSEL",
                title="5 motivos", platform="instagram",
            ),
        ],
        month="marco",
        year="2026",
        platform="instagram",
        observations="Cronograma otimizado.",
    )


def _make_handler(rules_engine, agent=None, clickup=None, schedule_agent=None):
    return BriefingHandler(
        agent=agent or MagicMock(),
        clickup_client=clickup or MagicMock(),
        rules_engine=rules_engine,
        allowed_user_ids=[999],
        schedule_agent=schedule_agent,
    )


def _make_callback_query(data, user_id=999):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.reply_text = AsyncMock()

    update = MagicMock()
    update.effective_user.id = user_id
    update.callback_query = query

    return update, query


@pytest.mark.asyncio
async def test_process_briefing_sends_schedule_prompt(rules_engine, mock_analysis):
    """After creating ClickUp tasks, bot should offer schedule generation."""
    mock_response = MagicMock()
    mock_response.content = mock_analysis
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_clickup.create_task = AsyncMock(
        return_value={"id": "parent_123", "name": "Instagram - Loja Bella - Marco 2026"},
    )

    handler = _make_handler(
        rules_engine, agent=mock_agent,
        clickup=mock_clickup, schedule_agent=MagicMock(),
    )
    update = MagicMock()
    update.effective_user.id = 999
    update.message.text = "Briefing Loja Bella marco 2026"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await handler.handle_message(update, context)

    # With schedule_agent: only parent created (subtasks come from cronograma)
    assert mock_clickup.create_task.call_count == 1

    # Should have: "Analisando..." + success response + schedule prompt
    assert update.message.reply_text.call_count == 3
    last_call = update.message.reply_text.call_args_list[2]
    # Check that the last message mentions cronograma
    msg = last_call[0][0] if last_call[0] else last_call[1].get("text", "")
    assert "cronograma" in msg.lower()


@pytest.mark.asyncio
async def test_handle_schedule_generate(rules_engine, mock_schedule):
    """When user clicks 'Gerar Cronograma', bot generates and shows schedule."""
    mock_sched_agent = MagicMock()
    mock_sched_response = MagicMock()
    mock_sched_response.content = mock_schedule
    mock_sched_agent.arun = AsyncMock(return_value=mock_sched_response)

    handler = _make_handler(rules_engine, schedule_agent=mock_sched_agent)
    update, query = _make_callback_query("schedule_generate")

    context = MagicMock()
    context.user_data = {
        "briefing_text": "Briefing Loja Bella marco",
        "analysis": MagicMock(
            client_name="Loja Bella",
            social_network="instagram",
            month="marco",
            year="2026",
        ),
        "parent_task_id": "parent_123",
    }

    await handler.handle_schedule_callback(update, context)

    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once()
    call_args = query.edit_message_text.call_args
    msg = call_args[1].get(
        "text",
        call_args[0][0] if call_args[0] else "",
    )
    assert "03/03" in msg
    assert "POST" in msg


@pytest.mark.asyncio
async def test_handle_schedule_skip(rules_engine):
    """When user clicks 'Pular', bot acknowledges and ends flow."""
    handler = _make_handler(rules_engine)
    update, query = _make_callback_query("schedule_skip")

    context = MagicMock()
    context.user_data = {}

    await handler.handle_schedule_callback(update, context)

    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once()
    msg = query.edit_message_text.call_args[0][0]
    assert "cronograma" in msg.lower() or "pular" in msg.lower() or "ok" in msg.lower()


@pytest.mark.asyncio
async def test_handle_schedule_approve_creates_subtasks(rules_engine, mock_schedule):
    """When user clicks 'Aprovar', bot creates subtasks in ClickUp."""
    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_clickup.create_task = AsyncMock(
        side_effect=[
            {"id": "sched_1", "name": "03/03 - POST Inauguracao"},
            {"id": "sched_2", "name": "06/03 - CARROSSEL 5 motivos"},
        ]
    )

    handler = _make_handler(rules_engine, clickup=mock_clickup)
    update, query = _make_callback_query("schedule_approve")

    context = MagicMock()
    context.user_data = {
        "schedule": mock_schedule,
        "analysis": MagicMock(client_name="loja bella", year="2026"),
        "parent_task_id": "parent_123",
    }

    await handler.handle_schedule_callback(update, context)

    assert mock_clickup.create_task.call_count == 2
    query.edit_message_text.assert_called_once()
    msg = query.edit_message_text.call_args[0][0]
    assert "2" in msg


@pytest.mark.asyncio
async def test_handle_schedule_edit_enters_edit_mode(rules_engine):
    """When user clicks 'Editar', bot asks for edit instructions."""
    handler = _make_handler(rules_engine)
    update, query = _make_callback_query("schedule_edit")

    context = MagicMock()
    context.user_data = {"schedule": MagicMock()}

    await handler.handle_schedule_callback(update, context)

    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once()
    msg = query.edit_message_text.call_args[0][0]
    assert "editar" in msg.lower() or "ajust" in msg.lower() or "envie" in msg.lower()
    assert context.user_data.get("awaiting_edit") is True


@pytest.mark.asyncio
async def test_handle_schedule_edit_text(rules_engine, mock_schedule):
    """After entering edit mode, user sends text and AI adjusts schedule."""
    mock_sched_agent = MagicMock()
    adjusted = PostSchedule(
        posts=[
            ScheduledPost(
                date="03/03", post_type="REELS",
                title="Tour pela loja", platform="instagram",
            ),
            ScheduledPost(
                date="06/03", post_type="CARROSSEL",
                title="5 motivos", platform="instagram",
            ),
        ],
        month="marco",
        year="2026",
        platform="instagram",
        observations="Ajustado: trocado post 1 por reels.",
    )
    mock_response = MagicMock()
    mock_response.content = adjusted
    mock_sched_agent.arun = AsyncMock(return_value=mock_response)

    handler = _make_handler(rules_engine, schedule_agent=mock_sched_agent)

    update = MagicMock()
    update.effective_user.id = 999
    update.message.text = "troca o post 1 por um reels"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {
        "awaiting_edit": True,
        "schedule": mock_schedule,
        "briefing_text": "Briefing original",
        "analysis": MagicMock(
            client_name="Loja Bella",
            social_network="instagram",
            month="marco",
            year="2026",
        ),
    }

    await handler.handle_schedule_edit(update, context)

    assert context.user_data["awaiting_edit"] is False
    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "REELS" in msg


# === Task 9: _parse_due_date unit tests ===


def test_parse_due_date_valid():
    result = BriefingHandler._parse_due_date("03/03", "2026")
    assert result is not None
    assert isinstance(result, int)
    assert result > 0


def test_parse_due_date_end_of_month():
    result = BriefingHandler._parse_due_date("28/02", "2026")
    assert result is not None


def test_parse_due_date_invalid_format():
    result = BriefingHandler._parse_due_date("invalid", "2026")
    assert result is None


def test_parse_due_date_invalid_date():
    result = BriefingHandler._parse_due_date("31/02", "2026")
    assert result is None


def test_parse_due_date_first_day():
    result = BriefingHandler._parse_due_date("01/01", "2026")
    assert result is not None
    expected_approx = 1767261600000  # Jan 1 2026 12:00 UTC approximate
    assert abs(result - expected_approx) < 86400000  # within 1 day


# === Task 11: End-to-end integration test ===


@pytest.mark.asyncio
async def test_full_schedule_flow_end_to_end(rules_engine, mock_analysis, mock_schedule):
    """Integration test: briefing -> card -> schedule prompt -> generate -> approve -> subtasks."""
    mock_response = MagicMock()
    mock_response.content = mock_analysis
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    mock_sched_response = MagicMock()
    mock_sched_response.content = mock_schedule
    mock_sched_agent = MagicMock()
    mock_sched_agent.arun = AsyncMock(return_value=mock_sched_response)

    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_clickup.create_task = AsyncMock(
        side_effect=[
            # Phase 1: briefing -> parent only (subtasks skipped when schedule_agent exists)
            {"id": "parent_123", "name": "Instagram - Loja Bella - Marco 2026"},
            # Phase 2: schedule -> subtasks
            {"id": "sched_1", "name": "03/03 - POST Inauguracao"},
            {"id": "sched_2", "name": "06/03 - CARROSSEL 5 motivos"},
        ]
    )

    handler = _make_handler(
        rules_engine,
        agent=mock_agent,
        clickup=mock_clickup,
        schedule_agent=mock_sched_agent,
    )

    # Phase 1: Send briefing
    update = MagicMock()
    update.effective_user.id = 999
    update.message.text = "Briefing Loja Bella marco 2026 - 1 post Instagram"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await handler.handle_message(update, context)

    # With schedule_agent: only parent created (subtasks come from cronograma)
    assert mock_clickup.create_task.call_count == 1
    assert "analysis" in context.user_data
    assert "parent_task_id" in context.user_data

    # Phase 2: Click "Gerar Cronograma"
    gen_update, gen_query = _make_callback_query("schedule_generate")
    await handler.handle_schedule_callback(gen_update, context)

    assert "schedule" in context.user_data
    assert gen_query.edit_message_text.called

    # Phase 3: Click "Aprovar"
    approve_update, approve_query = _make_callback_query("schedule_approve")
    await handler.handle_schedule_callback(approve_update, context)

    # Should have created 2 schedule subtasks (total 3 ClickUp calls: 1 parent + 2 schedule)
    assert mock_clickup.create_task.call_count == 3
    msg = approve_query.edit_message_text.call_args[0][0]
    assert "2" in msg
