import pytest

from src.integrations.extraction.text_extractor import extract_text


def test_extract_plain_text():
    content = b"Hello world, this is a plain text file."
    result = extract_text(content, "test.txt", "text/plain")
    assert result == "Hello world, this is a plain text file."


def test_extract_markdown():
    content = b"# Title\n\nSome **bold** text."
    result = extract_text(content, "test.md", "text/markdown")
    assert "# Title" in result
    assert "**bold**" in result


def test_extract_csv():
    content = b"name,value\nfoo,1\nbar,2"
    result = extract_text(content, "data.csv", "text/csv")
    assert "name,value" in result


def test_extract_unsupported_type():
    with pytest.raises(ValueError, match="Tipo de arquivo nao suportado"):
        extract_text(b"data", "test.xyz", "application/octet-stream")


def test_extract_text_by_extension():
    """Even with wrong content_type, .txt extension should work."""
    content = b"Text by extension detection"
    result = extract_text(content, "readme.txt", "application/octet-stream")
    assert result == "Text by extension detection"
