from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
import yaml

from src.agents.schemas import ContentReview
from src.engine.rules import RulesEngine
from src.integrations.clickup.client import ClickUpClient

# === Task 1: ClickUp get_comments + RulesEngine get_client_by_list_id ===


@pytest.fixture
def clickup_client():
    return ClickUpClient(api_token="test-token")


@respx.mock
@pytest.mark.asyncio
async def test_get_comments(clickup_client):
    respx.get("https://api.clickup.com/api/v2/task/task_abc/comment").mock(
        return_value=httpx.Response(
            200,
            json={
                "comments": [
                    {"id": "c1", "comment_text": "Arte pronta"},
                    {"id": "c2", "comment_text": "Ver anexo"},
                ],
            },
        )
    )
    result = await clickup_client.get_comments("task_abc")
    assert len(result) == 2
    assert result[0]["comment_text"] == "Arte pronta"


@respx.mock
@pytest.mark.asyncio
async def test_get_comments_empty(clickup_client):
    respx.get("https://api.clickup.com/api/v2/task/task_abc/comment").mock(
        return_value=httpx.Response(200, json={"comments": []})
    )
    result = await clickup_client.get_comments("task_abc")
    assert result == []


@pytest.fixture
def rules_engine(tmp_path):
    rules = {
        "assignment_rules": {"design": {"default_assignees": ["101"], "tags": []}},
        "reviewers": {},
        "client_overrides": {
            "ClientDelta": {"designer": "101", "list_id": "list_client_delta"},
            "ClientAlpha": {"designer": "102", "list_id": "list_client_alpha"},
        },
        "default_config": {"list_id": "list_default"},
        "team_mapping": {},
        "notification_rules": {},
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


def test_get_client_by_list_id_found(rules_engine):
    assert rules_engine.get_client_by_list_id("list_client_delta") == "ClientDelta"
    assert rules_engine.get_client_by_list_id("list_client_alpha") == "ClientAlpha"


def test_get_client_by_list_id_default(rules_engine):
    assert rules_engine.get_client_by_list_id("unknown_list") == "default"


# === Task 3: ReviewHandler tests ===


@pytest.fixture
def mock_review():
    return ContentReview(
        checklist=["tom de voz adequado", "ortografia ok", "hashtags presentes"],
        issues=["falta CTA no final"],
        suggestions=["adicionar link na bio"],
        overall_score=7,
        summary="Conteudo bom no geral. Falta CTA. Sugerimos ajuste.",
        approved=False,
    )


@pytest.fixture
def mock_review_approved():
    return ContentReview(
        checklist=["tom de voz adequado", "ortografia ok"],
        issues=[],
        suggestions=[],
        overall_score=9,
        summary="Excelente conteudo. Pronto para publicar.",
        approved=True,
    )


@pytest.fixture
def review_handler_deps(rules_engine):
    mock_agent = MagicMock()
    mock_clickup = AsyncMock(spec=ClickUpClient)
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    return {
        "review_agent": mock_agent,
        "clickup_client": mock_clickup,
        "rules_engine": rules_engine,
        "bot": mock_bot,
        "group_chat_id": -1001234567890,
    }


@pytest.fixture
def review_handler(review_handler_deps):
    from src.bot.review_handler import ReviewHandler

    return ReviewHandler(**review_handler_deps)


@pytest.mark.asyncio
async def test_trigger_review_calls_agent(review_handler, review_handler_deps, mock_review):
    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc",
        "name": "Post Instagram ClientDelta",
        "description": "Campanha verao",
        "list": {"id": "list_client_delta"},
    }
    deps["clickup_client"].get_comments.return_value = [
        {"comment_text": "Arte pronta"},
    ]

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await review_handler.trigger_review("task_abc", "list_client_delta")
        mock_rc.assert_called_once()
        call_kwargs = mock_rc.call_args[1]
        assert call_kwargs["task_name"] == "Post Instagram ClientDelta"
        assert call_kwargs["client_name"] == "ClientDelta"


@pytest.mark.asyncio
async def test_trigger_review_sends_message(review_handler, review_handler_deps, mock_review):
    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc",
        "name": "Post Instagram ClientDelta",
        "description": "Campanha verao",
        "list": {"id": "list_client_delta"},
    }
    deps["clickup_client"].get_comments.return_value = []

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await review_handler.trigger_review("task_abc", "list_client_delta")

    deps["bot"].send_message.assert_called_once()
    call_kwargs = deps["bot"].send_message.call_args[1]
    assert call_kwargs["chat_id"] == -1001234567890
    assert call_kwargs["parse_mode"] == "Markdown"
    assert call_kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_format_review_approved(review_handler, mock_review_approved):
    task = {"id": "task_abc", "name": "Post LinkedIn ClientAlpha"}
    msg = review_handler._format_review_message(task, mock_review_approved)
    assert "9/10" in msg
    assert "Excelente" in msg


@pytest.mark.asyncio
async def test_format_review_issues(review_handler, mock_review):
    task = {"id": "task_abc", "name": "Post Instagram ClientDelta"}
    msg = review_handler._format_review_message(task, mock_review)
    assert "falta CTA" in msg


@pytest.mark.asyncio
async def test_format_review_link(review_handler, mock_review):
    task = {"id": "task_abc", "name": "Post Instagram ClientDelta"}
    msg = review_handler._format_review_message(task, mock_review)
    assert "clickup.com/t/task_abc" in msg


@pytest.mark.asyncio
async def test_callback_approve(review_handler, review_handler_deps):
    deps = review_handler_deps
    deps["clickup_client"].update_task.return_value = {}

    query = AsyncMock()
    query.data = "review_approve:task_abc"
    query.message = MagicMock()
    query.message.text = "Original message"

    update = MagicMock()
    update.callback_query = query

    await review_handler.handle_review_callback(update, None)
    deps["clickup_client"].update_task.assert_called_once_with("task_abc", status="aprovado")
    query.edit_message_text.assert_called_once()
    assert "Aprovado" in query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_change(review_handler, review_handler_deps):
    deps = review_handler_deps
    deps["clickup_client"].update_task.return_value = {}

    query = AsyncMock()
    query.data = "review_change:task_abc"
    query.message = MagicMock()
    query.message.text = "Original message"

    update = MagicMock()
    update.callback_query = query

    await review_handler.handle_review_callback(update, None)
    deps["clickup_client"].update_task.assert_called_once_with("task_abc", status="alteracao")
    query.edit_message_text.assert_called_once()
    assert "Alteracao" in query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_edits_message(review_handler, review_handler_deps):
    deps = review_handler_deps
    deps["clickup_client"].update_task.return_value = {}

    query = AsyncMock()
    query.data = "review_approve:task_xyz"
    query.message = MagicMock()
    query.message.text = "Review message here"

    update = MagicMock()
    update.callback_query = query

    await review_handler.handle_review_callback(update, None)
    query.edit_message_text.assert_called_once()
    edited_text = query.edit_message_text.call_args[0][0]
    assert "Review message here" in edited_text


@pytest.mark.asyncio
async def test_trigger_review_error_no_crash(review_handler, review_handler_deps):
    deps = review_handler_deps
    deps["clickup_client"].get_task.side_effect = Exception("API down")

    # Should not raise
    await review_handler.trigger_review("task_abc", "list_client_delta")
    deps["bot"].send_message.assert_not_called()


def test_review_keyboard_data():
    from src.bot.keyboards import review_action_keyboard

    kb = review_action_keyboard("task_xyz")
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].callback_data == "review_approve:task_xyz"
    assert buttons[1].callback_data == "review_change:task_xyz"
    assert buttons[0].text == "Aprovar"
    assert buttons[1].text == "Pedir Alteracao"


# === A4: Review checklist tests ===


@pytest.mark.asyncio
async def test_trigger_review_creates_checklist(
    review_handler, review_handler_deps, mock_review,
):
    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc",
        "name": "Post Instagram ClientDelta",
        "description": "Campanha verao",
    }
    deps["clickup_client"].get_comments.return_value = []
    deps["clickup_client"].create_checklist.return_value = {"id": "cl_1"}
    deps["clickup_client"].add_checklist_item.return_value = {}

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await review_handler.trigger_review("task_abc", "list_client_delta")

    deps["clickup_client"].create_checklist.assert_awaited_once_with(
        "task_abc", "Revisao IA",
    )
    # 5 standard + 1 issue + 1 suggestion = 7 items
    assert deps["clickup_client"].add_checklist_item.await_count == 7


@pytest.mark.asyncio
async def test_checklist_items_include_issues_and_suggestions(
    review_handler, review_handler_deps, mock_review,
):
    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc", "name": "Post", "description": "",
    }
    deps["clickup_client"].get_comments.return_value = []
    deps["clickup_client"].create_checklist.return_value = {"id": "cl_1"}
    deps["clickup_client"].add_checklist_item.return_value = {}

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await review_handler.trigger_review("task_abc", "list_client_delta")

    item_names = [
        call.args[1]
        for call in deps["clickup_client"].add_checklist_item.call_args_list
    ]
    assert any("[Problema]" in n for n in item_names)
    assert any("[Sugestao]" in n for n in item_names)


@pytest.mark.asyncio
async def test_checklist_includes_standard_items(
    review_handler, review_handler_deps, mock_review_approved,
):
    """Even an approved review gets standard checklist items."""
    from src.bot.review_handler import ReviewHandler

    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc", "name": "Post", "description": "",
    }
    deps["clickup_client"].get_comments.return_value = []
    deps["clickup_client"].create_checklist.return_value = {"id": "cl_1"}
    deps["clickup_client"].add_checklist_item.return_value = {}

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review_approved
        await review_handler.trigger_review("task_abc", "list_client_delta")

    item_names = [
        call.args[1]
        for call in deps["clickup_client"].add_checklist_item.call_args_list
    ]
    for std_item in ReviewHandler.STANDARD_CHECKLIST_ITEMS:
        assert std_item in item_names


@pytest.mark.asyncio
async def test_checklist_error_doesnt_block_notification(
    review_handler, review_handler_deps, mock_review,
):
    """If checklist creation fails, the Telegram message is still sent."""
    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc", "name": "Post", "description": "",
    }
    deps["clickup_client"].get_comments.return_value = []
    deps["clickup_client"].create_checklist.side_effect = Exception("API error")

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await review_handler.trigger_review("task_abc", "list_client_delta")

    # Notification should still be sent
    deps["bot"].send_message.assert_called_once()


@pytest.mark.asyncio
async def test_checklist_disabled(review_handler_deps, mock_review):
    """create_checklist=False skips checklist creation."""
    from src.bot.review_handler import ReviewHandler

    deps = review_handler_deps
    handler = ReviewHandler(**deps, create_checklist=False)

    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc", "name": "Post", "description": "",
    }
    deps["clickup_client"].get_comments.return_value = []

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await handler.trigger_review("task_abc", "list_client_delta")

    deps["clickup_client"].create_checklist.assert_not_awaited()
    # But notification is still sent
    deps["bot"].send_message.assert_called_once()


@pytest.mark.asyncio
async def test_checklist_no_id_returned(
    review_handler, review_handler_deps, mock_review,
):
    """If create_checklist returns no ID, items are not added."""
    deps = review_handler_deps
    deps["clickup_client"].get_task.return_value = {
        "id": "task_abc", "name": "Post", "description": "",
    }
    deps["clickup_client"].get_comments.return_value = []
    deps["clickup_client"].create_checklist.return_value = {}  # no id

    with patch("src.bot.review_handler.review_content", new_callable=AsyncMock) as mock_rc:
        mock_rc.return_value = mock_review
        await review_handler.trigger_review("task_abc", "list_client_delta")

    deps["clickup_client"].add_checklist_item.assert_not_awaited()
