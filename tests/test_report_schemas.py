from src.agents.schemas import ApprovalMetrics, MonthlyReport


class TestApprovalMetrics:
    def test_creates_with_valid_data(self):
        am = ApprovalMetrics(
            first_approval_rate=0.75,
            avg_review_days=1.5,
            total_alterations=3,
            total_assets_reviewed=12,
        )
        assert am.first_approval_rate == 0.75
        assert am.total_assets_reviewed == 12


class TestMonthlyReport:
    def test_creates_with_all_fields(self):
        report = MonthlyReport(
            period="Fevereiro 2026",
            client_name="ClientDelta",
            resumo_executivo="Mes produtivo com entregas no prazo.",
            total_tasks_created=20,
            total_tasks_completed=15,
            on_time_rate=0.8,
            tasks_by_status={"aprovado": 15, "em criacao": 3},
            approval_metrics=ApprovalMetrics(
                first_approval_rate=0.6,
                avg_review_days=1.5,
                total_alterations=8,
                total_assets_reviewed=15,
            ),
            time_per_status={"planejamento": 24.5, "em criacao": 48.0},
            bottlenecks=["Gargalo em revisao"],
            recommendations=["Reduzir ciclos"],
            highlights=["100% Instagram no prazo"],
        )
        assert report.client_name == "ClientDelta"
        assert report.on_time_rate == 0.8
        assert report.approval_metrics.first_approval_rate == 0.6

    def test_serializes_to_json(self):
        report = MonthlyReport(
            period="Marco 2026",
            client_name="ClientAlpha",
            resumo_executivo="Resumo teste.",
            total_tasks_created=10,
            total_tasks_completed=8,
            on_time_rate=0.75,
            tasks_by_status={"aprovado": 8},
            approval_metrics=ApprovalMetrics(
                first_approval_rate=0.5,
                avg_review_days=2.0,
                total_alterations=4,
                total_assets_reviewed=8,
            ),
            time_per_status={},
            bottlenecks=[],
            recommendations=[],
            highlights=[],
        )
        data = report.model_dump(mode="json")
        assert data["client_name"] == "ClientAlpha"
        assert isinstance(data["approval_metrics"], dict)
