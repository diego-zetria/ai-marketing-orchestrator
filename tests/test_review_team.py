"""Tests for ReviewTeam (Phase 4.4) and combined review flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.schemas import (
    BrandComplianceResult,
    BrandViolation,
    CombinedReviewResult,
    ContentReview,
)


@pytest.fixture
def mock_quality_review():
    return ContentReview(
        checklist=["tom ok", "ortografia ok"],
        issues=["falta CTA"],
        suggestions=["adicionar link"],
        overall_score=7,
        summary="Bom conteudo, falta CTA.",
        approved=False,
    )


@pytest.fixture
def mock_quality_approved():
    return ContentReview(
        checklist=["tom ok"],
        issues=[],
        suggestions=[],
        overall_score=9,
        summary="Excelente.",
        approved=True,
    )


@pytest.fixture
def mock_compliance_pass():
    return BrandComplianceResult(
        violations=[],
        compliance_score=10,
        passed=True,
        summary="Conforme.",
    )


@pytest.fixture
def mock_compliance_fail():
    return BrandComplianceResult(
        violations=[
            BrandViolation(
                rule="forbidden_words",
                severity="critical",
                detail="Usou 'barato'",
            ),
        ],
        compliance_score=8,
        passed=False,
        summary="Violacao de marca.",
    )


class TestCombinedReviewResult:
    def test_overall_approved_both_pass(
        self, mock_quality_approved, mock_compliance_pass,
    ):
        result = CombinedReviewResult(
            quality=mock_quality_approved,
            compliance=mock_compliance_pass,
        )
        assert result.overall_approved is True

    def test_overall_not_approved_quality_fails(
        self, mock_quality_review, mock_compliance_pass,
    ):
        result = CombinedReviewResult(
            quality=mock_quality_review,
            compliance=mock_compliance_pass,
        )
        assert result.overall_approved is False

    def test_overall_not_approved_compliance_fails(
        self, mock_quality_approved, mock_compliance_fail,
    ):
        result = CombinedReviewResult(
            quality=mock_quality_approved,
            compliance=mock_compliance_fail,
        )
        assert result.overall_approved is False

    def test_combined_summary_includes_quality(
        self, mock_quality_approved, mock_compliance_pass,
    ):
        result = CombinedReviewResult(
            quality=mock_quality_approved,
            compliance=mock_compliance_pass,
        )
        assert "Excelente" in result.combined_summary

    def test_combined_summary_includes_compliance_on_fail(
        self, mock_quality_approved, mock_compliance_fail,
    ):
        result = CombinedReviewResult(
            quality=mock_quality_approved,
            compliance=mock_compliance_fail,
        )
        assert "Marca:" in result.combined_summary


class TestRunCombinedReview:
    @pytest.mark.asyncio
    async def test_runs_both_agents(
        self, mock_quality_review, mock_compliance_pass,
    ):
        from src.agents.review_team import run_combined_review

        mock_brand = AsyncMock()
        mock_brand.arun = AsyncMock(
            return_value=MagicMock(content=mock_compliance_pass),
        )
        mock_quality = AsyncMock()
        mock_quality.arun = AsyncMock(
            return_value=MagicMock(content=mock_quality_review),
        )

        with patch(
            "src.agents.review_team.check_brand_compliance",
            new_callable=AsyncMock,
            return_value=mock_compliance_pass,
        ), patch(
            "src.agents.review_team.review_content",
            new_callable=AsyncMock,
            return_value=mock_quality_review,
        ):
            result = await run_combined_review(
                brand_agent=mock_brand,
                quality_agent=mock_quality,
                task_name="Post Instagram",
                task_description="Content here",
                comments_text="comments",
                client_name="client_delta",
            )

        assert isinstance(result, CombinedReviewResult)
        assert result.quality.overall_score == 7
        assert result.compliance.passed is True

    @pytest.mark.asyncio
    async def test_combined_with_violations(
        self, mock_quality_approved, mock_compliance_fail,
    ):
        from src.agents.review_team import run_combined_review

        with patch(
            "src.agents.review_team.check_brand_compliance",
            new_callable=AsyncMock,
            return_value=mock_compliance_fail,
        ), patch(
            "src.agents.review_team.review_content",
            new_callable=AsyncMock,
            return_value=mock_quality_approved,
        ):
            result = await run_combined_review(
                brand_agent=AsyncMock(),
                quality_agent=AsyncMock(),
                task_name="Post",
                task_description="",
                comments_text="",
                client_name="client_delta",
            )

        assert result.overall_approved is False
        assert len(result.compliance.violations) == 1


class TestCreateReviewTeam:
    @patch("src.agents.review_team.Team")
    @patch("src.agents.review_team.create_brand_compliance_agent")
    @patch("src.agents.review_team.create_review_agent")
    @patch("src.agents.review_team.OpenRouter")
    def test_creates_team(self, mock_or, mock_qa, mock_brand, mock_team):
        from src.agents.review_team import create_review_team
        create_review_team(api_key="k", model_id="m")
        mock_team.assert_called_once()
        kwargs = mock_team.call_args[1]
        assert kwargs["name"] == "ReviewTeam"
        assert len(kwargs["members"]) == 2
        assert kwargs["share_member_interactions"] is True


class TestReviewHandlerWithBrandAgent:
    @pytest.mark.asyncio
    async def test_combined_review_message_includes_compliance(
        self, mock_quality_review, mock_compliance_fail,
    ):
        from src.bot.review_handler import ReviewHandler

        handler = ReviewHandler(
            review_agent=MagicMock(),
            clickup_client=AsyncMock(),
            rules_engine=MagicMock(),
            bot=AsyncMock(),
            group_chat_id=123,
            create_checklist=False,
            brand_agent=MagicMock(),
        )
        task = {"id": "t1", "name": "Post ClientDelta"}
        msg = handler._format_review_message(
            task, mock_quality_review, compliance=mock_compliance_fail,
        )
        assert "Conformidade da Marca" in msg
        assert "barato" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_brand_agent_skips_compliance(
        self, mock_quality_approved,
    ):
        from src.bot.review_handler import ReviewHandler

        handler = ReviewHandler(
            review_agent=MagicMock(),
            clickup_client=AsyncMock(),
            rules_engine=MagicMock(),
            bot=AsyncMock(),
            group_chat_id=123,
            create_checklist=False,
            brand_agent=None,
        )
        task = {"id": "t1", "name": "Post"}
        msg = handler._format_review_message(
            task, mock_quality_approved, compliance=None,
        )
        assert "Conformidade" not in msg
        assert "Aprovado" in msg
