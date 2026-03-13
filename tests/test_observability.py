"""Tests for the observability module."""

import pytest


@pytest.fixture(autouse=True)
def _reset_cost_tracker():
    """Reset the cost tracker singleton before each test to ensure isolation."""
    from src.observability.cost_tracker import reset_cost_tracker

    reset_cost_tracker()
    yield
    reset_cost_tracker()


def test_observability_disabled_by_default():
    """Verify observability is disabled when env vars are not set."""
    from src.observability import is_observability_enabled

    assert is_observability_enabled() is False


def test_get_observability_status_when_disabled():
    """Verify status endpoint works when observability is disabled."""
    from src.observability import get_observability_status

    status = get_observability_status()
    assert status["enabled"] is False
    assert status["initialized"] is False


def test_decorators_noop_when_disabled():
    """Verify decorators pass through when observability is disabled."""
    from src.observability import trace_agent, trace_span, trace_tool

    @trace_agent(name="test_agent")
    def agent_fn():
        return "agent_result"

    @trace_tool(name="test_tool")
    def tool_fn(x):
        return x * 2

    @trace_span(name="test_span")
    def span_fn():
        return "span_result"

    assert agent_fn() == "agent_result"
    assert tool_fn(5) == 10
    assert span_fn() == "span_result"


def test_pii_sanitization():
    """Verify PII patterns are correctly redacted."""
    from src.observability import sanitize_pii

    text = "Email: test@gmail.com, CPF: 123.456.789-00, Phone: +55 11 99999-9999"
    result = sanitize_pii(text)
    assert "[EMAIL_REDACTED]" in result
    assert "[CPF_REDACTED]" in result
    assert "[PHONE_REDACTED]" in result
    assert "test@gmail.com" not in result
    assert "123.456.789-00" not in result


def test_cost_calculation():
    """Verify cost calculation for OpenRouter models."""
    from src.observability.cost_tracker import calculate_request_cost

    cost = calculate_request_cost(
        provider="openrouter",
        model="anthropic/claude-sonnet-4",
        input_tokens=1000,
        output_tokens=500,
        record=False,
    )
    # input: 1000/1M * 3.00 = 0.003, output: 500/1M * 15.00 = 0.0075
    assert abs(cost - 0.0105) < 0.0001


def test_budget_status():
    """Verify budget status returns correct structure."""
    from src.observability import get_budget_status

    status = get_budget_status()
    assert "budget_limit_usd" in status
    assert "current_usage_usd" in status
    assert "percentage_used" in status
    assert status["current_usage_usd"] == 0.0


def test_setup_returns_false_when_disabled():
    """Verify setup returns False when observability is disabled."""
    from src.observability import setup_observability

    result = setup_observability()
    assert result is False


def test_shutdown_noop_when_not_initialized():
    """Verify shutdown is safe when not initialized."""
    from src.observability import shutdown_observability

    shutdown_observability()


def test_get_tracer_returns_none_when_disabled():
    """Verify get_tracer returns None when not initialized."""
    from src.observability import get_tracer

    assert get_tracer() is None


def test_langfuse_client_noop_when_not_configured():
    """Verify Langfuse client functions return safely when not configured."""
    from src.observability import get_current_trace_id, record_score

    assert get_current_trace_id() is None
    assert record_score("test", 0.5) is False
