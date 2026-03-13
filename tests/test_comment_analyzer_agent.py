"""Tests for CommentAnalyzerAgent (Phase 6.2) and LLM fallback integration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.comment_analyzer import (
    CommentAnalysis,
    analyze_comment,
    create_comment_analyzer_agent,
)


class TestCreateCommentAnalyzerAgent:
    @patch("src.agents.comment_analyzer.Agent")
    @patch("src.agents.comment_analyzer.OpenRouter")
    def test_creates_agent_with_defaults(self, mock_or, mock_agent):
        create_comment_analyzer_agent(api_key="k", model_id="m")
        mock_agent.assert_called_once()
        kwargs = mock_agent.call_args[1]
        assert kwargs["name"] == "comment_analyzer"
        assert kwargs["markdown"] is False

    @patch("src.agents.comment_analyzer.Agent")
    @patch("src.agents.comment_analyzer.OpenRouter")
    def test_creates_agent_with_clickup_client(self, mock_or, mock_agent):
        mock_client = AsyncMock()
        create_comment_analyzer_agent(
            api_key="k", model_id="m", clickup_client=mock_client,
        )
        kwargs = mock_agent.call_args[1]
        assert len(kwargs["tools"]) == 1

    @patch("src.agents.comment_analyzer.Agent")
    @patch("src.agents.comment_analyzer.OpenRouter")
    def test_creates_agent_without_clickup_client(self, mock_or, mock_agent):
        create_comment_analyzer_agent(api_key="k", model_id="m")
        kwargs = mock_agent.call_args[1]
        assert kwargs["tools"] == []

    @patch("src.agents.comment_analyzer.Agent")
    @patch("src.agents.comment_analyzer.OpenRouter")
    def test_creates_agent_with_db(self, mock_or, mock_agent):
        fake_db = MagicMock()
        create_comment_analyzer_agent(
            api_key="k", model_id="m", db=fake_db,
        )
        kwargs = mock_agent.call_args[1]
        assert kwargs["storage"] is fake_db


class TestAnalyzeComment:
    @pytest.mark.asyncio
    async def test_no_intent_detected(self):
        """Agent responds with text, no tool call — no intent."""
        mock_agent = AsyncMock()
        mock_response = MagicMock()
        mock_response.is_paused = False
        mock_response.content = "SEM_INTENCAO"
        mock_agent.arun = AsyncMock(return_value=mock_response)

        result = await analyze_comment(
            agent=mock_agent,
            comment_text="Que legal o design!",
            user_role="account",
            current_status="em criacao",
            task_id="t1",
            task_name="Post ClientDelta",
        )
        assert result.has_intent is False
        assert "SEM_INTENCAO" in result.response_text

    @pytest.mark.asyncio
    async def test_intent_detected_paused(self):
        """Agent calls tool, run pauses — intent detected."""
        mock_agent = AsyncMock()

        mock_tool_exec = MagicMock()
        mock_tool_exec.tool_args = {
            "task_id": "t1",
            "new_status": "aprovado",
            "reason": "Reviewer said looks good",
        }

        mock_requirement = MagicMock()
        mock_requirement.tool_execution = mock_tool_exec

        mock_response = MagicMock()
        mock_response.is_paused = True
        mock_response.requirements = [mock_requirement]
        mock_agent.arun = AsyncMock(return_value=mock_response)

        result = await analyze_comment(
            agent=mock_agent,
            comment_text="Ficou otimo, pode publicar",
            user_role="strategy_reviewer",
            current_status="revisao",
            task_id="t1",
            task_name="Post ClientDelta",
        )
        assert result.has_intent is True
        assert result.run_output is mock_response

    @pytest.mark.asyncio
    async def test_prompt_includes_context(self):
        """Verify the prompt sent to the agent includes all context."""
        mock_agent = AsyncMock()
        mock_response = MagicMock()
        mock_response.is_paused = False
        mock_response.content = "SEM_INTENCAO"
        mock_agent.arun = AsyncMock(return_value=mock_response)

        await analyze_comment(
            agent=mock_agent,
            comment_text="esta show",
            user_role="designer",
            current_status="alteracao",
            task_id="t99",
            task_name="Post ClientAlpha",
        )
        prompt = mock_agent.arun.call_args[0][0]
        assert "esta show" in prompt
        assert "designer" in prompt
        assert "alteracao" in prompt
        assert "t99" in prompt
        assert "Post ClientAlpha" in prompt


class TestCommentAnalysis:
    def test_no_intent(self):
        a = CommentAnalysis(has_intent=False, response_text="nada")
        assert a.has_intent is False
        assert a.run_output is None
        assert a.response_text == "nada"

    def test_with_intent(self):
        mock_run = MagicMock()
        a = CommentAnalysis(has_intent=True, run_output=mock_run)
        assert a.has_intent is True
        assert a.run_output is mock_run


class TestCommentHandlerLLMFallback:
    @pytest.mark.asyncio
    async def test_llm_fallback_called_when_regex_misses(self):
        """When regex returns None and analyzer_agent is set, LLM is called."""
        from src.bot.comment_handler import CommentHandler

        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1",
            "name": "Post ClientDelta",
            "status": {"status": "revisao"},
        })

        mock_rules = MagicMock()
        mock_rules.get_user_role_by_clickup_id.return_value = "strategy_reviewer"
        mock_rules.get_user_name_by_clickup_id.return_value = "Luis"
        mock_rules.get_client_by_list_id.return_value = "client_delta"
        mock_rules.get_client_topic_id.return_value = None
        mock_rules.detect_intent.return_value = None

        mock_analyzer = AsyncMock()

        handler = CommentHandler(
            bot=mock_bot,
            rules_engine=mock_rules,
            clickup_client=mock_clickup,
            group_chat_id=123,
            comment_analyzer_agent=mock_analyzer,
        )

        # Comment that regex won't match but LLM might understand
        with patch(
            "src.agents.comment_analyzer.analyze_comment",
            new_callable=AsyncMock,
            return_value=CommentAnalysis(has_intent=False),
        ) as mock_analyze:
            await handler._detect_and_handle_intent(
                "t1", "ficou show demais", "96270997",
            )
            mock_analyze.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_fallback_when_no_analyzer(self):
        """Without analyzer_agent, no LLM fallback."""
        from src.bot.comment_handler import CommentHandler

        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1",
            "name": "Post",
            "status": {"status": "revisao"},
        })

        mock_rules = MagicMock()
        mock_rules.get_user_role_by_clickup_id.return_value = "strategy_reviewer"

        handler = CommentHandler(
            bot=mock_bot,
            rules_engine=mock_rules,
            clickup_client=mock_clickup,
            group_chat_id=123,
            comment_analyzer_agent=None,  # No LLM agent
        )

        with patch(
            "src.agents.comment_analyzer.analyze_comment",
            new_callable=AsyncMock,
        ) as mock_analyze:
            await handler._detect_and_handle_intent(
                "t1", "ambiguous comment", "96270997",
            )
            mock_analyze.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_llm_sends_confirm_buttons_on_intent(self):
        """When LLM detects intent (paused), confirm buttons are sent."""
        from src.bot.comment_handler import CommentHandler

        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1",
            "name": "Post ClientDelta",
            "status": {"status": "revisao"},
        })

        mock_rules = MagicMock()
        mock_rules.get_user_role_by_clickup_id.return_value = "strategy_reviewer"
        mock_rules.get_user_name_by_clickup_id.return_value = "Luis"
        mock_rules.detect_intent.return_value = None

        mock_tool_exec = MagicMock()
        mock_tool_exec.tool_args = {
            "task_id": "t1",
            "new_status": "aprovado",
            "reason": "Content looks great",
        }
        mock_req = MagicMock()
        mock_req.tool_execution = mock_tool_exec

        mock_run_output = MagicMock()
        mock_run_output.is_paused = True
        mock_run_output.requirements = [mock_req]

        analysis_with_intent = CommentAnalysis(
            has_intent=True, run_output=mock_run_output,
        )

        handler = CommentHandler(
            bot=mock_bot,
            rules_engine=mock_rules,
            clickup_client=mock_clickup,
            group_chat_id=123,
            comment_analyzer_agent=AsyncMock(),
        )

        with patch(
            "src.agents.comment_analyzer.analyze_comment",
            new_callable=AsyncMock,
            return_value=analysis_with_intent,
        ):
            await handler._detect_and_handle_intent(
                "t1", "pode publicar isso ai", "96270997",
            )

        mock_bot.send_message.assert_awaited_once()
        msg = mock_bot.send_message.call_args[1]["text"]
        assert "IA detectou" in msg
        assert "aprovado" in msg
        assert "Luis" in msg

    @pytest.mark.asyncio
    async def test_llm_error_doesnt_crash(self):
        """LLM analysis failure doesn't crash CommentHandler."""
        from src.bot.comment_handler import CommentHandler

        mock_bot = AsyncMock()
        mock_clickup = AsyncMock()
        mock_clickup.get_task = AsyncMock(return_value={
            "id": "t1",
            "name": "Post",
            "status": {"status": "revisao"},
        })

        mock_rules = MagicMock()
        mock_rules.get_user_role_by_clickup_id.return_value = "strategy_reviewer"
        mock_rules.detect_intent.return_value = None

        handler = CommentHandler(
            bot=mock_bot,
            rules_engine=mock_rules,
            clickup_client=mock_clickup,
            group_chat_id=123,
            comment_analyzer_agent=AsyncMock(),
        )

        with patch(
            "src.agents.comment_analyzer.analyze_comment",
            new_callable=AsyncMock,
            side_effect=Exception("LLM API error"),
        ):
            # Should not raise
            await handler._detect_and_handle_intent(
                "t1", "maybe approve", "96270997",
            )
        mock_bot.send_message.assert_not_awaited()
