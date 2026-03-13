from src.api.admin.agents import AgentConfigResponse, AgentConfigUpdate
from src.api.admin.tools import ToolCreate, ToolResponse, ToolUpdate


def test_tool_create_schema():
    t = ToolCreate(
        tool_key="clickup_create_task",
        display_name="Criar Task",
        description="Cria task no ClickUp",
        category="clickup",
    )
    assert t.tool_key == "clickup_create_task"
    assert t.is_global is True
    assert t.config == {}


def test_tool_update_schema():
    t = ToolUpdate(display_name="Novo Nome")
    assert t.display_name == "Novo Nome"
    assert t.description is None


def test_tool_response_schema():
    t = ToolResponse(
        id="abc",
        tool_key="test",
        display_name="Test",
        description="desc",
        category="cat",
        is_global=True,
        config={},
    )
    assert t.id == "abc"


def test_agent_config_update_has_enabled_tools():
    u = AgentConfigUpdate(enabled_tools=["clickup_create_task", "search_web"])
    assert u.enabled_tools == ["clickup_create_task", "search_web"]


def test_agent_config_response_has_enabled_tools():
    r = AgentConfigResponse(
        id="abc",
        agent_name="test",
        model_id="test/model",
        instructions=["test"],
        is_active=True,
        enabled_tools=["tool1"],
    )
    assert r.enabled_tools == ["tool1"]
