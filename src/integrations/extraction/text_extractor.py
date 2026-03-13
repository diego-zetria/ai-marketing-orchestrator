"""Extract text from uploaded documents for knowledge base injection."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

TEXT_TYPES = {"text/plain", "text/markdown", "text/csv"}


def extract_text(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Extract text content from file bytes.

    For text files: decode as UTF-8.
    For PDF/DOCX/XLSX/PPTX: use markitdown.
    """
    if content_type in TEXT_TYPES or filename.endswith((".md", ".txt", ".csv")):
        return file_bytes.decode("utf-8")

    if content_type not in SUPPORTED_TYPES:
        ext = Path(filename).suffix
        if ext not in (".pdf", ".docx", ".xlsx", ".pptx"):
            raise ValueError(
                f"Tipo de arquivo nao suportado: {content_type} ({filename})"
            )

    # Lazy import to avoid loading heavy libs when not needed
    import tempfile

    from markitdown import MarkItDown

    md_converter = MarkItDown()
    with tempfile.NamedTemporaryFile(
        suffix=Path(filename).suffix, delete=False
    ) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        result = md_converter.convert(tmp.name)
    return result.text_content
