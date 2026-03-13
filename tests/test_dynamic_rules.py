"""Tests for DynamicRulesEngine -- no real database required.

All tests manipulate internal state directly after construction,
verifying the synchronous public interface without DB fixtures.
"""

from __future__ import annotations

import re

from src.bot.comment_patterns import CommentIntent, detect_intent_dynamic
from src.engine.dynamic_rules import DynamicRulesEngine

# ---------------------------------------------------------------------------
# Helpers: build an engine with pre-populated state
# ---------------------------------------------------------------------------


def _make_engine(
    *,
    automation_rules: list[dict] | None = None,
    workflows: dict[str, dict] | None = None,
    default_workflow: str = "",
    team_mapping: dict[str, dict] | None = None,
    topics: dict[str, dict] | None = None,
    client_overrides: dict[str, dict] | None = None,
) -> DynamicRulesEngine:
    engine = DynamicRulesEngine()

    if automation_rules is not None:
        engine._automation_rules_list = automation_rules
        engine._compiled_patterns = {}
        for rule in automation_rules:
            compiled = []
            for p in rule.get("patterns", []):
                try:
                    compiled.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    pass
            engine._compiled_patterns[rule["name"]] = compiled

    if workflows is not None:
        engine._workflows = workflows
    if default_workflow:
        engine._default_workflow_name = default_workflow
    if team_mapping is not None:
        engine._team_mapping = team_mapping
    if topics is not None:
        engine._telegram_topics_map = topics
    if client_overrides is not None:
        engine._client_overrides = client_overrides

    engine._loaded = True
    return engine


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

APPROVAL_RULE = {
    "name": "approval",
    "intent_type": "approval",
    "patterns": [r"\baprovado\b", r"\baprovo\b"],
    "allowed_roles": {"strategy_reviewer", "content_reviewer", "admin"},
    "valid_from_statuses": {"revisao"},
    "target_status": "aprovado",
    "mode": "confirm",
    "special_action": None,
    "priority": 10,
}

DELIVERY_RULE = {
    "name": "delivery",
    "intent_type": "delivery",
    "patterns": [r"\bfinalizado\b", r"\bsegue para aprova[cç][aã]o\b"],
    "allowed_roles": {"designer", "admin"},
    "valid_from_statuses": {"em criacao", "alteracao"},
    "target_status": "revisao",
    "mode": "confirm",
    "special_action": None,
    "priority": 20,
}

CLIENT_APPROVAL_RULE = {
    "name": "client_approval",
    "intent_type": "client_approval",
    "patterns": [r"\benviar para (?:o )?cliente\b"],
    "allowed_roles": {"account", "admin"},
    "valid_from_statuses": {"aprovado"},
    "target_status": "",
    "mode": "confirm",
    "special_action": "trigger_approval_email",
    "priority": 5,
}

DEFAULT_WORKFLOW = {
    "display_name": "Padrao Agency",
    "description": "Default agency workflow",
    "statuses": [
        "ativar", "planejamento", "desenvolvimento", "em criacao",
        "revisao", "alteracao", "aprovado", "pronto",
    ],
    "transitions": {
        "em criacao": [
            {"to": "revisao", "roles": ["designer"]},
        ],
        "revisao": [
            {"to": "aprovado", "roles": ["strategy_reviewer", "content_reviewer"]},
            {"to": "alteracao", "roles": ["strategy_reviewer", "content_reviewer"]},
        ],
        "alteracao": [
            {"to": "revisao", "roles": ["designer"]},
        ],
    },
    "transition_actions": {},
    "is_default": True,
}

CUSTOM_WORKFLOW = {
    "display_name": "Custom Client",
    "description": "Workflow for specific client",
    "statuses": ["draft", "review", "done"],
    "transitions": {
        "draft": [{"to": "review", "roles": []}],
        "review": [{"to": "done", "roles": ["admin"]}],
    },
    "transition_actions": {},
    "is_default": False,
}


# ---------------------------------------------------------------------------
# Intent detection tests
# ---------------------------------------------------------------------------


class TestDetectIntentFromDb:
    def test_detect_intent_from_db(self):
        """Patterns from internal state match correctly."""
        engine = _make_engine(
            automation_rules=[APPROVAL_RULE, DELIVERY_RULE],
        )
        result = engine.detect_intent("aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"
        assert result.target_status == "aprovado"
        assert result.matched_pattern == "aprovado"
        assert result.confidence == 1.0

    def test_detect_intent_priority_order(self):
        """Lower priority number wins (first in list after ordering by priority)."""
        low_priority_rule = {
            **APPROVAL_RULE,
            "name": "approval_low",
            "priority": 10,
            "target_status": "aprovado",
        }
        high_priority_rule = {
            "name": "approval_high",
            "intent_type": "fast_approval",
            "patterns": [r"\baprovado\b"],
            "allowed_roles": {"strategy_reviewer", "admin"},
            "valid_from_statuses": {"revisao"},
            "target_status": "pronto",
            "mode": "auto",
            "special_action": None,
            "priority": 1,
        }
        engine = _make_engine(
            automation_rules=[high_priority_rule, low_priority_rule],
        )
        result = engine.detect_intent("aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "fast_approval"
        assert result.target_status == "pronto"

    def test_detect_intent_role_validation(self):
        """Disallowed role returns None for that rule."""
        engine = _make_engine(
            automation_rules=[APPROVAL_RULE],
        )
        result = engine.detect_intent("aprovado", "designer", "revisao")
        assert result is None

    def test_detect_intent_status_validation(self):
        """Invalid current status returns None."""
        engine = _make_engine(
            automation_rules=[APPROVAL_RULE],
        )
        result = engine.detect_intent("aprovado", "strategy_reviewer", "desenvolvimento")
        assert result is None

    def test_detect_intent_empty_text_returns_none(self):
        engine = _make_engine(automation_rules=[APPROVAL_RULE])
        assert engine.detect_intent("", "strategy_reviewer", "revisao") is None
        assert engine.detect_intent("   ", "strategy_reviewer", "revisao") is None

    def test_detect_intent_none_role_skips_role_check(self):
        """When user_role is None, role validation is skipped (lenient)."""
        engine = _make_engine(automation_rules=[APPROVAL_RULE])
        result = engine.detect_intent("aprovado", None, "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_detect_intent_none_status_skips_status_check(self):
        """When current_status is None, status validation is skipped (lenient)."""
        engine = _make_engine(automation_rules=[APPROVAL_RULE])
        result = engine.detect_intent("aprovado", "strategy_reviewer", None)
        assert result is not None

    def test_detect_intent_no_matching_pattern(self):
        engine = _make_engine(automation_rules=[APPROVAL_RULE])
        result = engine.detect_intent("boa tarde, como vai?", "strategy_reviewer", "revisao")
        assert result is None

    def test_detect_intent_skips_invalid_regex(self):
        """Invalid regex patterns are skipped during compilation."""
        rule_with_bad_pattern = {
            **APPROVAL_RULE,
            "name": "bad_regex_rule",
            "patterns": [r"[invalid(", r"\baprovado\b"],
        }
        engine = _make_engine(automation_rules=[rule_with_bad_pattern])
        result = engine.detect_intent("aprovado", "strategy_reviewer", "revisao")
        assert result is not None


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------


class TestWorkflows:
    def test_is_valid_transition_valid(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW},
            default_workflow="default",
        )
        assert engine.is_valid_transition("em criacao", "revisao", "designer") is True

    def test_is_valid_transition_invalid(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW},
            default_workflow="default",
        )
        assert engine.is_valid_transition("revisao", "aprovado", "account") is False

    def test_is_valid_transition_no_workflow(self):
        engine = _make_engine()
        assert engine.is_valid_transition("em criacao", "revisao", "designer") is False

    def test_is_valid_transition_no_role_restriction(self):
        engine = _make_engine(
            workflows={"custom": CUSTOM_WORKFLOW},
            default_workflow="custom",
        )
        assert engine.is_valid_transition("draft", "review", "anyone") is True

    def test_get_workflow_default(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW},
            default_workflow="default",
        )
        wf = engine.get_workflow()
        assert wf is not None
        assert wf["display_name"] == "Padrao Agency"

    def test_get_workflow_by_name(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW, "custom": CUSTOM_WORKFLOW},
            default_workflow="default",
        )
        wf = engine.get_workflow("custom")
        assert wf is not None
        assert wf["display_name"] == "Custom Client"

    def test_get_workflow_none_when_missing(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW},
            default_workflow="default",
        )
        assert engine.get_workflow("nonexistent") is None

    def test_get_workflow_none_when_no_default(self):
        engine = _make_engine(workflows={"custom": CUSTOM_WORKFLOW})
        assert engine.get_workflow() is None

    def test_get_client_workflow_fallback(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW},
            default_workflow="default",
            client_overrides={"client_alpha": {"list_id": "list_client_alpha"}},
        )
        wf = engine.get_client_workflow("client_alpha")
        assert wf is not None
        assert wf["display_name"] == "Padrao Agency"

    def test_get_client_workflow_with_override(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW, "custom": CUSTOM_WORKFLOW},
            default_workflow="default",
            client_overrides={"special_client": {"list_id": "x", "workflow_name": "custom"}},
        )
        wf = engine.get_client_workflow("special_client")
        assert wf is not None
        assert wf["display_name"] == "Custom Client"

    def test_get_all_statuses(self):
        engine = _make_engine(
            workflows={"default": DEFAULT_WORKFLOW},
            default_workflow="default",
        )
        statuses = engine.get_all_statuses()
        assert statuses == [
            "ativar", "planejamento", "desenvolvimento", "em criacao",
            "revisao", "alteracao", "aprovado", "pronto",
        ]

    def test_get_all_statuses_empty(self):
        engine = _make_engine()
        assert engine.get_all_statuses() == []


# ---------------------------------------------------------------------------
# Topic methods
# ---------------------------------------------------------------------------


class TestTopics:
    def test_get_client_topic_id_from_db(self):
        engine = _make_engine(
            topics={"client_alpha": {"topic_id": 12345, "label": "ClientAlpha", "client_id": None}},
        )
        assert engine.get_client_topic_id("client_alpha") == 12345

    def test_get_client_topic_id_zero_returns_none(self):
        engine = _make_engine(
            topics={"client_alpha": {"topic_id": 0, "label": "ClientAlpha", "client_id": None}},
        )
        assert engine.get_client_topic_id("client_alpha") is None

    def test_get_topic_id_missing_returns_none(self):
        engine = _make_engine(topics={})
        assert engine.get_topic_id("nonexistent") is None

    def test_get_topic_id_existing(self):
        engine = _make_engine(
            topics={"geral": {"topic_id": 99999, "label": "Geral", "client_id": None}},
        )
        assert engine.get_topic_id("geral") == 99999


# ---------------------------------------------------------------------------
# Auto-status config reconstruction
# ---------------------------------------------------------------------------


class TestAutoStatusConfig:
    def test_get_auto_status_config_from_rules(self):
        engine = _make_engine(
            automation_rules=[APPROVAL_RULE, DELIVERY_RULE, CLIENT_APPROVAL_RULE],
        )
        config = engine.get_auto_status_config()
        assert "approval" in config
        assert config["approval"]["target_status"] == "aprovado"
        assert "strategy_reviewer" in config["approval"]["allowed_roles"]
        assert "delivery" in config
        assert config["delivery"]["target_status"] == "revisao"
        assert "client_approval" in config

    def test_get_auto_status_config_empty(self):
        engine = _make_engine(automation_rules=[])
        assert engine.get_auto_status_config() == {}


# ---------------------------------------------------------------------------
# User lookup methods
# ---------------------------------------------------------------------------


class TestUserLookup:
    def test_get_user_role_by_clickup_id(self):
        engine = _make_engine(
            team_mapping={"123": {"name": "Test User", "role": "admin", "telegram_chat_id": 111}},
        )
        assert engine.get_user_role_by_clickup_id("123") == "admin"

    def test_get_user_role_missing(self):
        engine = _make_engine(team_mapping={})
        assert engine.get_user_role_by_clickup_id("999") is None

    def test_get_user_name_by_clickup_id(self):
        engine = _make_engine(
            team_mapping={"456": {"name": "Maria", "role": "account", "telegram_chat_id": 222}},
        )
        assert engine.get_user_name_by_clickup_id("456") == "Maria"

    def test_get_user_name_missing(self):
        engine = _make_engine(team_mapping={})
        assert engine.get_user_name_by_clickup_id("999") is None

    def test_get_user_role_coerces_to_string(self):
        engine = _make_engine(
            team_mapping={"789": {"name": "Pedro", "role": "designer", "telegram_chat_id": 333}},
        )
        assert engine.get_user_role_by_clickup_id("789") == "designer"


# ---------------------------------------------------------------------------
# detect_intent_dynamic wrapper (from comment_patterns)
# ---------------------------------------------------------------------------


class TestDetectIntentDynamic:
    def test_fallback_when_engine_has_no_detect_intent(self):
        class FakeEngine:
            pass

        result = detect_intent_dynamic(FakeEngine(), "aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_fallback_when_engine_returns_none(self):
        class FakeEngine:
            def detect_intent(self, text, role, status):
                return None

        result = detect_intent_dynamic(FakeEngine(), "aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_uses_engine_result_when_available(self):
        custom_intent = CommentIntent(
            intent_type="custom_intent",
            target_status="custom_status",
            matched_pattern="custom",
            confidence=0.9,
        )

        class FakeEngine:
            def detect_intent(self, text, role, status):
                return custom_intent

        result = detect_intent_dynamic(FakeEngine(), "any text", "any_role", "any_status")
        assert result is custom_intent

    def test_fallback_when_engine_is_none(self):
        result = detect_intent_dynamic(None, "finalizado", "designer", "em criacao")
        assert result is not None
        assert result.intent_type == "delivery"

    def test_dynamic_with_real_engine_populated(self):
        engine = _make_engine(automation_rules=[APPROVAL_RULE])
        result = detect_intent_dynamic(engine, "aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_dynamic_engine_no_match_falls_back(self):
        engine = _make_engine(automation_rules=[DELIVERY_RULE])
        result = detect_intent_dynamic(engine, "aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"
