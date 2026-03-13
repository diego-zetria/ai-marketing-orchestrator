import uuid

from sqlalchemy import inspect

from src.db.admin_models import (
    ActivityLog,
    AgentConfig,
    AssignmentRule,
    BrandGuideline,
    Client,
    NotificationRule,
    SystemConfig,
)
from src.db.models import TeamMember


class TestClientModel:
    def test_creation_with_required_fields(self):
        client = Client(name="client_alpha", display_name="ClientAlpha")
        assert client.name == "client_alpha"
        assert client.display_name == "ClientAlpha"

    def test_is_active_column_default(self):
        """Verify the column has a default of True (applied at flush/insert time)."""
        mapper = inspect(Client)
        col = mapper.columns["is_active"]
        assert col.default.arg is True

    def test_explicit_is_active(self):
        client = Client(name="test", display_name="Test", is_active=True)
        assert client.is_active is True
        client2 = Client(name="test2", display_name="Test 2", is_active=False)
        assert client2.is_active is False

    def test_uuid_generation(self):
        explicit_id = uuid.uuid4()
        client = Client(id=explicit_id, name="test", display_name="Test")
        assert client.id == explicit_id

    def test_nullable_foreign_keys(self):
        client = Client(name="test", display_name="Test")
        assert client.designer_id is None
        assert client.account_id is None
        assert client.clickup_list_id is None

    def test_table_in_marketing_bot_schema(self):
        assert Client.__table__.schema == "marketing_bot"


class TestAssignmentRuleModel:
    def test_creation_with_required_fields(self):
        rule = AssignmentRule(
            service_type="design",
            default_assignee_ids=["123"],
            tags=["design"],
        )
        assert rule.service_type == "design"
        assert rule.default_assignee_ids == ["123"]
        assert rule.tags == ["design"]

    def test_explicit_empty_lists(self):
        rule = AssignmentRule(
            service_type="copy",
            default_assignee_ids=[],
            tags=[],
        )
        assert rule.default_assignee_ids == []
        assert rule.tags == []

    def test_service_type_is_unique(self):
        mapper = inspect(AssignmentRule)
        col = mapper.columns["service_type"]
        assert col.unique is True


class TestNotificationRuleModel:
    def test_creation_with_required_fields(self):
        rule = NotificationRule(
            status="revisao",
            notify_roles=["strategy_reviewer"],
            message_template="precisa de revisao",
        )
        assert rule.status == "revisao"
        assert rule.notify_roles == ["strategy_reviewer"]
        assert rule.message_template == "precisa de revisao"

    def test_is_active_column_default(self):
        mapper = inspect(NotificationRule)
        col = mapper.columns["is_active"]
        assert col.default.arg is True

    def test_explicit_is_active(self):
        rule = NotificationRule(
            status="test",
            notify_roles=["admin"],
            message_template="test message",
            is_active=True,
        )
        assert rule.is_active is True


class TestAgentConfigModel:
    def test_creation_with_required_fields(self):
        config = AgentConfig(
            agent_name="briefing_analyzer",
            model_id="anthropic/claude-sonnet-4",
            instructions=["Analyze briefings", "Extract key info"],
        )
        assert config.agent_name == "briefing_analyzer"
        assert config.model_id == "anthropic/claude-sonnet-4"
        assert len(config.instructions) == 2

    def test_is_active_column_default(self):
        mapper = inspect(AgentConfig)
        col = mapper.columns["is_active"]
        assert col.default.arg is True

    def test_explicit_is_active(self):
        config = AgentConfig(
            agent_name="test",
            model_id="test-model",
            instructions=[],
            is_active=False,
        )
        assert config.is_active is False


class TestBrandGuidelineModel:
    def test_creation_with_required_fields(self):
        guideline = BrandGuideline(content="Use blue color palette")
        assert guideline.content == "Use blue color palette"

    def test_nullable_client_id(self):
        guideline = BrandGuideline(content="Global guidelines")
        assert guideline.client_id is None

    def test_with_client_id(self):
        client_id = uuid.uuid4()
        guideline = BrandGuideline(client_id=client_id, content="Client-specific")
        assert guideline.client_id == client_id


class TestSystemConfigModel:
    def test_key_as_primary_key(self):
        config = SystemConfig(
            key="daily_summary_hour",
            value={"hour": 8, "timezone": "America/Sao_Paulo"},
        )
        assert config.key == "daily_summary_hour"
        assert config.value["hour"] == 8

    def test_key_is_primary_key_column(self):
        mapper = inspect(SystemConfig)
        pk_cols = [col.name for col in mapper.primary_key]
        assert pk_cols == ["key"]

    def test_no_uuid_id_column(self):
        """SystemConfig uses key as PK, not a UUID id."""
        mapper = inspect(SystemConfig)
        col_names = [col.name for col in mapper.columns]
        assert "id" not in col_names

    def test_nullable_description(self):
        config = SystemConfig(key="test_key", value={"enabled": True})
        assert config.description is None

    def test_with_description(self):
        config = SystemConfig(
            key="test_key",
            value={"enabled": True},
            description="A test configuration",
        )
        assert config.description == "A test configuration"


class TestActivityLogModel:
    def test_creation_with_required_fields(self):
        log = ActivityLog(action="create_client")
        assert log.action == "create_client"

    def test_user_column_default_is_admin(self):
        """Verify the column has a default of 'admin' (applied at flush/insert time)."""
        mapper = inspect(ActivityLog)
        col = mapper.columns["user"]
        assert col.default.arg == "admin"

    def test_custom_user(self):
        log = ActivityLog(action="update_rule", user="luis_may")
        assert log.user == "luis_may"

    def test_nullable_fields(self):
        log = ActivityLog(action="test")
        assert log.entity_type is None
        assert log.entity_id is None
        assert log.details is None

    def test_with_entity_info(self):
        log = ActivityLog(
            action="update_client",
            entity_type="client",
            entity_id="client_alpha",
            details={"field": "designer_id", "old": None, "new": "uuid-123"},
        )
        assert log.entity_type == "client"
        assert log.entity_id == "client_alpha"
        assert log.details["field"] == "designer_id"

    def test_uuid_primary_key(self):
        explicit_id = uuid.uuid4()
        log = ActivityLog(id=explicit_id, action="test")
        assert log.id == explicit_id


class TestTeamMemberNewColumns:
    def test_role_column(self):
        member = TeamMember(name="Test User", role="designer")
        assert member.role == "designer"

    def test_role_nullable(self):
        member = TeamMember(name="Test User")
        assert member.role is None

    def test_telegram_chat_id_explicit(self):
        member = TeamMember(name="Test User", telegram_chat_id=ADMIN_TELEGRAM_ID)
        assert member.telegram_chat_id == ADMIN_TELEGRAM_ID

    def test_telegram_chat_id_column_default(self):
        mapper = inspect(TeamMember)
        col = mapper.columns["telegram_chat_id"]
        assert col.default.arg == 0

    def test_updated_at_column_exists(self):
        mapper = inspect(TeamMember)
        col_names = [col.name for col in mapper.columns]
        assert "updated_at" in col_names

    def test_updated_at_has_onupdate(self):
        mapper = inspect(TeamMember)
        col = mapper.columns["updated_at"]
        assert col.onupdate is not None

    def test_existing_active_field_unchanged(self):
        member = TeamMember(
            name="Existing Pattern",
            clickup_user_id="cu_999",
            active=True,
        )
        assert member.active is True
        assert member.name == "Existing Pattern"
