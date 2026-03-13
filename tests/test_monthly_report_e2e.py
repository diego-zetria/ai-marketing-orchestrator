"""End-to-end test: data collection -> AI mock -> PDF generation -> delivery mock."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lambdas.report_generator.pdf_builder import build_client_pdf, build_internal_pdf
from src.agents.schemas import ApprovalMetrics, MonthlyReport
from src.bot.monthly_report_job import ReportDataCollector


@pytest.fixture
def mock_report():
    return MonthlyReport(
        period="Fevereiro 2026",
        client_name="ClientDelta",
        resumo_executivo=(
            "Fevereiro foi um mes produtivo para ClientDelta com 15 entregas concluidas. "
            "A taxa de entrega no prazo foi de 80%, acima da meta de 75%. "
            "Destaque para os posts de Instagram que tiveram 100% de pontualidade."
        ),
        total_tasks_created=20,
        total_tasks_completed=15,
        on_time_rate=0.8,
        tasks_by_status={"aprovado": 15, "em criacao": 3, "revisao": 2},
        approval_metrics=ApprovalMetrics(
            first_approval_rate=0.6,
            avg_review_days=1.5,
            total_alterations=8,
            total_assets_reviewed=15,
        ),
        time_per_status={
            "planejamento": 24.5,
            "em criacao": 48.0,
            "revisao": 12.0,
            "alteracao": 8.0,
        },
        bottlenecks=[
            "3 tasks em revisao ha mais de 5 dias",
            "Designer Pedro com 6 tasks simultaneas",
        ],
        recommendations=[
            "Reduzir ciclos de alteracao (media atual: 1.5 por entrega)",
            "Antecipar envio de briefings em 3 dias uteis",
            "Priorizar revisoes com mais de 48h pendentes",
        ],
        highlights=[
            "100% das entregas de Instagram no prazo",
            "Taxa de primeira aprovacao subiu 15% vs janeiro",
            "Tempo medio em criacao reduziu 20%",
        ],
    )


def _mock_db_session(fetchall_return=None, fetchone_return=None):
    """Create a mock async context manager that behaves like session_factory()."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = fetchall_return or []
    mock_result.fetchone.return_value = fetchone_return
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


class TestFullPipeline:
    def test_client_pdf_generates_valid_pdf(self, mock_report):
        pdf_bytes = build_client_pdf(mock_report)
        assert len(pdf_bytes) > 1000  # reasonable PDF size
        assert pdf_bytes[:5] == b"%PDF-"

    def test_internal_pdf_generates_valid_pdf(self, mock_report):
        pdf_bytes = build_internal_pdf(mock_report)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes[:5] == b"%PDF-"

    def test_both_pdfs_generate_without_error(self, mock_report):
        client_pdf = build_client_pdf(mock_report)
        internal_pdf = build_internal_pdf(mock_report)
        # Both should be valid non-empty PDFs
        assert len(client_pdf) > 0
        assert len(internal_pdf) > 0
        # Internal should be larger (has bottleneck page)
        assert len(internal_pdf) >= len(client_pdf)

    async def test_collector_formats_data(self):
        clickup = AsyncMock()
        clickup.get_filtered_team_tasks.return_value = [
            {
                "id": "t1",
                "status": {"status": "aprovado"},
                "due_date": "9999999999999",
                "date_done": "1000000000000",
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list1"},
            },
        ]

        rules = MagicMock()
        rules.get_client_by_list_id.return_value = "ClientDelta"

        mock_session = _mock_db_session()
        session_factory = MagicMock(return_value=mock_session)

        collector = ReportDataCollector(
            clickup_client=clickup,
            rules_engine=rules,
            session_factory=session_factory,
            team_id="123",
        )

        text = await collector.collect_and_format("ClientDelta", 2, 2026)
        assert "ClientDelta" in text
        assert "Fevereiro 2026" in text
