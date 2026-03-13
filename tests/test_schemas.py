from src.agents.schemas import BriefingAnalysis, PostTask


def test_post_task_creation():
    task = PostTask(
        title="Post 1 - Promocao Verao",
        description="Arte para Instagram sobre promocao de verao",
        service_type="design",
    )
    assert task.title == "Post 1 - Promocao Verao"
    assert task.service_type == "design"


def test_briefing_analysis_creation():
    analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="Loja Bella",
        social_network="instagram",
        month="fevereiro",
        year="2026",
        project_summary="Promocao de verao com 3 posts",
        posts=[
            PostTask(
                title="Post 1 - Promocao Verao",
                description="Arte promocional",
                service_type="design+copy",
            ),
        ],
        urgency="urgent",
        observations="",
    )
    assert analysis.client_name == "Loja Bella"
    assert len(analysis.posts) == 1
    assert analysis.urgency == "urgent"


def test_briefing_analysis_generates_card_title():
    analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="Loja Bella",
        social_network="instagram",
        month="fevereiro",
        year="2026",
        project_summary="Teste",
        posts=[],
        urgency="normal",
        observations="",
    )
    assert analysis.card_title == "Instagram - Loja Bella - Fevereiro 2026"


def test_card_title_capitalizes_properly():
    analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="loja bella",
        social_network="tiktok",
        month="marco",
        year="2026",
        project_summary="Teste",
        posts=[],
        urgency="normal",
        observations="",
    )
    assert analysis.card_title == "Tiktok - Loja Bella - Marco 2026"


def test_briefing_analysis_invalid_has_defaults():
    analysis = BriefingAnalysis(
        is_valid_briefing=False,
        rejection_message="Nao parece ser um briefing.",
    )
    assert analysis.is_valid_briefing is False
    assert analysis.rejection_message == "Nao parece ser um briefing."
    assert analysis.client_name == ""
    assert analysis.posts == []
    assert analysis.urgency == "normal"


def test_briefing_analysis_valid_requires_no_rejection():
    analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="ClientAlpha",
        social_network="instagram",
        month="marco",
        year="2026",
        project_summary="Test",
        posts=[PostTask(title="P1", description="D", service_type="design")],
    )
    assert analysis.is_valid_briefing is True
    assert analysis.rejection_message == ""
