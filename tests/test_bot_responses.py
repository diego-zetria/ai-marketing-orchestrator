from src.agents.schemas import BriefingAnalysis, PostTask
from src.bot.responses import format_error_response, format_success_response


def test_format_success_response():
    analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="Loja Bella",
        social_network="instagram",
        month="fevereiro",
        year="2026",
        project_summary="Campanha de verao",
        posts=[
            PostTask(title="Post 1 - Verao", description="Arte", service_type="design+copy"),
            PostTask(title="Post 2 - Verao", description="Copy", service_type="copy"),
        ],
        urgency="urgent",
        observations="",
    )
    tasks_info = [
        {"title": "Post 1 - Verao", "assignees": ["@joao", "@maria"]},
        {"title": "Post 2 - Verao", "assignees": ["@maria"]},
    ]

    text = format_success_response(analysis, tasks_info)

    assert "Loja Bella" in text
    assert "Instagram - Loja Bella - Fevereiro 2026" in text
    assert "Post 1 - Verao" in text
    assert "Post 2 - Verao" in text
    assert "Urgente" in text


def test_format_success_response_with_observations():
    analysis = BriefingAnalysis(
        is_valid_briefing=True,
        client_name="Cliente Y",
        social_network="tiktok",
        month="marco",
        year="2026",
        project_summary="Videos curtos",
        posts=[PostTask(title="Video 1", description="Teste", service_type="design")],
        urgency="normal",
        observations="Briefing nao especifica duracao dos videos.",
    )
    tasks_info = [{"title": "Video 1", "assignees": []}]

    text = format_success_response(analysis, tasks_info)
    assert "duracao dos videos" in text


def test_format_error_response():
    text = format_error_response("Nao consegui analisar o briefing.")
    assert "Erro" in text
    assert "analisar" in text
