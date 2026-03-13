"""Tests for AudioTranscriber (Groq + OpenAI fallback)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.audio_transcriber import MAX_AUDIO_DURATION, MAX_AUDIO_FILE_SIZE, AudioTranscriber


class TestAudioTranscriberInit:
    def test_no_api_keys_raises(self):
        with pytest.raises(ValueError, match="Pelo menos uma API key"):
            AudioTranscriber()

    @patch("src.bot.audio_transcriber.AsyncGroq")
    def test_groq_only(self, mock_groq_cls):
        t = AudioTranscriber(groq_api_key="gsk_test")
        assert t._groq_client is not None
        assert t._openai_client is None

    @patch("src.bot.audio_transcriber.AsyncOpenAI")
    def test_openai_only(self, mock_openai_cls):
        t = AudioTranscriber(openai_api_key="sk_test")
        assert t._groq_client is None
        assert t._openai_client is not None

    @patch("src.bot.audio_transcriber.AsyncOpenAI")
    @patch("src.bot.audio_transcriber.AsyncGroq")
    def test_both_keys(self, mock_groq_cls, mock_openai_cls):
        t = AudioTranscriber(groq_api_key="gsk_test", openai_api_key="sk_test")
        assert t._groq_client is not None
        assert t._openai_client is not None


class TestAudioTranscriberTranscribe:
    @patch("src.bot.audio_transcriber.AsyncGroq")
    async def test_groq_success(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value="texto transcrito")
        mock_groq_cls.return_value = mock_client

        t = AudioTranscriber(groq_api_key="gsk_test")
        result = await t.transcribe(b"fake_audio", "audio.ogg")
        assert result == "texto transcrito"
        mock_client.audio.transcriptions.create.assert_awaited_once()

    @patch("src.bot.audio_transcriber.AsyncGroq")
    async def test_groq_returns_object(self, mock_groq_cls):
        mock_resp = MagicMock()
        mock_resp.text = "texto via objeto"
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_resp)
        mock_groq_cls.return_value = mock_client

        t = AudioTranscriber(groq_api_key="gsk_test")
        result = await t.transcribe(b"fake_audio", "audio.ogg")
        assert result == "texto via objeto"

    @patch("src.bot.audio_transcriber.AsyncOpenAI")
    @patch("src.bot.audio_transcriber.AsyncGroq")
    async def test_groq_fails_openai_succeeds(self, mock_groq_cls, mock_openai_cls):
        groq_client = MagicMock()
        groq_client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("Groq error")
        )
        mock_groq_cls.return_value = groq_client

        openai_client = MagicMock()
        openai_client.audio.transcriptions.create = AsyncMock(return_value="texto openai")
        mock_openai_cls.return_value = openai_client

        t = AudioTranscriber(groq_api_key="gsk_test", openai_api_key="sk_test")
        result = await t.transcribe(b"fake_audio", "audio.ogg")
        assert result == "texto openai"

    @patch("src.bot.audio_transcriber.AsyncOpenAI")
    @patch("src.bot.audio_transcriber.AsyncGroq")
    async def test_both_fail_raises(self, mock_groq_cls, mock_openai_cls):
        groq_client = MagicMock()
        groq_client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("Groq error")
        )
        mock_groq_cls.return_value = groq_client

        openai_client = MagicMock()
        openai_client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("OpenAI error")
        )
        mock_openai_cls.return_value = openai_client

        t = AudioTranscriber(groq_api_key="gsk_test", openai_api_key="sk_test")
        with pytest.raises(RuntimeError, match="Todos os servicos"):
            await t.transcribe(b"fake_audio", "audio.ogg")

    @patch("src.bot.audio_transcriber.AsyncGroq")
    async def test_groq_only_fails_raises(self, mock_groq_cls):
        groq_client = MagicMock()
        groq_client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("Groq error")
        )
        mock_groq_cls.return_value = groq_client

        t = AudioTranscriber(groq_api_key="gsk_test")
        with pytest.raises(RuntimeError, match="Todos os servicos"):
            await t.transcribe(b"fake_audio", "audio.ogg")

    @patch("src.bot.audio_transcriber.AsyncGroq")
    async def test_groq_called_with_correct_params(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value="ok")
        mock_groq_cls.return_value = mock_client

        t = AudioTranscriber(groq_api_key="gsk_test")
        await t.transcribe(b"audio_data", "voice.ogg")

        mock_client.audio.transcriptions.create.assert_awaited_once_with(
            file=("voice.ogg", b"audio_data"),
            model="whisper-large-v3-turbo",
            language="pt",
            response_format="text",
            temperature=0.0,
        )


class TestConstants:
    def test_max_file_size(self):
        assert MAX_AUDIO_FILE_SIZE == 20 * 1024 * 1024

    def test_max_duration(self):
        assert MAX_AUDIO_DURATION == 300
