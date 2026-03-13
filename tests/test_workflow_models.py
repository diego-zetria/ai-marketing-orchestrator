"""Tests for workflow_models.py: WorkflowDefinition, AutomationRule, TelegramTopic."""

import uuid

from sqlalchemy import inspect

from src.db.workflow_models import AutomationRule, TelegramTopic, WorkflowDefinition


class TestWorkflowDefinitionModel:
    def test_creation_with_required_fields(self):
        wf = WorkflowDefinition(
            name="default",
            display_name="Fluxo Padrao",
            statuses=["planejamento", "em criacao", "revisao", "aprovado"],
        )
        assert wf.name == "default"
        assert wf.display_name == "Fluxo Padrao"
        assert len(wf.statuses) == 4

    def test_transitions_jsonb(self):
        transitions = {
            "revisao": [
                {"to": "aprovado", "roles": ["strategy_reviewer"], "label": "Aprovar"},
            ],
        }
        wf = WorkflowDefinition(
            name="test",
            display_name="Test",
            statuses=["revisao", "aprovado"],
            transitions=transitions,
        )
        assert wf.transitions["revisao"][0]["to"] == "aprovado"
        assert wf.transitions["revisao"][0]["roles"] == ["strategy_reviewer"]

    def test_transition_actions_jsonb(self):
        actions = {"revisao->aprovado": {"notify": True}}
        wf = WorkflowDefinition(
            name="test",
            display_name="Test",
            statuses=["revisao", "aprovado"],
            transition_actions=actions,
        )
        assert wf.transition_actions["revisao->aprovado"]["notify"] is True

    def test_is_default_column_default(self):
        mapper = inspect(WorkflowDefinition)
        col = mapper.columns["is_default"]
        assert col.default.arg is False

    def test_is_active_column_default(self):
        mapper = inspect(WorkflowDefinition)
        col = mapper.columns["is_active"]
        assert col.default.arg is True

    def test_table_in_marketing_bot_schema(self):
        assert WorkflowDefinition.__table__.schema == "marketing_bot"

    def test_name_is_unique(self):
        mapper = inspect(WorkflowDefinition)
        col = mapper.columns["name"]
        assert col.unique is True

    def test_uuid_generation(self):
        explicit_id = uuid.uuid4()
        wf = WorkflowDefinition(
            id=explicit_id,
            name="test",
            display_name="Test",
            statuses=[],
        )
        assert wf.id == explicit_id


class TestAutomationRuleModel:
    def test_creation_with_required_fields(self):
        rule = AutomationRule(
            name="approval",
            display_name="Aprovacao",
            intent_type="approval",
            patterns=[r"\baprovado\b", r"\baprovo\b"],
            allowed_roles=["strategy_reviewer", "admin"],
            valid_from_statuses=["revisao"],
            target_status="aprovado",
        )
        assert rule.name == "approval"
        assert rule.intent_type == "approval"
        assert len(rule.patterns) == 2
        assert rule.target_status == "aprovado"

    def test_patterns_jsonb_serialization(self):
        patterns = [r"\baprovado\b", r"\bpor mim okk?\b"]
        rule = AutomationRule(
            name="test",
            display_name="Test",
            intent_type="test",
            patterns=patterns,
            allowed_roles=["admin"],
            valid_from_statuses=["revisao"],
        )
        assert rule.patterns == patterns
        assert rule.patterns[1] == r"\bpor mim okk?\b"

    def test_priority_default(self):
        mapper = inspect(AutomationRule)
        col = mapper.columns["priority"]
        assert col.default.arg == 100

    def test_mode_default(self):
        mapper = inspect(AutomationRule)
        col = mapper.columns["mode"]
        assert col.default.arg == "confirm"

    def test_special_action_nullable(self):
        rule = AutomationRule(
            name="test",
            display_name="Test",
            intent_type="test",
            patterns=[],
            allowed_roles=[],
            valid_from_statuses=[],
        )
        assert rule.special_action is None

    def test_with_special_action(self):
        rule = AutomationRule(
            name="client_approval",
            display_name="Aprovacao Cliente",
            intent_type="client_approval",
            patterns=[],
            allowed_roles=["account"],
            valid_from_statuses=["aprovado"],
            target_status="",
            special_action="client_approval",
        )
        assert rule.special_action == "client_approval"
        assert rule.target_status == ""

    def test_intent_type_indexed(self):
        mapper = inspect(AutomationRule)
        col = mapper.columns["intent_type"]
        assert col.index is True

    def test_priority_indexed(self):
        mapper = inspect(AutomationRule)
        col = mapper.columns["priority"]
        assert col.index is True

    def test_name_is_unique(self):
        mapper = inspect(AutomationRule)
        col = mapper.columns["name"]
        assert col.unique is True

    def test_table_in_marketing_bot_schema(self):
        assert AutomationRule.__table__.schema == "marketing_bot"


class TestTelegramTopicModel:
    def test_creation_with_required_fields(self):
        topic = TelegramTopic(
            name="client_alpha",
            label="ClientAlpha",
            topic_id=12345,
        )
        assert topic.name == "client_alpha"
        assert topic.label == "ClientAlpha"
        assert topic.topic_id == 12345

    def test_client_id_nullable(self):
        topic = TelegramTopic(name="geral", label="Geral", topic_id=0)
        assert topic.client_id is None

    def test_with_client_id(self):
        client_id = uuid.uuid4()
        topic = TelegramTopic(
            name="client_alpha",
            label="ClientAlpha",
            topic_id=12345,
            client_id=client_id,
        )
        assert topic.client_id == client_id

    def test_is_active_column_default(self):
        mapper = inspect(TelegramTopic)
        col = mapper.columns["is_active"]
        assert col.default.arg is True

    def test_name_is_unique(self):
        mapper = inspect(TelegramTopic)
        col = mapper.columns["name"]
        assert col.unique is True

    def test_client_id_indexed(self):
        mapper = inspect(TelegramTopic)
        col = mapper.columns["client_id"]
        assert col.index is True

    def test_table_in_marketing_bot_schema(self):
        assert TelegramTopic.__table__.schema == "marketing_bot"
