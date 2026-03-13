from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.command_handlers import VALID_STATUSES, CommandHandlers, _extract_task_id, handle_meuid


@pytest.fixture
def mock_clickup():
    return AsyncMock()


@pytest.fixture
def mock_rules():
    rules = MagicMock()
    rules.get_clickup_user_id.return_value = "95324421"
    rules.get_all_mapped_users.return_value = {
        "95324421": {"telegram_chat_id": 111, "name": "Pedro"},
    }
    _client_overrides = {
        "client_delta": {"list_id": "list_client_delta"},
    }
    rules.get_all_clients.return_value = _client_overrides
    rules.get_default_list_id.return_value = "list_default"
    rules.get_client_config.side_effect = lambda name: (
        _client_overrides.get(name, {})
    )
    return rules


@pytest.fixture
def commands(mock_clickup, mock_rules):
    return CommandHandlers(
        clickup_client=mock_clickup,
        rules_engine=mock_rules,
        allowed_user_ids=[999],
    )


def _make_update(user_id=999, text="/status"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    # _move_task checks hasattr(target, "edit_message_text") to distinguish
    # Message from CallbackQuery. Remove auto-created attr so it falls
    # through to reply_text.
    del update.message.edit_message_text
    return update


# === /meuid ===


@pytest.mark.asyncio
async def test_meuid_returns_user_info():
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.full_name = "Admin User"
    update.effective_user.username = "diegoramos"
    update.message.reply_text = AsyncMock()

    await handle_meuid(update, MagicMock())

    reply = update.message.reply_text.call_args[0][0]
    assert "12345" in reply
    assert "Admin User" in reply
    assert "@diegoramos" in reply


@pytest.mark.asyncio
async def test_meuid_without_username():
    update = MagicMock()
    update.effective_user.id = 67890
    update.effective_user.full_name = "Maria"
    update.effective_user.username = None
    update.message.reply_text = AsyncMock()

    await handle_meuid(update, MagicMock())

    reply = update.message.reply_text.call_args[0][0]
    assert "67890" in reply
    assert "Maria" in reply
    assert "@" not in reply


# === /status ===

@pytest.mark.asyncio
async def test_status_shows_tasks(commands, mock_clickup):
    mock_clickup.get_tasks.return_value = [
        {
            "id": "t1",
            "name": "Post ClientDelta 03/03",
            "status": {"status": "desenvolvimento"},
            "assignees": [{"id": 95324421, "username": "Pedro"}],
            "due_date": "1709251200000",
        },
    ]

    update = _make_update()
    context = MagicMock()

    await commands.handle_status(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Post ClientDelta" in msg


@pytest.mark.asyncio
async def test_status_no_tasks(commands, mock_clickup):
    mock_clickup.get_tasks.return_value = []

    update = _make_update()
    context = MagicMock()

    await commands.handle_status(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "sem tasks" in msg.lower() or "nenhuma" in msg.lower()


@pytest.mark.asyncio
async def test_status_unauthorized(commands, mock_clickup):
    update = _make_update(user_id=000)
    context = MagicMock()

    await commands.handle_status(update, context)

    mock_clickup.get_tasks.assert_not_called()


@pytest.mark.asyncio
async def test_status_filters_done_tasks(commands, mock_clickup):
    mock_clickup.get_tasks.return_value = [
        {
            "id": "t1", "name": "Active",
            "status": {"status": "desenvolvimento"}, "assignees": [], "due_date": None,
        },
        {
            "id": "t2", "name": "Done",
            "status": {"status": "pronto"}, "assignees": [], "due_date": None,
        },
    ]

    update = _make_update()
    context = MagicMock()

    await commands.handle_status(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "Active" in msg
    assert "Done" not in msg


# === /pendencias ===

@pytest.mark.asyncio
async def test_pendencias_shows_overdue(commands, mock_clickup):
    mock_clickup.get_tasks.return_value = [
        {
            "id": "t1", "name": "Post atrasado",
            "status": {"status": "desenvolvimento"},
            "assignees": [{"id": 95324421, "username": "Pedro"}],
            "due_date": "1609459200000",  # 2021-01-01 (past)
        },
        {
            "id": "t2", "name": "Post no prazo",
            "status": {"status": "desenvolvimento"},
            "assignees": [],
            "due_date": "1893456000000",  # 2030-01-01 (future)
        },
    ]

    update = _make_update(text="/pendencias")
    context = MagicMock()

    await commands.handle_pendencias(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Post atrasado" in msg
    assert "Post no prazo" not in msg


@pytest.mark.asyncio
async def test_pendencias_no_overdue(commands, mock_clickup):
    mock_clickup.get_tasks.return_value = [
        {
            "id": "t1", "name": "On time",
            "status": {"status": "desenvolvimento"},
            "assignees": [],
            "due_date": "1893456000000",  # future
        },
    ]

    update = _make_update(text="/pendencias")
    context = MagicMock()

    await commands.handle_pendencias(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "nenhuma" in msg.lower() or "atrasada" in msg.lower()


# === /minhas ===

@pytest.mark.asyncio
async def test_minhas_shows_user_tasks(commands, mock_clickup, mock_rules):
    mock_clickup.get_tasks.return_value = [
        {
            "id": "t1", "name": "Minha task",
            "status": {"status": "desenvolvimento"},
            "assignees": [{"id": 95324421, "username": "Pedro"}],
            "due_date": None,
        },
    ]

    update = _make_update(text="/minhas")
    context = MagicMock()

    await commands.handle_minhas(update, context)

    update.message.reply_text.assert_called_once()
    msg = update.message.reply_text.call_args[0][0]
    assert "Minha task" in msg


@pytest.mark.asyncio
async def test_minhas_unmapped_user(commands, mock_clickup, mock_rules):
    mock_rules.get_clickup_user_id.return_value = None

    update = _make_update(text="/minhas")
    context = MagicMock()

    await commands.handle_minhas(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "mapeado" in msg.lower() or "configurar" in msg.lower()
    mock_clickup.get_tasks.assert_not_called()


@pytest.mark.asyncio
async def test_minhas_no_tasks(commands, mock_clickup):
    mock_clickup.get_tasks.return_value = []

    update = _make_update(text="/minhas")
    context = MagicMock()

    await commands.handle_minhas(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "nao tem" in msg.lower() or "sem tasks" in msg.lower() or "nenhuma" in msg.lower()


# === Utility ===

def test_format_due_date():
    result = CommandHandlers._format_due_date("1709251200000")
    assert "/" in result  # DD/MM format


def test_format_due_date_none():
    result = CommandHandlers._format_due_date(None)
    assert result == ""


def test_format_due_date_invalid():
    result = CommandHandlers._format_due_date("invalid")
    assert result == ""


# === _extract_task_id ===

def test_extract_task_id_plain():
    assert _extract_task_id("abc123") == "abc123"


def test_extract_task_id_from_url():
    assert _extract_task_id("https://app.clickup.com/t/abc123") == "abc123"


def test_extract_task_id_from_url_with_path():
    assert _extract_task_id("https://app.clickup.com/t/86abc123/some-title") == "86abc123"


def test_extract_task_id_strips_whitespace():
    assert _extract_task_id("  abc123  ") == "abc123"


# === VALID_STATUSES ===

def test_valid_statuses_contains_known():
    assert "revisão" in VALID_STATUSES
    assert "em criação" in VALID_STATUSES
    assert "pronto" in VALID_STATUSES


# === /mover ===

@pytest.mark.asyncio
async def test_mover_success(commands, mock_clickup):
    mock_clickup.update_task.return_value = {
        "id": "abc123", "status": {"status": "revisão"},
    }

    update = _make_update(text="/mover abc123 revisao")
    update.message.text = "/mover abc123 revisao"
    context = MagicMock()
    context.args = ["abc123", "revisao"]

    await commands.handle_mover(update, context)

    # "revisao" gets normalized to "revisão" by _normalize_status
    mock_clickup.update_task.assert_called_once_with("abc123", status="revisão")
    msg = update.message.reply_text.call_args[0][0]
    assert "revisão" in msg.lower()


@pytest.mark.asyncio
async def test_mover_with_url(commands, mock_clickup):
    mock_clickup.update_task.return_value = {
        "id": "abc123", "status": {"status": "desenvolvimento"},
    }

    update = _make_update(text="/mover https://app.clickup.com/t/abc123 desenvolvimento")
    context = MagicMock()
    context.args = ["https://app.clickup.com/t/abc123", "desenvolvimento"]

    await commands.handle_mover(update, context)

    mock_clickup.update_task.assert_called_once_with("abc123", status="desenvolvimento")


@pytest.mark.asyncio
async def test_mover_em_criacao(commands, mock_clickup):
    """Status 'em criacao' has a space, should be joined and normalized."""
    mock_clickup.update_task.return_value = {
        "id": "abc123", "status": {"status": "em criação"},
    }

    update = _make_update(text="/mover abc123 em criacao")
    context = MagicMock()
    context.args = ["abc123", "em", "criacao"]

    await commands.handle_mover(update, context)

    # "em criacao" gets normalized to "em criação" by _normalize_status
    mock_clickup.update_task.assert_called_once_with("abc123", status="em criação")


@pytest.mark.asyncio
async def test_mover_invalid_status(commands, mock_clickup):
    update = _make_update(text="/mover abc123 invalido")
    context = MagicMock()
    context.args = ["abc123", "invalido"]

    await commands.handle_mover(update, context)

    mock_clickup.update_task.assert_not_called()
    msg = update.message.reply_text.call_args[0][0]
    assert "status" in msg.lower()


@pytest.mark.asyncio
async def test_mover_no_args(commands, mock_clickup):
    update = _make_update(text="/mover")
    context = MagicMock()
    context.args = []

    await commands.handle_mover(update, context)

    mock_clickup.update_task.assert_not_called()
    # No args triggers interactive mode (list picker)
    msg = update.message.reply_text.call_args[0][0]
    assert "selecione" in msg.lower() or "lista" in msg.lower()


@pytest.mark.asyncio
async def test_mover_unauthorized(commands, mock_clickup):
    update = _make_update(user_id=000, text="/mover abc123 revisao")
    context = MagicMock()
    context.args = ["abc123", "revisao"]

    await commands.handle_mover(update, context)

    mock_clickup.update_task.assert_not_called()


@pytest.mark.asyncio
async def test_mover_api_error(commands, mock_clickup):
    import httpx
    mock_clickup.update_task.side_effect = httpx.HTTPStatusError(
        "Not found", request=MagicMock(), response=MagicMock(status_code=404),
    )

    update = _make_update(text="/mover abc123 revisao")
    context = MagicMock()
    context.args = ["abc123", "revisao"]

    await commands.handle_mover(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "erro" in msg.lower()


# === /comentar ===

@pytest.mark.asyncio
async def test_comentar_success(commands, mock_clickup):
    mock_clickup.add_comment.return_value = {
        "id": "c1", "comment_text": "Ficou otimo!",
    }

    update = _make_update(text="/comentar abc123 Ficou otimo!")
    context = MagicMock()
    context.args = ["abc123", "Ficou", "otimo!"]

    await commands.handle_comentar(update, context)

    mock_clickup.add_comment.assert_called_once_with("abc123", "Ficou otimo!")
    msg = update.message.reply_text.call_args[0][0]
    assert "comentario" in msg.lower() or "adicionado" in msg.lower()


@pytest.mark.asyncio
async def test_comentar_with_url(commands, mock_clickup):
    mock_clickup.add_comment.return_value = {"id": "c1", "comment_text": "ok"}

    update = _make_update(text="/comentar https://app.clickup.com/t/abc123 Aprovado!")
    context = MagicMock()
    context.args = ["https://app.clickup.com/t/abc123", "Aprovado!"]

    await commands.handle_comentar(update, context)

    mock_clickup.add_comment.assert_called_once_with("abc123", "Aprovado!")


@pytest.mark.asyncio
async def test_comentar_no_args(commands, mock_clickup):
    update = _make_update(text="/comentar")
    context = MagicMock()
    context.args = []

    await commands.handle_comentar(update, context)

    mock_clickup.add_comment.assert_not_called()
    msg = update.message.reply_text.call_args[0][0]
    assert "uso" in msg.lower() or "/comentar" in msg.lower()


@pytest.mark.asyncio
async def test_comentar_no_text(commands, mock_clickup):
    update = _make_update(text="/comentar abc123")
    context = MagicMock()
    context.args = ["abc123"]

    await commands.handle_comentar(update, context)

    mock_clickup.add_comment.assert_not_called()
    msg = update.message.reply_text.call_args[0][0]
    assert "texto" in msg.lower() or "comentario" in msg.lower()


@pytest.mark.asyncio
async def test_comentar_unauthorized(commands, mock_clickup):
    update = _make_update(user_id=000, text="/comentar abc123 teste")
    context = MagicMock()
    context.args = ["abc123", "teste"]

    await commands.handle_comentar(update, context)

    mock_clickup.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_comentar_api_error(commands, mock_clickup):
    import httpx
    mock_clickup.add_comment.side_effect = httpx.HTTPStatusError(
        "Not found", request=MagicMock(), response=MagicMock(status_code=404),
    )

    update = _make_update(text="/comentar abc123 teste")
    context = MagicMock()
    context.args = ["abc123", "teste"]

    await commands.handle_comentar(update, context)

    msg = update.message.reply_text.call_args[0][0]
    assert "erro" in msg.lower()
