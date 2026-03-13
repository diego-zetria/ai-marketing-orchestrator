"""Tests for the Performance Analyzer agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.performance_analyzer import (
    create_performance_analyzer,
    format_account_data,
    format_media_data,
    generate_performance_insight,
)
from src.agents.schemas import (
    AccountGrowth,
    FormatStats,
    PerformanceInsight,
    PostPerformance,
)


def test_create_performance_analyzer():
    agent = create_performance_analyzer(
        api_key="test-key",
        model_id="test/model",
    )
    assert agent.name == "performance_analyzer"


def test_create_performance_analyzer_custom_instructions():
    agent = create_performance_analyzer(
        api_key="test-key",
        model_id="test/model",
        instructions="Custom instructions here",
    )
    assert agent.name == "performance_analyzer"


def test_format_media_data_with_posts():
    posts = [
        {
            "caption": "Dica da semana #5 sobre cuidados com a pele",
            "media_type": "CAROUSEL_ALBUM",
            "published_at": "2026-03-03",
            "reach": 3200,
            "views": 5000,
            "likes": 200,
            "comments": 35,
            "saves": 47,
            "shares": 15,
            "total_interactions": 297,
        },
        {
            "caption": "Bastidores producao",
            "media_type": "VIDEO",
            "published_at": "2026-03-05",
            "reach": 2800,
            "views": 4500,
            "likes": 150,
            "comments": 20,
            "saves": 30,
            "shares": 10,
            "total_interactions": 210,
        },
    ]
    result = format_media_data(posts)
    assert "CAROUSEL_ALBUM" in result
    assert "VIDEO" in result
    assert "3200" in result
    assert "Total: 2 posts" in result


def test_format_media_data_empty():
    result = format_media_data([])
    assert "Nenhum dado de posts disponivel" in result


def test_format_media_data_engagement_rate_calculation():
    posts = [
        {
            "caption": "Test post",
            "media_type": "IMAGE",
            "published_at": "2026-03-01",
            "reach": 1000,
            "views": 1500,
            "likes": 50,
            "comments": 10,
            "saves": 5,
            "shares": 2,
            "total_interactions": 67,
        },
    ]
    result = format_media_data(posts)
    # 67 / 1000 * 100 = 6.7%
    assert "6.7%" in result


def test_format_media_data_zero_reach():
    posts = [
        {
            "caption": "Zero reach post",
            "media_type": "IMAGE",
            "published_at": "2026-03-01",
            "reach": 0,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "saves": 0,
            "shares": 0,
            "total_interactions": 0,
        },
    ]
    result = format_media_data(posts)
    assert "0.0%" in result


def test_format_account_data_with_entries():
    entries = [
        {"date": "2026-03-01", "reach": 1200, "views": 3000, "follower_count": 5000},
        {"date": "2026-03-02", "reach": 1350, "views": 3200, "follower_count": 5010},
    ]
    result = format_account_data(entries)
    assert "5000" in result
    assert "5010" in result
    assert "+10" in result


def test_format_account_data_empty():
    result = format_account_data([])
    assert "Nenhum dado de conta disponivel" in result


def test_format_account_data_single_entry():
    entries = [
        {"date": "2026-03-01", "reach": 1200, "views": 3000, "follower_count": 5000},
    ]
    result = format_account_data(entries)
    assert "5000" in result
    # Single entry should not show follower change
    assert "Seguidores:" not in result or "->" not in result


@pytest.mark.asyncio
async def test_generate_performance_insight_returns_schema():
    mock_insight = PerformanceInsight(
        client_name="ClientDelta",
        period="Ultimos 30 dias",
        resumo="Bom desempenho.",
        top_posts=[
            PostPerformance(
                caption_preview="Dica da semana",
                media_type="CAROUSEL_ALBUM",
                published_at="03/03/2026",
                reach=3200,
                engagement_rate=5.8,
                top_metric="saves",
            ),
        ],
        bottom_posts=[],
        format_analysis={
            "CAROUSEL_ALBUM": FormatStats(
                count=4, avg_reach=2500.0, avg_engagement_rate=4.9
            ),
        },
        trends=["Carrosseis geram mais alcance"],
        recommendations=["Mais carrosseis"],
        account_growth=AccountGrowth(
            followers_start=5000,
            followers_end=5142,
            followers_change=142,
            avg_daily_reach=1200.5,
        ),
    )
    mock_response = MagicMock()
    mock_response.content = mock_insight

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    result = await generate_performance_insight(
        agent=mock_agent,
        client_name="ClientDelta",
        period="Ultimos 30 dias",
        posts_data="2 posts com alcance medio de 3000",
        account_data="Seguidores: 5000 -> 5142",
    )

    assert isinstance(result, PerformanceInsight)
    assert result.client_name == "ClientDelta"
    mock_agent.arun.assert_called_once()


@pytest.mark.asyncio
async def test_generate_performance_insight_prompt_contains_context():
    mock_insight = PerformanceInsight(
        client_name="ClientAlpha",
        period="Fevereiro 2026",
        resumo="Resumo.",
        top_posts=[],
        bottom_posts=[],
        format_analysis={},
        trends=["t"],
        recommendations=["r"],
        account_growth=AccountGrowth(
            followers_start=3000,
            followers_end=3050,
            followers_change=50,
            avg_daily_reach=800.0,
        ),
    )
    mock_response = MagicMock()
    mock_response.content = mock_insight

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=mock_response)

    await generate_performance_insight(
        agent=mock_agent,
        client_name="ClientAlpha",
        period="Fevereiro 2026",
        posts_data="5 posts, 3 reels",
        account_data="Seguidores: 3000 -> 3050",
    )

    call_args = mock_agent.arun.call_args[0][0]
    assert "ClientAlpha" in call_args
    assert "Fevereiro 2026" in call_args
    assert "5 posts, 3 reels" in call_args
    assert "Seguidores: 3000" in call_args


@pytest.mark.asyncio
async def test_generate_performance_insight_retries_on_bad_response():
    mock_insight = PerformanceInsight(
        client_name="Test",
        period="Test",
        resumo="Test.",
        top_posts=[],
        bottom_posts=[],
        format_analysis={},
        trends=["t"],
        recommendations=["r"],
        account_growth=AccountGrowth(
            followers_start=100,
            followers_end=110,
            followers_change=10,
            avg_daily_reach=50.0,
        ),
    )
    bad_response = MagicMock()
    bad_response.content = "raw string instead of schema"
    good_response = MagicMock()
    good_response.content = mock_insight

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(side_effect=[bad_response, good_response])

    result = await generate_performance_insight(
        agent=mock_agent,
        client_name="Test",
        period="Test",
        posts_data="data",
        account_data="account",
    )

    assert isinstance(result, PerformanceInsight)
    assert mock_agent.arun.call_count == 2


@pytest.mark.asyncio
async def test_generate_performance_insight_raises_on_exhausted_retries():
    bad_response = MagicMock()
    bad_response.content = "raw string"

    mock_agent = MagicMock()
    mock_agent.arun = AsyncMock(return_value=bad_response)

    with pytest.raises(ValueError, match="resposta invalida"):
        await generate_performance_insight(
            agent=mock_agent,
            client_name="Test",
            period="Test",
            posts_data="data",
            account_data="account",
            max_retries=1,
        )

    assert mock_agent.arun.call_count == 2
