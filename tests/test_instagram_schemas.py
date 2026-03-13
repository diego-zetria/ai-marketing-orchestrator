"""Tests for Instagram analytics Pydantic schemas."""
from src.agents.schemas import (
    AccountGrowth,
    FormatStats,
    InstagramMonthlyMetrics,
    PerformanceInsight,
    PostPerformance,
)


def test_post_performance_schema():
    pp = PostPerformance(
        caption_preview="Dica da semana #5 sobre cuidados...",
        media_type="CAROUSEL_ALBUM",
        published_at="03/03/2026",
        reach=3200,
        engagement_rate=5.8,
        top_metric="saves",
    )
    assert pp.media_type == "CAROUSEL_ALBUM"
    assert pp.reach == 3200
    assert pp.engagement_rate == 5.8


def test_format_stats_schema():
    fs = FormatStats(
        count=4,
        avg_reach=2500.0,
        avg_engagement_rate=4.9,
    )
    assert fs.count == 4
    assert fs.avg_reach == 2500.0


def test_account_growth_schema():
    ag = AccountGrowth(
        followers_start=5000,
        followers_end=5142,
        followers_change=142,
        avg_daily_reach=1200.5,
    )
    assert ag.followers_change == 142
    assert ag.avg_daily_reach == 1200.5


def test_performance_insight_schema():
    insight = PerformanceInsight(
        client_name="ClientDelta",
        period="Ultimos 30 dias",
        resumo="Carrosseis educativos tiveram 2.3x mais alcance.",
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
            "CAROUSEL_ALBUM": FormatStats(count=4, avg_reach=2500.0, avg_engagement_rate=4.9),
        },
        trends=["Carrosseis educativos geram 2x mais alcance"],
        recommendations=["Aumentar frequencia de carrosseis"],
        account_growth=AccountGrowth(
            followers_start=5000,
            followers_end=5142,
            followers_change=142,
            avg_daily_reach=1200.5,
        ),
    )
    assert insight.client_name == "ClientDelta"
    assert len(insight.top_posts) == 1
    assert "CAROUSEL_ALBUM" in insight.format_analysis
    assert len(insight.trends) == 1
    assert len(insight.recommendations) == 1


def test_performance_insight_formatted_text():
    insight = PerformanceInsight(
        client_name="ClientAlpha",
        period="Fevereiro 2026",
        resumo="Bom desempenho geral.",
        top_posts=[
            PostPerformance(
                caption_preview="Post premium",
                media_type="IMAGE",
                published_at="15/02/2026",
                reach=1500,
                engagement_rate=3.2,
                top_metric="likes",
            ),
        ],
        bottom_posts=[],
        format_analysis={
            "IMAGE": FormatStats(count=5, avg_reach=1400.0, avg_engagement_rate=2.8),
        },
        trends=["Posts estaticos performam abaixo da media"],
        recommendations=["Testar Reels"],
        account_growth=AccountGrowth(
            followers_start=3000,
            followers_end=3050,
            followers_change=50,
            avg_daily_reach=800.0,
        ),
    )
    text = insight.formatted_text
    assert "ClientAlpha" in text
    assert "Post premium" in text
    assert "IMAGE" in text
    assert "50" in text


def test_instagram_monthly_metrics_schema():
    im = InstagramMonthlyMetrics(
        total_posts_tracked=16,
        total_reach=45000,
        avg_engagement_rate=3.5,
        best_format="CAROUSEL_ALBUM",
        follower_change=142,
        top_post_caption="Dica da semana #5",
        top_post_reach=3200,
    )
    assert im.total_posts_tracked == 16
    assert im.best_format == "CAROUSEL_ALBUM"
