"""Servico de transcricao de audio com fallback Groq -> OpenAI."""

from __future__ import annotations

import logging
from io import BytesIO

from groq import AsyncGroq
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

MAX_AUDIO_FILE_SIZE = 20 * 1024 * 1024  # 20 MB (limite Telegram getFile)
MAX_AUDIO_DURATION = 300  # 5 minutos


class AudioTranscriber:
    """Transcreve audio usando Groq Whisper com fallback para OpenAI."""

    def __init__(
        self,
        groq_api_key: str = "",
        openai_api_key: str = "",
    ):
        self._groq_client: AsyncGroq | None = None
        self._openai_client: AsyncOpenAI | None = None

        if groq_api_key:
            self._groq_client = AsyncGroq(api_key=groq_api_key)

        if openai_api_key:
            self._openai_client = AsyncOpenAI(api_key=openai_api_key)

        if not self._groq_client and not self._openai_client:
            raise ValueError(
                "Pelo menos uma API key (GROQ_API_KEY ou OPENAI_API_KEY) deve ser configurada."
            )

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        """Transcreve audio com fallback automatico.

        Args:
            audio_bytes: Bytes do arquivo de audio.
            filename: Nome do arquivo (extensao importa para a API).

        Returns:
            Texto transcrito.

        Raises:
            RuntimeError: Se todos os servicos falharem.
        """
        if self._groq_client:
            try:
                return await self._transcribe_groq(audio_bytes, filename)
            except Exception as e:
                logger.warning("Groq transcription failed: %s", e)

        if self._openai_client:
            try:
                return await self._transcribe_openai(audio_bytes, filename)
            except Exception as e:
                logger.warning("OpenAI transcription failed: %s", e)

        raise RuntimeError("Todos os servicos de transcricao falharam.")

    async def _transcribe_groq(self, audio_bytes: bytes, filename: str) -> str:
        transcription = await self._groq_client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3-turbo",
            language="pt",
            response_format="text",
            temperature=0.0,
        )
        text = transcription if isinstance(transcription, str) else transcription.text
        logger.info("Groq transcription OK (%d chars)", len(text))
        return text

    async def _transcribe_openai(self, audio_bytes: bytes, filename: str) -> str:
        buffer = BytesIO(audio_bytes)
        buffer.name = filename
        transcription = await self._openai_client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=buffer,
            language="pt",
            response_format="text",
        )
        text = transcription if isinstance(transcription, str) else transcription.text
        logger.info("OpenAI transcription OK (%d chars)", len(text))
        return text
