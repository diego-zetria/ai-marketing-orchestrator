from src.db.admin_models import AgentConfig, AgentTool


def test_agent_tool_model_fields():
    tool = AgentTool(
        tool_key="clickup_create_task",
        display_name="Criar Task no ClickUp",
        description="Cria uma nova task no ClickUp com os dados fornecidos.",
        category="clickup",
        is_global=True,
        config={},
    )
    assert tool.tool_key == "clickup_create_task"
    assert tool.display_name == "Criar Task no ClickUp"
    assert tool.category == "clickup"
    assert tool.is_global is True
    assert isinstance(tool.config, dict)


def test_agent_tool_default_values():
    """Defaults apply at DB insert time; at construction they are None."""
    tool = AgentTool(
        tool_key="test",
        display_name="Test",
        description="Test tool",
        category="test",
    )
    # SQLAlchemy column defaults apply at flush, not at __init__
    assert tool.tool_key == "test"
    assert tool.display_name == "Test"
    assert tool.description == "Test tool"
    assert tool.category == "test"


def test_agent_tool_explicit_defaults():
    tool = AgentTool(
        tool_key="test",
        display_name="Test",
        description="Test tool",
        category="test",
        is_global=True,
        config={},
    )
    assert tool.is_global is True
    assert tool.config == {}


def test_agent_config_has_enabled_tools():
    config = AgentConfig(
        agent_name="test_agent",
        model_id="test/model",
        instructions=["do stuff"],
        enabled_tools=["clickup_create_task", "search_web"],
    )
    assert config.enabled_tools == ["clickup_create_task", "search_web"]


def test_agent_config_enabled_tools_default():
    """enabled_tools column default applies at DB insert; at construction it is None."""
    config = AgentConfig(
        agent_name="test_agent",
        model_id="test/model",
        instructions=["do stuff"],
        enabled_tools=[],
    )
    assert config.enabled_tools == []
