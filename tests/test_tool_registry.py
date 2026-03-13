from src.agents.tool_registry import TOOL_FUNCTIONS, get_tools_for_agent, register_tool


def test_register_tool():
    @register_tool("test_tool_reg")
    def my_tool():
        return "hello"

    assert "test_tool_reg" in TOOL_FUNCTIONS
    assert TOOL_FUNCTIONS["test_tool_reg"]() == "hello"


def test_get_tools_for_agent():
    @register_tool("test_tool_get")
    def another_tool():
        return "world"

    tools = get_tools_for_agent(["test_tool_get"])
    assert len(tools) == 1
    assert tools[0]() == "world"


def test_get_tools_unknown_key():
    tools = get_tools_for_agent(["nonexistent_key_xyz"])
    assert len(tools) == 0
