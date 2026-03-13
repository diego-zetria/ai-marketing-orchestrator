"""Tests for Models Catalog API schemas."""

from src.api.admin.models import ModelCreate, ModelResponse, ModelUpdate, SyncResponse


def test_model_create_schema():
    m = ModelCreate(
        model_id="anthropic/claude-sonnet-4.6",
        provider="Anthropic",
        display_name="Claude Sonnet 4.6",
        description_pt="Excelente equilibrio entre qualidade e custo",
        tier="recommended",
        speed_rating="fast",
        cost_rating="moderate",
    )
    assert m.model_id == "anthropic/claude-sonnet-4.6"
    assert m.quality_stars == 3
    assert m.best_for == []
    assert m.is_recommended is False
    assert m.display_order == 100


def test_model_create_with_all_fields():
    m = ModelCreate(
        model_id="test/model",
        provider="Test",
        display_name="Test Model",
        description_pt="Desc",
        tier="premium",
        quality_stars=5,
        speed_rating="slow",
        cost_rating="ultra",
        best_for=["Revisao", "Briefings"],
        recommended_agents=["content_reviewer"],
        is_recommended=True,
        display_order=1,
    )
    assert m.quality_stars == 5
    assert m.best_for == ["Revisao", "Briefings"]
    assert m.recommended_agents == ["content_reviewer"]


def test_model_update_partial():
    m = ModelUpdate(display_name="New Name", quality_stars=4)
    assert m.display_name == "New Name"
    assert m.quality_stars == 4
    assert m.tier is None
    assert m.is_active is None


def test_model_response_schema():
    m = ModelResponse(
        id="abc-123",
        model_id="test/model",
        provider="Test",
        display_name="Test",
        description_pt="Desc",
        tier="fast",
        quality_stars=3,
        speed_rating="fast",
        cost_rating="budget",
        best_for=[],
        context_length=128000,
        prompt_price_per_m=1.5,
        completion_price_per_m=6.0,
        supports_images=False,
        supports_tools=True,
        supports_audio=False,
        supports_video=False,
        input_modalities=["text"],
        recommended_agents=[],
        is_recommended=False,
        display_order=100,
        is_active=True,
        last_synced_at=None,
        updated_at="2026-02-22T00:00:00",
    )
    assert m.id == "abc-123"
    assert m.context_length == 128000
    assert m.supports_tools is True


def test_sync_response_schema():
    r = SyncResponse(synced=5, not_found=["old/model"], errors=[])
    assert r.synced == 5
    assert r.not_found == ["old/model"]


def test_model_create_tier_validation():
    """Valid tiers should work."""
    for tier in ["premium", "recommended", "fast", "specialist", "router"]:
        m = ModelCreate(
            model_id=f"test/{tier}",
            provider="Test",
            display_name="Test",
            description_pt="Test",
            tier=tier,
            speed_rating="fast",
            cost_rating="budget",
        )
        assert m.tier == tier
