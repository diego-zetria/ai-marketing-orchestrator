"""Tests for F5.3: ReportDataCollector — monthly metrics aggregation."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.monthly_report_job import ReportDataCollector


@pytest.fixture
def collector():
    clickup = AsyncMock()
    rules = MagicMock()
    session_factory = AsyncMock()
    return ReportDataCollector(
        clickup_client=clickup,
        rules_engine=rules,
        session_factory=session_factory,
        team_id="YOUR_CLICKUP_TEAM_ID",
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


class TestCollectClientData:
    @pytest.mark.asyncio
    async def test_computes_on_time_rate(self, collector):
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        future_ms = now_ms + 86400000  # tomorrow
        past_ms = now_ms - 86400000  # yesterday

        collector.clickup_client.get_filtered_team_tasks.return_value = [
            {
                "id": "t1",
                "due_date": str(future_ms),
                "date_done": str(now_ms),
                "status": {"status": "aprovado"},
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list1"},
            },
            {
                "id": "t2",
                "due_date": str(past_ms),
                "date_done": str(now_ms),
                "status": {"status": "aprovado"},
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list1"},
            },
        ]

        collector.rules_engine.get_client_by_list_id.return_value = "TestClient"

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        data = await collector.collect_client_data("TestClient", 2, 2026)
        # 1 on time out of 2 = 0.5
        assert data["on_time_rate"] == 0.5
        assert data["total_tasks_completed"] == 2

    @pytest.mark.asyncio
    async def test_zero_tasks_yields_zero_rate(self, collector):
        collector.clickup_client.get_filtered_team_tasks.return_value = []
        collector.rules_engine.get_client_by_list_id.return_value = "ClientDelta"

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        data = await collector.collect_client_data("ClientDelta", 2, 2026)
        assert data["on_time_rate"] == 0.0
        assert data["total_tasks_completed"] == 0
        assert data["tasks_by_status"] == {}

    @pytest.mark.asyncio
    async def test_filters_tasks_by_client(self, collector):
        """Tasks from other clients are excluded."""
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        collector.clickup_client.get_filtered_team_tasks.return_value = [
            {
                "id": "t1",
                "due_date": None,
                "date_done": str(now_ms),
                "status": {"status": "pronto"},
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list_client_delta"},
            },
            {
                "id": "t2",
                "due_date": None,
                "date_done": str(now_ms),
                "status": {"status": "pronto"},
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list_client_alpha"},
            },
        ]

        def get_client(list_id):
            return {"list_client_delta": "ClientDelta", "list_client_alpha": "ClientAlpha"}.get(list_id, "default")

        collector.rules_engine.get_client_by_list_id.side_effect = get_client

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        data = await collector.collect_client_data("ClientDelta", 2, 2026)
        assert data["total_tasks_completed"] == 1
        assert data["client_name"] == "ClientDelta"

    @pytest.mark.asyncio
    async def test_counts_tasks_by_status(self, collector):
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        collector.clickup_client.get_filtered_team_tasks.return_value = [
            {
                "id": f"t{i}",
                "due_date": None,
                "date_done": str(now_ms),
                "status": {"status": status},
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list1"},
            }
            for i, status in enumerate(["aprovado", "aprovado", "pronto"])
        ]

        collector.rules_engine.get_client_by_list_id.return_value = "TestClient"

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        data = await collector.collect_client_data("TestClient", 2, 2026)
        assert data["tasks_by_status"]["aprovado"] == 2
        assert data["tasks_by_status"]["pronto"] == 1

    @pytest.mark.asyncio
    async def test_tasks_without_due_date_not_counted_on_time(self, collector):
        """Tasks with no due_date should not be counted as on-time."""
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        collector.clickup_client.get_filtered_team_tasks.return_value = [
            {
                "id": "t1",
                "due_date": None,
                "date_done": str(now_ms),
                "status": {"status": "aprovado"},
                "assignees": [],
                "custom_fields": [],
                "list": {"id": "list1"},
            },
        ]

        collector.rules_engine.get_client_by_list_id.return_value = "TestClient"

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        data = await collector.collect_client_data("TestClient", 2, 2026)
        assert data["total_tasks_completed"] == 1
        assert data["on_time_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_db_error_gracefully_handled(self, collector):
        """DB failures should not crash the collector."""
        collector.clickup_client.get_filtered_team_tasks.return_value = []
        collector.rules_engine.get_client_by_list_id.return_value = "ClientDelta"

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=Exception("DB connection refused"),
        )
        mock_session.__aexit__ = AsyncMock(return_value=False)
        collector.session_factory.return_value = mock_session

        # Should not raise
        data = await collector.collect_client_data("ClientDelta", 2, 2026)
        assert data["time_per_status"] == {}
        assert data["approval_metrics"]["total_assets_reviewed"] == 0


class TestCollectAndFormat:
    @pytest.mark.asyncio
    async def test_formats_data_for_agent(self, collector):
        collector.clickup_client.get_filtered_team_tasks.return_value = []
        collector.rules_engine.get_client_by_list_id.return_value = "ClientDelta"

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        text = await collector.collect_and_format("ClientDelta", 2, 2026)
        assert "ClientDelta" in text
        assert "Fevereiro 2026" in text

    @pytest.mark.asyncio
    async def test_format_includes_sections(self, collector):
        collector.clickup_client.get_filtered_team_tasks.return_value = []
        collector.rules_engine.get_client_by_list_id.return_value = "TestClient"

        mock_session = _mock_db_session()
        collector.session_factory.return_value = mock_session

        text = await collector.collect_and_format("TestClient", 1, 2026)
        assert "RELATORIO MENSAL" in text
        assert "Janeiro 2026" in text
        assert "TASKS POR STATUS" in text
        assert "METRICAS DE APROVACAO" in text
        assert "TEMPO MEDIO POR STATUS" in text
        assert "Analise os dados" in text

    @pytest.mark.asyncio
    async def test_month_range_coverage(self, collector):
        """Verify _month_range_ms returns correct boundaries."""
        start_ms, end_ms = collector._month_range_ms(2, 2026)
        start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
        assert start_dt.day == 1
        assert start_dt.month == 2
        assert end_dt.day == 28  # 2026 is not a leap year
        assert end_dt.month == 2
