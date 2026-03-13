from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.report_generator import create_report_agent, generate_report
from src.agents.schemas import MonthlyReport


class TestCreateReportAgent:
    def test_creates_agent_with_correct_schema(self):
        agent = create_report_agent(api_key="test-key", model_id="test/model")
        assert agent.model is not None
        assert agent.output_schema == MonthlyReport

    def test_creates_agent_with_db(self):
        mock_db = MagicMock()
        agent = create_report_agent(api_key="test-key", model_id="test/model", db=mock_db)
        assert agent is not None


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_returns_monthly_report(self):
        mock_response = MagicMock()
        mock_response.content = MonthlyReport(
            period="Fevereiro 2026",
            client_name="ClientDelta",
            resumo_executivo="Mes produtivo.",
            total_tasks_created=20,
            total_tasks_completed=15,
            on_time_rate=0.8,
            tasks_by_status={"aprovado": 15},
            approval_metrics={
                "first_approval_rate": 0.6,
                "avg_review_days": 1.5,
                "total_alterations": 8,
                "total_assets_reviewed": 15,
            },
            time_per_status={"planejamento": 24.5},
            bottlenecks=["Gargalo"],
            recommendations=["Recomendacao"],
            highlights=["Destaque"],
        )

        mock_agent = AsyncMock()
        mock_agent.arun.return_value = mock_response

        result = await generate_report(mock_agent, "data text here")
        assert isinstance(result, MonthlyReport)
        assert result.client_name == "ClientDelta"
        mock_agent.arun.assert_called_once_with("data text here")

    @pytest.mark.asyncio
    async def test_raises_on_invalid_response(self):
        mock_response = MagicMock()
        mock_response.content = "not a MonthlyReport"

        mock_agent = AsyncMock()
        mock_agent.arun.return_value = mock_response

        with pytest.raises(ValueError, match="MonthlyReport"):
            await generate_report(mock_agent, "data text")
