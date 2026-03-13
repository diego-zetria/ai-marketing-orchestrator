"""Tests for the Creative Director agent and schemas."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.creative_director import (
    create_creative_director,
    format_task_history,
    generate_creative_direction,
)
from src.agents.schemas import ContentTheme, CreativeDirection, SeasonalOpportunity


def test_content_theme_schema():
    theme = ContentTheme(
        name="Serie Educativa",
        description="Conteudo educativo sobre o segmento do cliente",
        pillar="educativo",
        subtopics=["Dica da semana", "Voce sabia?", "Mitos e verdades"],
        recommended_formats=["carrossel", "reels"],
        platforms=["instagram"],
        rationale="Carrosseis educativos geram 2x mais engajamento",
    )
    assert theme.name == "Serie Educativa"
    assert theme.pillar == "educativo"
    assert len(theme.subtopics) == 3
    assert "carrossel" in theme.recommended_formats


def test_seasonal_opportunity_schema():
    opp = SeasonalOpportunity(
        date="08/03",
        event="Dia Internacional da Mulher",
        suggestion="Post homenageando mulheres do segmento",
        format="carrossel",
        priority="alta",
    )
    assert opp.event == "Dia Internacional da Mulher"
    assert opp.priority == "alta"


def test_creative_direction_schema():
    direction = CreativeDirection(
        client_name="ClientAlpha",
        period="Marco 2026",
        resumo_estrategico="Foco em conteudo educativo e datas comemorativas.",
        themes=[
            ContentTheme(
                name="Serie Educativa",
                description="Conteudo educativo",
                pillar="educativo",
                subtopics=["Dica 1", "Dica 2"],
                recommended_formats=["carrossel"],
                platforms=["instagram"],
                rationale="Historico mostra alto engajamento",
            ),
        ],
        seasonal_opportunities=[
            SeasonalOpportunity(
                date="08/03",
                event="Dia da Mulher",
                suggestion="Post especial",
                format="post",
                priority="alta",
            ),
        ],
        format_mix={"carrossel": 4, "reels": 3, "post": 2},
        tone_guidance="Tom sofisticado e premium conforme guidelines",
        avoid=["Linguagem casual", "Descontos agressivos"],
    )
    assert direction.client_name == "ClientAlpha"
    assert len(direction.themes) == 1
    assert len(direction.seasonal_opportunities) == 1
    assert direction.format_mix["carrossel"] == 4
    assert len(direction.avoid) == 2


def test_creative_direction_formatted_text():
    direction = CreativeDirection(
        client_name="ClientDelta",
        period="Marco 2026",
        resumo_estrategico="Estrategia focada em reels.",
        themes=[
            ContentTheme(
                name="Behind the Scenes",
                description="Bastidores da producao",
                pillar="entretenimento",
                subtopics=["Dia a dia", "Equipe"],
                recommended_formats=["reels"],
                platforms=["instagram"],
                rationale="Reels curtos tem 3x mais alcance",
            ),
        ],
        seasonal_opportunities=[],
        format_mix={"reels": 5, "post": 3},
        tone_guidance="Tom jovem e dinamico",
        avoid=["Posts estaticos longos"],
    )
    text = direction.formatted_text
    assert "ClientDelta" in text
    assert "Behind the Scenes" in text
    assert "reels" in text.lower()


def test_create_creative_director():
    agent = create_creative_director(
        api_key="test-key",
        model_id="test/model",
    )
    assert agent.name == "creative_director"


def test_format_task_history_with_tasks():
    tasks = [
        {
            "name": "03/03 - POST Dica da semana",
            "status": {"status": "aprovado"},
            "description": "Post educativo",
        },
        {
            "name": "06/03 - CARROSSEL Produtos novos",
            "status": {"status": "aprovado"},
            "description": "Showcase",
        },
        {
            "name": "10/03 - REELS Bastidores",
            "status": {"status": "em criacao"},
            "description": "Behind the scenes",
        },
        {
            "name": "15/03 - POST Promocao",
            "status": {"status": "pronto"},
            "description": "Oferta especial",
        },
    ]
    result = format_task_history(tasks)
    assert "POST" in result
    assert "CARROSSEL" in result
    assert "REELS" in result
    assert "4 tasks" in result or "Total:" in result


def test_format_task_history_empty():
    result = format_task_history([])
    assert "Nenhum historico" in result or "sem historico" in result.lower()


@pytest.mark.asyncio
async def test_generate_creative_direction_returns_schema():
    mock_direction = CreativeDirection(
        client_name="ClientAlpha",
        period="Marco 2026",
        resumo_estrategico="Foco em conteudo premium.",
        themes=[
            ContentTheme(
                name="Premium Experience",
                description="Conteudo premium",
                pillar="inspiracional",
                subtopics=["Qualidade", "Exclusividade"],
                recommended_formats=["carrossel"],
                platforms=["instagram"],
                rationale="Alinhado com guidelines premium",
            ),
        ],
        seasonal_opportunities=[],
        format_mix={"carrossel": 4, "reels": 2},
        tone_guidance="Tom sofisticado",
        avoid=["Linguagem casual"],
    )
    mock_response = MagicMock()
    mock_response.content = mock_direction

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await generate_creative_direction(
        agent=mock_agent,
        client_name="ClientAlpha",
        social_network="instagram",
        month="marco",
        year="2026",
        brand_guidelines="Tom sofisticado e premium",
        task_history="3 posts aprovados, 1 carrossel, 2 reels",
        seasonal_data="08/03 - Dia da Mulher",
    )

    assert isinstance(result, CreativeDirection)
    assert result.client_name == "ClientAlpha"
    assert len(result.themes) == 1
    mock_agent.arun.assert_called_once()


@pytest.mark.asyncio
async def test_generate_creative_direction_prompt_contains_context():
    mock_direction = CreativeDirection(
        client_name="ClientDelta",
        period="Abril 2026",
        resumo_estrategico="Estrategia ClientDelta.",
        themes=[
            ContentTheme(
                name="T1", description="d", pillar="educativo",
                subtopics=["s"], recommended_formats=["post"],
                platforms=["instagram"], rationale="r",
            ),
        ],
        format_mix={"post": 3},
        tone_guidance="Tom amigavel",
        avoid=[],
    )
    mock_response = MagicMock()
    mock_response.content = mock_direction

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    await generate_creative_direction(
        agent=mock_agent,
        client_name="ClientDelta",
        social_network="instagram",
        month="abril",
        year="2026",
        brand_guidelines="Tom jovem e dinamico",
        task_history="5 posts, 3 reels",
        seasonal_data="07/04 - Dia da Saude",
    )

    call_args = mock_agent.arun.call_args[0][0]
    assert "ClientDelta" in call_args
    assert "instagram" in call_args
    assert "abril" in call_args
    assert "Tom jovem e dinamico" in call_args
    assert "5 posts, 3 reels" in call_args
    assert "Dia da Saude" in call_args


@pytest.mark.asyncio
async def test_generate_creative_direction_retries_on_bad_response():
    mock_direction = CreativeDirection(
        client_name="Test",
        period="Marco 2026",
        resumo_estrategico="Test.",
        themes=[
            ContentTheme(
                name="T", description="d", pillar="educativo",
                subtopics=["s"], recommended_formats=["post"],
                platforms=["instagram"], rationale="r",
            ),
        ],
        format_mix={"post": 3},
        tone_guidance="Tom neutro",
        avoid=[],
    )
    bad_response = MagicMock()
    bad_response.content = "raw string instead of schema"
    good_response = MagicMock()
    good_response.content = mock_direction

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(side_effect=[bad_response, good_response])

    result = await generate_creative_direction(
        agent=mock_agent,
        client_name="Test",
        social_network="instagram",
        month="marco",
        year="2026",
        brand_guidelines="guidelines",
        task_history="historico",
        seasonal_data="sazonal",
    )

    assert isinstance(result, CreativeDirection)
    assert mock_agent.arun.call_count == 2


@pytest.mark.asyncio
async def test_generate_creative_direction_raises_on_exhausted_retries():
    bad_response = MagicMock()
    bad_response.content = "raw string"

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=bad_response)

    with pytest.raises(ValueError, match="resposta invalida"):
        await generate_creative_direction(
            agent=mock_agent,
            client_name="Test",
            social_network="instagram",
            month="marco",
            year="2026",
            brand_guidelines="g",
            task_history="h",
            seasonal_data="s",
            max_retries=1,
        )

    assert mock_agent.arun.call_count == 2
