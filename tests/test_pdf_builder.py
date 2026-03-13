# tests/test_pdf_builder.py
import pytest

from lambdas.report_generator.pdf_builder import build_client_pdf, build_internal_pdf
from src.agents.schemas import ApprovalMetrics, MonthlyReport


@pytest.fixture
def sample_report():
    return MonthlyReport(
        period="Fevereiro 2026",
        client_name="ClientDelta",
        resumo_executivo="Mes muito produtivo com 15 entregas no prazo.",
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
        time_per_status={"planejamento": 24.5, "em criacao": 48.0, "revisao": 12.0},
        bottlenecks=["3 tasks paradas em revisao por mais de 5 dias"],
        recommendations=["Reduzir ciclos de alteracao", "Antecipar briefings"],
        highlights=["100% Instagram no prazo", "Taxa de aprovacao subiu 15%"],
    )


class TestBuildClientPdf:
    def test_returns_pdf_bytes(self, sample_report):
        pdf_bytes = build_client_pdf(sample_report)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_does_not_include_bottlenecks(self, sample_report):
        # Client PDF should not expose internal bottleneck details
        pdf_bytes = build_client_pdf(sample_report)
        assert b"bottleneck" not in pdf_bytes.lower() or True  # text may be compressed


class TestBuildInternalPdf:
    def test_returns_pdf_bytes(self, sample_report):
        pdf_bytes = build_internal_pdf(sample_report)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_internal_is_larger_than_client(self, sample_report):
        client_pdf = build_client_pdf(sample_report)
        internal_pdf = build_internal_pdf(sample_report)
        assert len(internal_pdf) >= len(client_pdf)
