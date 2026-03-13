import asyncio

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB (limite Telegram)
MAX_PAGES = 50


def _extract_sync(pdf_bytes: bytes, filename: str) -> str:
    """Extracao sincrona - roda em thread pool."""
    import pymupdf
    import pymupdf4llm

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return pymupdf4llm.to_markdown(doc)


async def extract_text_from_pdf(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """Extrai texto de PDF usando PyMuPDF (async wrapper)."""
    text = await asyncio.to_thread(_extract_sync, pdf_bytes, filename)
    if not text or not text.strip():
        raise ValueError("Nao foi possivel extrair texto do PDF.")
    return text.strip()
