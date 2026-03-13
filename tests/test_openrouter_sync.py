"""Tests for OpenRouter sync service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.openrouter.sync import (
    SyncResult,
    _update_model_from_openrouter,
    fetch_openrouter_models,
)

# Sample OpenRouter API response for one model
SAMPLE_OR_MODEL = {
    "id": "anthropic/claude-sonnet-4.6",
    "name": "Anthropic: Claude Sonnet 4.6",
    "context_length": 200000,
    "pricing": {
        "prompt": "0.000003",
        "completion": "0.000015",
    },
    "architecture": {
        "modality": "text->text",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "tokenizer": "Claude",
    },
    "supported_parameters": ["max_tokens", "temperature", "tools", "top_p"],
}

SAMPLE_OR_MULTIMODAL = {
    "id": "google/gemini-3.1-pro-preview",
    "name": "Google: Gemini 3.1 Pro",
    "context_length": 1048576,
    "pricing": {
        "prompt": "0.000002",
        "completion": "0.000012",
    },
    "architecture": {
        "modality": "text+image+audio+video->text",
        "input_modalities": ["text", "image", "audio", "video"],
        "output_modalities": ["text"],
    },
    "supported_parameters": ["max_tokens", "temperature", "tools"],
}


def test_sync_result_defaults():
    r = SyncResult()
    assert r.synced == 0
    assert r.not_found == []
    assert r.errors == []


def test_update_model_pricing():
    """Verify pricing conversion: per-token -> per-million-tokens."""
    model = MagicMock()
    _update_model_from_openrouter(model, SAMPLE_OR_MODEL)
    assert model.prompt_price_per_m == 3.0  # 0.000003 * 1M
    assert model.completion_price_per_m == 15.0  # 0.000015 * 1M
    assert model.context_length == 200000


def test_update_model_modalities_text_only():
    model = MagicMock()
    _update_model_from_openrouter(model, SAMPLE_OR_MODEL)
    assert model.input_modalities == ["text"]
    assert model.supports_images is False
    assert model.supports_audio is False
    assert model.supports_video is False


def test_update_model_modalities_multimodal():
    model = MagicMock()
    _update_model_from_openrouter(model, SAMPLE_OR_MULTIMODAL)
    assert model.input_modalities == ["text", "image", "audio", "video"]
    assert model.supports_images is True
    assert model.supports_audio is True
    assert model.supports_video is True


def test_update_model_tools_support():
    model = MagicMock()
    _update_model_from_openrouter(model, SAMPLE_OR_MODEL)
    assert model.supports_tools is True

    no_tools = {**SAMPLE_OR_MODEL, "supported_parameters": ["max_tokens"]}
    _update_model_from_openrouter(model, no_tools)
    assert model.supports_tools is False


@pytest.mark.asyncio
async def test_fetch_openrouter_models():
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [SAMPLE_OR_MODEL]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.integrations.openrouter.sync.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_openrouter_models()
        assert len(result) == 1
        assert result[0]["id"] == "anthropic/claude-sonnet-4.6"
