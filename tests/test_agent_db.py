"""Tests for Agno PostgresDb setup (agent_db module)."""
from unittest.mock import MagicMock, patch

from src.agents.agent_db import _convert_url, reset_agent_db


class TestConvertUrl:
    def test_asyncpg_to_psycopg(self):
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        assert _convert_url(url) == "postgresql+psycopg://user:pass@host:5432/db"

    def test_plain_postgresql_unchanged(self):
        url = "postgresql://user:pass@host:5432/db"
        assert _convert_url(url) == "postgresql://user:pass@host:5432/db"

    def test_already_psycopg_unchanged(self):
        url = "postgresql+psycopg://user:pass@host/db"
        assert _convert_url(url) == "postgresql+psycopg://user:pass@host/db"

    def test_preserves_query_params(self):
        url = "postgresql+asyncpg://u:p@h:5432/db?sslmode=require"
        result = _convert_url(url)
        assert result == "postgresql+psycopg://u:p@h:5432/db?sslmode=require"


class TestGetAgentDb:
    def setup_method(self):
        reset_agent_db()

    def teardown_method(self):
        reset_agent_db()

    @patch("src.agents.agent_db.PostgresDb", create=True)
    def test_returns_postgres_db_instance(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        with patch.dict("sys.modules", {"agno.storage.postgres": MagicMock(PostgresDb=mock_cls)}):
            from src.agents.agent_db import get_agent_db
            reset_agent_db()
            result = get_agent_db("postgresql+asyncpg://u:p@h/db")

        assert result is mock_instance

    @patch("src.agents.agent_db.PostgresDb", create=True)
    def test_singleton_returns_same_instance(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        with patch.dict("sys.modules", {"agno.storage.postgres": MagicMock(PostgresDb=mock_cls)}):
            from src.agents.agent_db import get_agent_db
            reset_agent_db()
            result1 = get_agent_db("postgresql+asyncpg://u:p@h/db")
            result2 = get_agent_db("postgresql+asyncpg://u:p@h/db")

        assert result1 is result2
        # Should only be constructed once
        assert mock_cls.call_count == 1

    def test_reset_clears_singleton(self):
        reset_agent_db()  # No error even when nothing to reset


class TestAgentCreatorsDbParam:
    """Verify all 4 agent creators accept db=None without errors."""

    @patch("src.agents.briefing_analyzer.Agent")
    @patch("src.agents.briefing_analyzer.OpenRouter")
    def test_briefing_agent_db_none(self, mock_or, mock_agent):
        from src.agents.briefing_analyzer import create_briefing_agent
        create_briefing_agent(api_key="k", model_id="m", db=None)
        kwargs = mock_agent.call_args[1]
        assert "storage" not in kwargs

    @patch("src.agents.briefing_analyzer.Agent")
    @patch("src.agents.briefing_analyzer.OpenRouter")
    def test_briefing_agent_db_provided(self, mock_or, mock_agent):
        from src.agents.briefing_analyzer import create_briefing_agent
        fake_db = MagicMock()
        create_briefing_agent(api_key="k", model_id="m", db=fake_db)
        kwargs = mock_agent.call_args[1]
        assert kwargs["storage"] is fake_db

    @patch("src.agents.content_reviewer.Agent")
    @patch("src.agents.content_reviewer.OpenRouter")
    def test_review_agent_db_none(self, mock_or, mock_agent):
        from src.agents.content_reviewer import create_review_agent
        create_review_agent(api_key="k", model_id="m", db=None)
        kwargs = mock_agent.call_args[1]
        assert "storage" not in kwargs

    @patch("src.agents.content_reviewer.Agent")
    @patch("src.agents.content_reviewer.OpenRouter")
    def test_review_agent_db_provided(self, mock_or, mock_agent):
        from src.agents.content_reviewer import create_review_agent
        fake_db = MagicMock()
        create_review_agent(api_key="k", model_id="m", db=fake_db)
        kwargs = mock_agent.call_args[1]
        assert kwargs["storage"] is fake_db

    @patch("src.agents.schedule_generator.Agent")
    @patch("src.agents.schedule_generator.OpenRouter")
    def test_schedule_agent_db_none(self, mock_or, mock_agent):
        from src.agents.schedule_generator import create_schedule_agent
        create_schedule_agent(api_key="k", model_id="m", db=None)
        kwargs = mock_agent.call_args[1]
        assert "storage" not in kwargs

    @patch("src.agents.schedule_generator.Agent")
    @patch("src.agents.schedule_generator.OpenRouter")
    def test_schedule_agent_db_provided(self, mock_or, mock_agent):
        from src.agents.schedule_generator import create_schedule_agent
        fake_db = MagicMock()
        create_schedule_agent(api_key="k", model_id="m", db=fake_db)
        kwargs = mock_agent.call_args[1]
        assert kwargs["storage"] is fake_db

    @patch("src.agents.summary_generator.Agent")
    @patch("src.agents.summary_generator.OpenRouter")
    def test_summary_agent_db_none(self, mock_or, mock_agent):
        from src.agents.summary_generator import create_summary_agent
        create_summary_agent(api_key="k", model_id="m", db=None)
        kwargs = mock_agent.call_args[1]
        assert "storage" not in kwargs

    @patch("src.agents.summary_generator.Agent")
    @patch("src.agents.summary_generator.OpenRouter")
    def test_summary_agent_db_provided(self, mock_or, mock_agent):
        from src.agents.summary_generator import create_summary_agent
        fake_db = MagicMock()
        create_summary_agent(api_key="k", model_id="m", db=fake_db)
        kwargs = mock_agent.call_args[1]
        assert kwargs["storage"] is fake_db
