"""Tests for monthly report enrichment with Instagram metrics."""

from src.agents.schemas import ApprovalMetrics, InstagramMonthlyMetrics, MonthlyReport


def test_monthly_report_with_instagram_metrics():
    report = MonthlyReport(
        period="Marco 2026",
        client_name="ClientDelta",
        resumo_executivo="Bom mes.",
        total_tasks_created=16,
        total_tasks_completed=16,
        on_time_rate=0.94,
        tasks_by_status={"aprovado": 14, "pronto": 2},
        approval_metrics=ApprovalMetrics(
            first_approval_rate=0.75,
            avg_review_days=1.5,
            total_alterations=4,
            total_assets_reviewed=16,
        ),
        time_per_status={"em criacao": 24.5, "revisao": 8.0},
        bottlenecks=["Revisao lenta"],
        recommendations=["Mais carrosseis"],
        highlights=["16 posts no prazo"],
        instagram_metrics=InstagramMonthlyMetrics(
            total_posts_tracked=16,
            total_reach=45000,
            avg_engagement_rate=3.5,
            best_format="CAROUSEL_ALBUM",
            follower_change=142,
            top_post_caption="Dica da semana #5",
            top_post_reach=3200,
        ),
    )
    assert report.instagram_metrics is not None
    assert report.instagram_metrics.total_reach == 45000
    assert report.instagram_metrics.best_format == "CAROUSEL_ALBUM"


def test_monthly_report_without_instagram_metrics():
    report = MonthlyReport(
        period="Marco 2026",
        client_name="ClientAlpha",
        resumo_executivo="Mes normal.",
        total_tasks_created=10,
        total_tasks_completed=10,
        on_time_rate=0.8,
        tasks_by_status={"aprovado": 8, "pronto": 2},
        approval_metrics=ApprovalMetrics(
            first_approval_rate=0.6,
            avg_review_days=2.0,
            total_alterations=4,
            total_assets_reviewed=10,
        ),
        time_per_status={"em criacao": 30.0},
        bottlenecks=[],
        recommendations=[],
        highlights=[],
    )
    assert report.instagram_metrics is None
