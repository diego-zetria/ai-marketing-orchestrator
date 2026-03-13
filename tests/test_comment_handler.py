"""Tests for CommentHandler (A1 auto-status + A3 Drive link extraction)."""
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from src.bot.comment_handler import CommentHandler
from src.engine.rules import RulesEngine


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_clickup():
    client = AsyncMock()
    client.get_task = AsyncMock(return_value={
        "id": "t1",
        "name": "Post Instagram ClientDelta",
        "status": {"status": "revisao"},
        "assignees": [],
        "custom_fields": [],
    })
    client.update_task = AsyncMock(return_value={"id": "t1"})
    client.set_custom_field = AsyncMock(return_value={})
    return client


@pytest.fixture
def rules_engine(tmp_path):
    rules = {
        "assignment_rules": {},
        "reviewers": {},
        "client_overrides": {},
        "default_config": {"list_id": "list1"},
        "team_mapping": {
            "201": {
                "telegram_chat_id": 2001,
                "name": "Luis Reviewer",
                "role": "strategy_reviewer",
            },
            "101": {
                "telegram_chat_id": 1001,
                "name": "Pedro Designer",
                "role": "designer",
            },
            "999": {
                "telegram_chat_id": 9001,
                "name": "Unknown",
                "role": "admin",
            },
        },
        "notification_rules": {},
    }
    f = tmp_path / "rules.yaml"
    f.write_text(yaml.dump(rules))
    return RulesEngine(f)


def _make_comment_event(
    task_id="t1",
    text="some comment",
    user_id=201,
    bookmarks=None,
):
    """Build a taskCommentPosted event."""
    comment_items = []
    if bookmarks:
        for url in bookmarks:
            comment_items.append({
                "type": "bookmark",
                "attributes": {"url": url},
            })

    return {
        "event": "taskCommentPosted",
        "task_id": task_id,
        "history_items": [{
            "comment": {
                "text_content": text,
                "comment": comment_items,
            },
            "user": {"id": user_id, "username": "User"},
        }],
    }


# === A3: Drive link extraction ===

class TestDriveLinkExtraction:
    @pytest.mark.asyncio
    async def test_extracts_drive_link_from_bookmark(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            drive_link_field_id="cf_drive",
        )
        event = _make_comment_event(
            text="Segue o link",
            bookmarks=["https://drive.google.com/file/d/abc123/view"],
        )
        await handler.handle_comment(event)

        mock_clickup.set_custom_field.assert_awaited_once_with(
            "t1", "cf_drive", "https://drive.google.com/file/d/abc123/view",
        )

    @pytest.mark.asyncio
    async def test_extracts_drive_link_from_text(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            drive_link_field_id="cf_drive",
        )
        event = _make_comment_event(
            text="Veja aqui https://drive.google.com/folder/xyz ok?",
        )
        await handler.handle_comment(event)

        mock_clickup.set_custom_field.assert_awaited_once()
        saved_link = mock_clickup.set_custom_field.call_args[0][2]
        assert "drive.google.com" in saved_link

    @pytest.mark.asyncio
    async def test_ignores_non_drive_links(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            drive_link_field_id="cf_drive",
        )
        event = _make_comment_event(
            text="veja https://example.com/file",
            bookmarks=["https://example.com/other"],
        )
        await handler.handle_comment(event)

        mock_clickup.set_custom_field.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_field_id_skips_extraction(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            drive_link_field_id="",
        )
        event = _make_comment_event(
            text="https://drive.google.com/file/abc",
        )
        await handler.handle_comment(event)

        mock_clickup.set_custom_field.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deduplicates_links(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        """Same link in bookmark and text should only be saved once."""
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            drive_link_field_id="cf_drive",
        )
        link = "https://drive.google.com/file/d/abc123/view"
        event = _make_comment_event(
            text=f"Link: {link}",
            bookmarks=[link],
        )
        await handler.handle_comment(event)

        mock_clickup.set_custom_field.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_error_doesnt_crash(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        mock_clickup.set_custom_field.side_effect = Exception("API error")
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            drive_link_field_id="cf_drive",
        )
        event = _make_comment_event(
            text="https://drive.google.com/file/abc",
        )
        await handler.handle_comment(event)


# === A1: Intent detection + auto-status ===

class TestIntentDetectionAutoMode:
    @pytest.mark.asyncio
    async def test_auto_mode_moves_status(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        mock_clickup.get_task.return_value = {
            "id": "t1",
            "name": "Post Instagram",
            "status": {"status": "revisao"},
        }
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            auto_status_mode="auto",
        )
        event = _make_comment_event(
            text="aprovado",
            user_id=201,  # strategy_reviewer
        )
        await handler.handle_comment(event)

        mock_clickup.update_task.assert_awaited_once_with(
            "t1", status="aprovado",
        )

    @pytest.mark.asyncio
    async def test_confirm_mode_sends_buttons(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        mock_clickup.get_task.return_value = {
            "id": "t1",
            "name": "Post Instagram",
            "status": {"status": "revisao"},
        }
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            auto_status_mode="confirm",
            group_chat_id=12345,
        )
        event = _make_comment_event(
            text="aprovado",
            user_id=201,
        )
        await handler.handle_comment(event)

        mock_clickup.update_task.assert_not_awaited()
        mock_bot.send_message.assert_awaited_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 12345
        assert "aprovado" in call_kwargs["text"].lower()
        assert call_kwargs["reply_markup"] is not None


class TestIntentNoMatch:
    @pytest.mark.asyncio
    async def test_no_intent_detected(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        mock_clickup.get_task.return_value = {
            "id": "t1",
            "name": "Post",
            "status": {"status": "revisao"},
        }
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            auto_status_mode="auto",
        )
        event = _make_comment_event(
            text="bom dia, vou verificar",
            user_id=201,
        )
        await handler.handle_comment(event)

        mock_clickup.update_task.assert_not_awaited()
        mock_bot.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_user_skipped(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        """User not in team_mapping has no role -> skip."""
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
            auto_status_mode="auto",
        )
        event = _make_comment_event(
            text="aprovado",
            user_id=88888,  # not in team_mapping
        )
        await handler.handle_comment(event)

        mock_clickup.update_task.assert_not_awaited()


class TestEmptyComment:
    @pytest.mark.asyncio
    async def test_empty_comment_text(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
        )
        event = _make_comment_event(text="")
        await handler.handle_comment(event)

        mock_clickup.get_task.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_history_items(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
        )
        event = {"event": "taskCommentPosted", "task_id": "t1", "history_items": []}
        await handler.handle_comment(event)


# === Callback handler ===

class TestAutoStatusCallback:
    @pytest.mark.asyncio
    async def test_confirm_moves_status(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
        )
        query = AsyncMock()
        query.data = "autostatus_confirm:t1:aprovado"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        await handler.handle_auto_status_callback(update, None)

        query.answer.assert_awaited_once()
        mock_clickup.update_task.assert_awaited_once_with("t1", status="aprovado")
        query.edit_message_text.assert_awaited_once()
        assert "aprovado" in query.edit_message_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_ignore_edits_message(
        self, mock_bot, mock_clickup, rules_engine,
    ):
        handler = CommentHandler(
            bot=mock_bot, rules_engine=rules_engine,
            clickup_client=mock_clickup,
        )
        query = AsyncMock()
        query.data = "autostatus_ignore:t1:aprovado"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        await handler.handle_auto_status_callback(update, None)

        query.answer.assert_awaited_once()
        mock_clickup.update_task.assert_not_awaited()
        assert "ignorado" in query.edit_message_text.call_args[0][0].lower()
