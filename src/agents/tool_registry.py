"""Map tool_keys to actual Agno tool functions."""

from __future__ import annotations

from typing import Callable

# Registry of available tool functions
TOOL_FUNCTIONS: dict[str, Callable] = {}


def register_tool(tool_key: str):
    """Decorator to register a function as an agent tool."""
    def decorator(func: Callable) -> Callable:
        TOOL_FUNCTIONS[tool_key] = func
        return func
    return decorator


def get_tools_for_agent(enabled_tools: list[str]) -> list[Callable]:
    """Return list of tool functions for the given enabled tool keys."""
    return [TOOL_FUNCTIONS[key] for key in enabled_tools if key in TOOL_FUNCTIONS]
