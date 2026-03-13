from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.schemas import ContentReview

# === Task 1: ContentReview schema tests ===


def test_content_review_schema_valid():
    review = ContentReview(
        checklist=["tom de voz adequado", "ortografia ok"],
        issues=["falta CTA"],
        suggestions=["adicionar hashtags"],
        overall_score=7,
        summary="Conteudo bom, falta CTA.",
        approved=False,
    )
    assert review.overall_score == 7
    assert review.approved is False


def test_content_review_schema_fields():
    review = ContentReview(
        checklist=[],
        issues=[],
        suggestions=[],
        overall_score=10,
        summary="Perfeito.",
        approved=True,
    )
    assert review.checklist == []
    assert review.issues == []
    assert review.suggestions == []
    assert review.summary == "Perfeito."
    assert review.approved is True


# === Task 2: Content reviewer agent tests ===


def test_load_brand_guidelines_specific(tmp_path):
    from src.agents.content_reviewer import _load_brand_guidelines

    brand_file = tmp_path / "client_delta.md"
    brand_file.write_text("# ClientDelta Guidelines\n- Tom inovador")

    result = _load_brand_guidelines("client_delta", brands_dir=tmp_path)
    assert "ClientDelta Guidelines" in result
    assert "Tom inovador" in result


def test_load_brand_guidelines_fallback(tmp_path):
    from src.agents.content_reviewer import _load_brand_guidelines

    default_file = tmp_path / "default.md"
    default_file.write_text("# Default Guidelines\n- Tom profissional")

    result = _load_brand_guidelines("nonexistent_client", brands_dir=tmp_path)
    assert "Default Guidelines" in result


@pytest.mark.asyncio
async def test_review_content_calls_agent():
    from src.agents.content_reviewer import review_content
    from src.agents.schemas import ContentReview

    mock_review = ContentReview(
        checklist=["ortografia ok"],
        issues=[],
        suggestions=["mais emojis"],
        overall_score=8,
        summary="Bom conteudo.",
        approved=True,
    )
    mock_response = MagicMock()
    mock_response.content = mock_review

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await review_content(
        agent=mock_agent,
        task_name="Post Instagram ClientDelta",
        task_description="Campanha de verao",
        comments_text="Arte pronta, ver anexo",
        client_name="client_delta",
        brands_dir=None,
    )
    assert result.overall_score == 8
    assert result.approved is True
    mock_agent.arun.assert_called_once()
    prompt = mock_agent.arun.call_args[0][0]
    assert "Post Instagram ClientDelta" in prompt
    assert "Campanha de verao" in prompt


def test_create_review_agent_schema():
    from src.agents.content_reviewer import create_review_agent

    agent = create_review_agent(api_key="test-key", model_id="anthropic/claude-sonnet-4")
    assert agent is not None
    assert agent.name == "content_reviewer"
