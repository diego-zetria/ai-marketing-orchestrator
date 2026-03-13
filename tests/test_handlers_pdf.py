from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.agents.schemas import BriefingAnalysis, PostTask
from src.bot.handlers import BriefingHandler
from src.bot.pdf_extractor import MAX_FILE_SIZE
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
        project_summary="Campanha de verao com 1 post para Instagram",
        posts=[
            PostTask(title="Post 1 - Verao", description="Arte promo", service_type="design"),
        ],
        urgency="normal",
        observations="",
    )


def _make_handler(rules_engine, agent=None, clickup=None):
    return BriefingHandler(
        agent=agent or MagicMock(),
        clickup_client=clickup or MagicMock(),
        rules_engine=rules_engine,
        allowed_user_ids=[999],
    )


def _make_update(user_id=999, mime_type="application/pdf", file_size=1024, file_name="brief.pdf"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    update.message.document.mime_type = mime_type
    update.message.document.file_size = file_size
    update.message.document.file_name = file_name

    tg_file = AsyncMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake-pdf"))
    update.message.document.get_file = AsyncMock(return_value=tg_file)

    return update


@pytest.mark.asyncio
async def test_handle_document_unauthorized_user(rules_engine):
    handler = _make_handler(rules_engine)
    update = _make_update(user_id=000)

    context = MagicMock()
    context.user_data = {}
    await handler.handle_document(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "permissao" in msg.lower()


@pytest.mark.asyncio
async def test_handle_document_rejects_non_pdf(rules_engine):
    handler = _make_handler(rules_engine)
    update = _make_update(mime_type="application/msword")

    context = MagicMock()
    context.user_data = {}
    await handler.handle_document(update, context)

    update.message.reply_text.assert_called_once()
    assert "apenas arquivos PDF" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_document_rejects_large_file(rules_engine):
    handler = _make_handler(rules_engine)
    update = _make_update(file_size=MAX_FILE_SIZE + 1)

    context = MagicMock()
    context.user_data = {}
    await handler.handle_document(update, context)

    update.message.reply_text.assert_called_once()
    assert "muito grande" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_document_full_flow(rules_engine, mock_analysis):
    mock_response = MagicMock()
    mock_response.content = mock_analysis
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_clickup.create_task = AsyncMock(
        side_effect=[
            {"id": "parent_123", "name": "Instagram - Loja Bella - Fevereiro 2026"},
            {"id": "sub_1", "name": "Post 1 - Verao"},
        ]
    )

    handler = _make_handler(rules_engine, agent=mock_agent, clickup=mock_clickup)
    update = _make_update()

    context = MagicMock()
    context.user_data = {}
    with patch("src.bot.handlers.extract_text_from_pdf", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = "Briefing do cliente Loja Bella: 1 post Instagram verao."
        await handler.handle_document(update, context)

    # "Processando PDF..." + result
    assert update.message.reply_text.call_count == 2
    assert "Processando PDF" in update.message.reply_text.call_args_list[0][0][0]

    final_response = update.message.reply_text.call_args_list[1][0][0]
    assert "Loja Bella" in final_response
    assert "Post 1 - Verao" in final_response


@pytest.mark.asyncio
async def test_handle_document_extraction_error(rules_engine):
    handler = _make_handler(rules_engine)
    update = _make_update()

    context = MagicMock()
    context.user_data = {}
    with patch("src.bot.handlers.extract_text_from_pdf", new_callable=AsyncMock) as mock_extract:
        mock_extract.side_effect = ValueError("Nao foi possivel extrair texto do PDF.")
        await handler.handle_document(update, context)

    # "Processando PDF..." + error
    assert update.message.reply_text.call_count == 2
    error_msg = update.message.reply_text.call_args_list[1][0][0]
    assert "Erro no PDF" in error_msg


@pytest.mark.asyncio
async def test_handle_document_generic_error(rules_engine):
    handler = _make_handler(rules_engine)
    update = _make_update()

    context = MagicMock()
    context.user_data = {}
    with patch("src.bot.handlers.extract_text_from_pdf", new_callable=AsyncMock) as mock_extract:
        mock_extract.side_effect = RuntimeError("Network error")
        await handler.handle_document(update, context)

    # "Processando PDF..." + error
    assert update.message.reply_text.call_count == 2
    error_msg = update.message.reply_text.call_args_list[1][0][0]
    assert "Erro" in error_msg


@pytest.mark.asyncio
async def test_handle_message_still_works_after_refactor(rules_engine, mock_analysis):
    """Verify the text handler still works after refactoring to _process_briefing."""
    mock_response = MagicMock()
    mock_response.content = mock_analysis
    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_clickup.create_task = AsyncMock(
        side_effect=[
            {"id": "parent_123", "name": "Instagram - Loja Bella - Fevereiro 2026"},
            {"id": "sub_1", "name": "Post 1 - Verao"},
        ]
    )

    handler = _make_handler(rules_engine, agent=mock_agent, clickup=mock_clickup)

    update = MagicMock()
    update.effective_user.id = 999
    update.message.text = "Briefing do cliente Loja Bella: 1 post Instagram verao."
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}
    await handler.handle_message(update, context)

    assert update.message.reply_text.call_count == 2
    final_response = update.message.reply_text.call_args_list[1][0][0]
    assert "Loja Bella" in final_response
