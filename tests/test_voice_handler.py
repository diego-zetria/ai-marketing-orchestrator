"""Tests for handle_voice in BriefingHandler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers import BriefingHandler


@pytest.fixture
def mock_transcriber():
    t = AsyncMock()
    t.transcribe = AsyncMock(return_value="Briefing do cliente ClientAlpha para marco 2026")
    return t


@pytest.fixture
def handler(mock_transcriber):
    return BriefingHandler(
        agent=MagicMock(),
        clickup_client=AsyncMock(),
        rules_engine=MagicMock(),
        allowed_user_ids=[123, 456],
        audio_transcriber=mock_transcriber,
    )


@pytest.fixture
def handler_no_audio():
    return BriefingHandler(
        agent=MagicMock(),
        clickup_client=AsyncMock(),
        rules_engine=MagicMock(),
        allowed_user_ids=[123, 456],
    )


@pytest.fixture
def mock_voice():
    voice = MagicMock()
    voice.file_size = 1024 * 1024  # 1MB
    voice.duration = 30  # 30 seconds
    voice.get_file = AsyncMock()
    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake_audio"))
    voice.get_file.return_value = tg_file
    return voice


@pytest.fixture
def mock_update_voice(mock_voice):
    update = MagicMock()
    update.effective_user.id = 123
    update.message.voice = mock_voice
    update.message.audio = None
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx


class TestHandleVoiceUnauthorized:
    async def test_unauthorized_user(self, handler, mock_update_voice, mock_context):
        mock_update_voice.effective_user.id = 99999
        await handler.handle_voice(mock_update_voice, mock_context)
        mock_update_voice.message.reply_text.assert_awaited_once_with(
            "Voce nao tem permissao para usar este bot. Seu ID: 99999"
        )


class TestHandleVoiceNoTranscriber:
    async def test_no_transcriber(self, handler_no_audio, mock_update_voice, mock_context):
        await handler_no_audio.handle_voice(mock_update_voice, mock_context)
        mock_update_voice.message.reply_text.assert_awaited_once_with(
            "Transcricao de audio nao esta configurada. Envie o briefing por texto."
        )


class TestHandleVoiceValidation:
    async def test_file_too_large(self, handler, mock_update_voice, mock_context):
        mock_update_voice.message.voice.file_size = 25 * 1024 * 1024
        await handler.handle_voice(mock_update_voice, mock_context)
        call_args = mock_update_voice.message.reply_text.call_args[0][0]
        assert "grande" in call_args.lower()
        assert "20MB" in call_args

    async def test_audio_too_long(self, handler, mock_update_voice, mock_context):
        mock_update_voice.message.voice.duration = 400
        await handler.handle_voice(mock_update_voice, mock_context)
        call_args = mock_update_voice.message.reply_text.call_args[0][0]
        assert "longo" in call_args.lower()

    async def test_no_voice_or_audio(self, handler, mock_context):
        update = MagicMock()
        update.effective_user.id = 123
        update.message.voice = None
        update.message.audio = None
        update.message.reply_text = AsyncMock()
        await handler.handle_voice(update, mock_context)
        # Should not crash, just return silently after transcriber check
        # The "Transcrevendo audio..." message should not be sent
        for call in update.message.reply_text.call_args_list:
            assert "Transcrevendo" not in call[0][0]


class TestHandleVoiceTranscription:
    async def test_empty_transcription(
        self, handler, mock_transcriber, mock_update_voice, mock_context,
    ):
        mock_transcriber.transcribe.return_value = ""
        # reply_text returns a mock message (status_msg) for later edit
        status_msg = AsyncMock()
        mock_update_voice.message.reply_text.return_value = status_msg

        await handler.handle_voice(mock_update_voice, mock_context)
        # Status message should be edited with "nao foi possivel" text
        status_msg.edit_text.assert_awaited()
        edit_text = status_msg.edit_text.call_args[0][0]
        assert "nao foi possivel" in edit_text.lower()

    async def test_short_transcription(
        self, handler, mock_transcriber, mock_update_voice, mock_context,
    ):
        mock_transcriber.transcribe.return_value = "curto"
        status_msg = AsyncMock()
        mock_update_voice.message.reply_text.return_value = status_msg

        await handler.handle_voice(mock_update_voice, mock_context)
        status_msg.edit_text.assert_awaited()
        edit_text = status_msg.edit_text.call_args[0][0]
        assert "nao foi possivel" in edit_text.lower()

    @patch.object(BriefingHandler, "_process_briefing", new_callable=AsyncMock)
    async def test_success_triggers_briefing(
        self, mock_process, handler, mock_transcriber, mock_update_voice, mock_context,
    ):
        mock_transcriber.transcribe.return_value = "Briefing do cliente ClientAlpha para marco 2026"
        status_msg = AsyncMock()
        mock_update_voice.message.reply_text.return_value = status_msg

        await handler.handle_voice(mock_update_voice, mock_context)

        # Status message edited to "Audio transcrito..."
        edit_calls = [c[0][0] for c in status_msg.edit_text.call_args_list]
        assert any("transcrito" in t.lower() for t in edit_calls)

        # _process_briefing called with transcribed text
        mock_process.assert_awaited_once_with(
            mock_update_voice, mock_context,
            "Briefing do cliente ClientAlpha para marco 2026",
        )

    async def test_transcription_error_handled(
        self, handler, mock_transcriber, mock_update_voice, mock_context,
    ):
        mock_transcriber.transcribe.side_effect = RuntimeError("API down")
        status_msg = AsyncMock()
        mock_update_voice.message.reply_text.return_value = status_msg

        await handler.handle_voice(mock_update_voice, mock_context)
        status_msg.edit_text.assert_awaited()
        edit_text = status_msg.edit_text.call_args[0][0]
        assert "erro" in edit_text.lower() or "Erro" in edit_text


class TestHandleVoiceAudioMessage:
    async def test_audio_message_instead_of_voice(
        self, handler, mock_transcriber, mock_context,
    ):
        """Audio sent as file (not voice note) should also work."""
        audio = MagicMock()
        audio.file_size = 2 * 1024 * 1024
        audio.duration = 60
        audio.mime_type = "audio/mpeg"
        tg_file = MagicMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"mp3_data"))
        audio.get_file = AsyncMock(return_value=tg_file)

        update = MagicMock()
        update.effective_user.id = 123
        update.message.voice = None
        update.message.audio = audio
        status_msg = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        mock_transcriber.transcribe.return_value = "Briefing via audio mp3 muito longo"

        with patch.object(BriefingHandler, "_process_briefing", new_callable=AsyncMock) as mock_p:
            await handler.handle_voice(update, mock_context)
            mock_p.assert_awaited_once()
            # Filename should have .mp3 extension
            call_args = mock_transcriber.transcribe.call_args
            assert call_args[0][1].endswith(".mp3")


class TestAudioExtension:
    def test_ogg(self):
        assert BriefingHandler._audio_extension("audio/ogg") == ".ogg"

    def test_mp3(self):
        assert BriefingHandler._audio_extension("audio/mpeg") == ".mp3"

    def test_m4a(self):
        assert BriefingHandler._audio_extension("audio/mp4") == ".m4a"

    def test_wav(self):
        assert BriefingHandler._audio_extension("audio/x-wav") == ".wav"

    def test_unknown_defaults_ogg(self):
        assert BriefingHandler._audio_extension("audio/unknown") == ".ogg"

    def test_none_defaults_ogg(self):
        assert BriefingHandler._audio_extension(None) == ".ogg"
