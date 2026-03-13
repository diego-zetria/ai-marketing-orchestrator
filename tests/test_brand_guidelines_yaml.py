"""Tests for structured brand guidelines YAML loading (P7)."""
import yaml

from src.agents.content_reviewer import (
    _format_yaml_guidelines,
    _load_brand_guidelines,
    load_brand_config,
)


class TestLoadBrandConfig:
    def test_loads_client_delta_yaml(self):
        config = load_brand_config("client_delta")
        assert config["brand"] == "client_delta"
        assert "tone" in config
        assert "forbidden_words" in config
        assert isinstance(config["forbidden_words"], list)

    def test_loads_client_alpha_yaml(self):
        config = load_brand_config("client_alpha")
        assert config["brand"] == "client_alpha"
        assert "gratis" in config["forbidden_words"]

    def test_unknown_client_falls_back_to_default(self):
        config = load_brand_config("nonexistent_brand")
        assert config["brand"] == "default"

    def test_returns_empty_when_no_yaml(self, tmp_path):
        config = load_brand_config("nope", brands_dir=tmp_path)
        assert config == {}


class TestLoadBrandGuidelines:
    def test_yaml_takes_priority_over_md(self):
        """YAML file should be used even when .md exists."""
        text = _load_brand_guidelines("client_delta")
        # YAML formatted output should have structured sections
        assert "ClientDelta" in text
        assert "barato" in text.lower() or "proibid" in text.lower()

    def test_falls_back_to_md(self, tmp_path):
        """When no YAML exists, falls back to .md."""
        md = tmp_path / "test_client.md"
        md.write_text("# Test Brand\n- Be nice\n")
        text = _load_brand_guidelines("test_client", brands_dir=tmp_path)
        assert "Test Brand" in text

    def test_db_content_highest_priority(self):
        """db_content always wins over file-based loading."""
        text = _load_brand_guidelines(
            "client_delta", db_content="Custom DB guidelines",
        )
        assert text == "Custom DB guidelines"

    def test_default_yaml_fallback(self):
        text = _load_brand_guidelines("nonexistent_brand_xyz")
        assert "default" in text.lower() or "profissional" in text.lower()


class TestFormatYamlGuidelines:
    def test_formats_yaml_with_all_sections(self, tmp_path):
        data = {
            "brand": "test",
            "tone": "formal",
            "forbidden_words": ["bad", "worse"],
            "hashtags": {"required": ["#Test"], "suggested": ["#Nice"]},
            "color_palette": ["#000", "#FFF"],
            "required_elements": {
                "instagram": {"cta_required": True, "emoji_max": 2},
            },
            "guidelines": ["Be good", "Be better"],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = _format_yaml_guidelines(f)

        assert "TEST" in result
        assert "formal" in result
        assert "bad, worse" in result
        assert "#Test" in result
        assert "#Nice" in result
        assert "#000" in result
        assert "cta_required" in result
        assert "Be good" in result

    def test_handles_minimal_yaml(self, tmp_path):
        f = tmp_path / "minimal.yaml"
        f.write_text(yaml.dump({"brand": "minimal"}))
        result = _format_yaml_guidelines(f)
        assert "MINIMAL" in result


class TestBrandYamlStructure:
    """Validate that the actual YAML files have expected structure."""

    def test_client_delta_has_required_fields(self):
        config = load_brand_config("client_delta")
        assert "tone" in config
        assert "forbidden_words" in config
        assert "required_elements" in config
        assert "hashtags" in config
        assert "color_palette" in config
        assert "#ClientDelta" in config["hashtags"]["required"]

    def test_client_alpha_has_required_fields(self):
        config = load_brand_config("client_alpha")
        assert "tone" in config
        assert "forbidden_words" in config
        assert "#ClientAlpha" in config["hashtags"]["required"]

    def test_default_has_no_forbidden_words(self):
        config = load_brand_config("default")
        assert config["forbidden_words"] == []
