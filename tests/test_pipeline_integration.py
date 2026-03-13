from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from src.agents.schemas import BriefingAnalysis, PostTask
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
    "client_overrides": {},
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
        month="fevereiro",
        year="2026",
        project_summary="Campanha de verao com 2 posts para Instagram",
        posts=[
            PostTask(title="Post 1 - Verao", description="Arte promo", service_type="design+copy"),
            PostTask(title="Post 2 - Verao", description="Copy promo", service_type="copy"),
        ],
        urgency="urgent",
        observations="",
    )


@pytest.mark.asyncio
async def test_full_pipeline(rules_engine, mock_analysis):
    # Mock the agent
    mock_response = MagicMock()
    mock_response.content = mock_analysis
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    # Mock the ClickUp client
    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_clickup.create_task = AsyncMock(
        side_effect=[
            {"id": "parent_123", "name": "Instagram - Loja Bella - Fevereiro 2026"},
            {"id": "sub_1", "name": "Post 1 - Verao"},
            {"id": "sub_2", "name": "Post 2 - Verao"},
        ]
    )

    # No schedule_agent -> creates parent + subtasks
    handler = BriefingHandler(
        agent=mock_agent,
        clickup_client=mock_clickup,
        rules_engine=rules_engine,
        allowed_user_ids=[999],
    )

    # Mock Telegram update
    mock_update = MagicMock()
    mock_update.effective_user.id = 999
    mock_update.message.text = "Briefing do cliente Loja Bella: 2 posts Instagram verao. Urgente."
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {}
    await handler.handle_message(mock_update, mock_context)

    # Verify ClickUp was called correctly (no schedule_agent -> parent + subtasks)
    assert mock_clickup.create_task.call_count == 3  # 1 parent + 2 subtasks

    # Verify response was sent
    assert mock_update.message.reply_text.call_count == 2  # "Analisando..." + result

    # Verify the final response contains expected content
    final_response = mock_update.message.reply_text.call_args_list[1][0][0]
    assert "Loja Bella" in final_response
    assert "Post 1 - Verao" in final_response
    assert "Post 2 - Verao" in final_response


@pytest.mark.asyncio
async def test_unauthorized_user_is_ignored(rules_engine):
    handler = BriefingHandler(
        agent=MagicMock(),
        clickup_client=MagicMock(),
        rules_engine=rules_engine,
        allowed_user_ids=[999],
    )

    mock_update = MagicMock()
    mock_update.effective_user.id = 000  # Not authorized
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {}
    await handler.handle_message(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    msg = mock_update.message.reply_text.call_args[0][0]
    assert "permissao" in msg.lower()


@pytest.mark.asyncio
async def test_short_message_rejected(rules_engine):
    handler = BriefingHandler(
        agent=MagicMock(),
        clickup_client=MagicMock(),
        rules_engine=rules_engine,
        allowed_user_ids=[999],
    )

    mock_update = MagicMock()
    mock_update.effective_user.id = 999
    mock_update.message.text = "Hi"
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {}
    await handler.handle_message(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    assert "10 caracteres" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_error_handling(rules_engine):
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(side_effect=Exception("LLM timeout"))

    handler = BriefingHandler(
        agent=mock_agent,
        clickup_client=MagicMock(),
        rules_engine=rules_engine,
        allowed_user_ids=[999],
    )

    mock_update = MagicMock()
    mock_update.effective_user.id = 999
    mock_update.message.text = "Briefing do cliente Teste: preciso de um post para Instagram."
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {}
    await handler.handle_message(mock_update, mock_context)

    # Should have sent "Analisando..." then error message
    assert mock_update.message.reply_text.call_count == 2
    error_response = mock_update.message.reply_text.call_args_list[1][0][0]
    assert "Erro" in error_response
