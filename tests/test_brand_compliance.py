"""Tests for Brand Compliance agent (Phase 4.2)."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.agents.brand_compliance import (
    _format_rules_for_prompt,
    check_brand_compliance,
)
from src.agents.schemas import BrandComplianceResult, BrandViolation


class TestFormatRulesForPrompt:
    def test_formats_complete_config(self):
        config = {
            "tone": "formal",
            "forbidden_words": ["barato", "desconto"],
            "hashtags": {"required": ["#Brand"]},
            "required_elements": {
                "instagram": {"cta_required": True, "emoji_max": 2},
            },
            "color_palette": ["#000", "#FFF"],
        }
        result = _format_rules_for_prompt(config, platform="instagram")
        assert "formal" in result
        assert "barato" in result
        assert "#Brand" in result
        assert "cta_required" in result
        assert "#000" in result

    def test_formats_minimal_config(self):
        result = _format_rules_for_prompt({"tone": "casual"})
        assert "casual" in result

    def test_empty_config(self):
        result = _format_rules_for_prompt({})
        assert "Sem regras" in result

    def test_platform_specific_elements(self):
        config = {
            "required_elements": {
                "instagram": {"emoji_max": 2},
                "linkedin": {"emoji_max": 0},
            },
        }
        result = _format_rules_for_prompt(config, platform="linkedin")
        assert "emoji_max: 0" in result

    def test_platform_fallback_to_first(self):
        config = {
            "required_elements": {
                "instagram": {"emoji_max": 2},
            },
        }
        result = _format_rules_for_prompt(config, platform="tiktok")
        assert "emoji_max: 2" in result


class TestCheckBrandCompliance:
    @pytest.mark.asyncio
    async def test_returns_auto_pass_when_no_config(self):
        """When no YAML config exists, return auto-pass."""
        mock_agent = MagicMock()
        result = await check_brand_compliance(
            agent=mock_agent,
            task_name="Post",
            task_description="Content",
            comments_text="Text",
            client_name="nonexistent_client",
            brands_dir=Path("/tmp/empty_brands_dir_that_doesnt_exist"),
        )
        assert isinstance(result, BrandComplianceResult)
        assert result.passed is True
        assert result.compliance_score == 10

    @pytest.mark.asyncio
    async def test_calls_agent_with_config(self, tmp_path):
        """When YAML config exists, agent is called."""
        brands_dir = tmp_path / "brands"
        brands_dir.mkdir()
        (brands_dir / "testclient.yaml").write_text(yaml.dump({
            "brand": "testclient",
            "tone": "formal",
            "forbidden_words": ["bad"],
        }))

        mock_response = MagicMock()
        mock_response.content = BrandComplianceResult(
            violations=[],
            compliance_score=10,
            passed=True,
            summary="All good",
        )
        mock_agent = AsyncMock()
        mock_agent.arun = AsyncMock(return_value=mock_response)

        result = await check_brand_compliance(
            agent=mock_agent,
            task_name="Post",
            task_description="Nice content",
            comments_text="",
            client_name="testclient",
            brands_dir=brands_dir,
        )
        assert result.passed is True
        mock_agent.arun.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_violations(self, tmp_path):
        brands_dir = tmp_path / "brands"
        brands_dir.mkdir()
        (brands_dir / "testclient.yaml").write_text(yaml.dump({
            "brand": "testclient",
            "forbidden_words": ["bad"],
        }))

        violation = BrandViolation(
            rule="forbidden_words",
            severity="critical",
            detail="Palavra proibida 'bad' encontrada",
        )
        mock_response = MagicMock()
        mock_response.content = BrandComplianceResult(
            violations=[violation],
            compliance_score=8,
            passed=False,
            summary="Found forbidden word",
        )
        mock_agent = AsyncMock()
        mock_agent.arun = AsyncMock(return_value=mock_response)

        result = await check_brand_compliance(
            agent=mock_agent,
            task_name="Post",
            task_description="This is bad content",
            comments_text="",
            client_name="testclient",
            brands_dir=brands_dir,
        )
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].severity == "critical"


class TestCreateBrandComplianceAgent:
    @patch("src.agents.brand_compliance.Agent")
    @patch("src.agents.brand_compliance.OpenRouter")
    def test_creates_agent_with_defaults(self, mock_or, mock_agent):
        from src.agents.brand_compliance import create_brand_compliance_agent
        create_brand_compliance_agent(api_key="k", model_id="m")
        mock_agent.assert_called_once()
        kwargs = mock_agent.call_args[1]
        assert kwargs["name"] == "brand_compliance"
        assert "storage" not in kwargs

    @patch("src.agents.brand_compliance.Agent")
    @patch("src.agents.brand_compliance.OpenRouter")
    def test_creates_agent_with_db(self, mock_or, mock_agent):
        from src.agents.brand_compliance import create_brand_compliance_agent
        fake_db = MagicMock()
        create_brand_compliance_agent(api_key="k", model_id="m", db=fake_db)
        kwargs = mock_agent.call_args[1]
        assert kwargs["storage"] is fake_db


class TestBrandViolationSchema:
    def test_brand_violation_fields(self):
        v = BrandViolation(
            rule="forbidden_words",
            severity="critical",
            detail="Used 'barato'",
        )
        assert v.rule == "forbidden_words"
        assert v.severity == "critical"

    def test_brand_compliance_result_fields(self):
        r = BrandComplianceResult(
            violations=[],
            compliance_score=10,
            passed=True,
            summary="OK",
        )
        assert r.passed is True
        assert r.compliance_score == 10
