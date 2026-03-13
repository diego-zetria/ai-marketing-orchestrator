from src.db.admin_models import HomologatedModel


def test_homologated_model_required_fields():
    m = HomologatedModel(
        model_id="anthropic/claude-sonnet-4.6",
        provider="Anthropic",
        display_name="Claude Sonnet 4.6",
        description_pt="Modelo de teste",
        tier="recommended",
        speed_rating="fast",
        cost_rating="moderate",
    )
    assert m.model_id == "anthropic/claude-sonnet-4.6"
    assert m.provider == "Anthropic"
    assert m.tier == "recommended"


def test_homologated_model_defaults():
    m = HomologatedModel(
        model_id="test/model",
        provider="Test",
        display_name="Test",
        description_pt="Test",
        tier="fast",
        speed_rating="fast",
        cost_rating="budget",
    )
    assert m.quality_stars == 3
    assert m.is_active is True
    assert m.is_recommended is False
    assert m.display_order == 100
    assert m.supports_images is False
    assert m.supports_tools is False
    assert m.context_length == 0


def test_homologated_model_jsonb_fields():
    m = HomologatedModel(
        model_id="test/model2",
        provider="Test",
        display_name="Test",
        description_pt="Test",
        tier="premium",
        speed_rating="slow",
        cost_rating="premium",
        best_for=["Revisao", "Briefings"],
        recommended_agents=["content_reviewer"],
        input_modalities=["text", "image"],
    )
    assert m.best_for == ["Revisao", "Briefings"]
    assert m.recommended_agents == ["content_reviewer"]
    assert m.input_modalities == ["text", "image"]
