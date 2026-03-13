from unittest.mock import patch

import pytest

from src.bot.pdf_extractor import extract_text_from_pdf


@pytest.mark.asyncio
async def test_extract_text_from_pdf_valid():
    with patch("src.bot.pdf_extractor._extract_sync") as mock_sync:
        mock_sync.return_value = "# Briefing\n\nCliente: Loja Bella"
        text = await extract_text_from_pdf(b"fake-pdf-bytes", "briefing.pdf")

    assert "Loja Bella" in text
    assert text.startswith("# Briefing")
    mock_sync.assert_called_once_with(b"fake-pdf-bytes", "briefing.pdf")


@pytest.mark.asyncio
async def test_extract_text_from_pdf_empty_text_raises():
    with patch("src.bot.pdf_extractor._extract_sync") as mock_sync:
        mock_sync.return_value = ""
        with pytest.raises(ValueError, match="Nao foi possivel extrair texto"):
            await extract_text_from_pdf(b"fake-pdf-bytes", "empty.pdf")


@pytest.mark.asyncio
async def test_extract_text_from_pdf_whitespace_only_raises():
    with patch("src.bot.pdf_extractor._extract_sync") as mock_sync:
        mock_sync.return_value = "   \n  \n  "
        with pytest.raises(ValueError, match="Nao foi possivel extrair texto"):
            await extract_text_from_pdf(b"fake-pdf-bytes", "blank.pdf")


@pytest.mark.asyncio
async def test_extract_text_from_pdf_strips_whitespace():
    with patch("src.bot.pdf_extractor._extract_sync") as mock_sync:
        mock_sync.return_value = "\n  Briefing content  \n\n"
        text = await extract_text_from_pdf(b"fake-pdf-bytes")

    assert text == "Briefing content"


@pytest.mark.asyncio
async def test_extract_text_from_pdf_default_filename():
    with patch("src.bot.pdf_extractor._extract_sync") as mock_sync:
        mock_sync.return_value = "Some text"
        await extract_text_from_pdf(b"fake-pdf-bytes")

    mock_sync.assert_called_once_with(b"fake-pdf-bytes", "document.pdf")


@pytest.mark.asyncio
async def test_extract_text_from_pdf_converter_error():
    with patch("src.bot.pdf_extractor._extract_sync") as mock_sync:
        mock_sync.side_effect = RuntimeError("Invalid PDF")
        with pytest.raises(RuntimeError, match="Invalid PDF"):
            await extract_text_from_pdf(b"not-a-pdf", "bad.pdf")
