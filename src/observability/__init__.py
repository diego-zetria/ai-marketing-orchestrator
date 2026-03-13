"""Observability module for Marketing Briefing Bot.

This module provides comprehensive observability for the Agno multi-agent system
using Langfuse v3 + OpenTelemetry + OpenInference integration.

Features:
- Automatic tracing of Agno Teams, Agents, and Tools
- Cost tracking per model and session
- Performance metrics collection
- PII sanitization for sensitive data
- Conditional initialization based on configuration

Usage:
    from src.observability import setup_observability, is_observability_enabled

    # Initialize at application startup
    if is_observability_enabled():
        setup_observability()

    # Or use the decorators for custom tracing
    from src.observability import trace_agent, trace_tool

    @trace_agent(name="my_agent", team="research")
    def my_agent_function():
        pass

    @trace_tool(name="my_tool")
    def my_tool_function():
        pass
"""

from src.observability.cost_tracker import (
    COST_PER_1M_TOKENS,
    BudgetExceededError,
    CostRecord,
    CostTracker,
    DailyCostSummary,
    calculate_request_cost,
    get_budget_status,
    get_cost_tracker,
    get_daily_cost_summary,
    is_budget_available,
    reset_cost_tracker,
)
from src.observability.decorators import (
    trace_agent,
    trace_span,
    trace_tool,
)
from src.observability.langfuse_client import (
    create_dataset,
    create_dataset_item,
    get_current_trace_id,
    # Debug Loop (Doctor Agent)
    get_trace,
    get_trace_observations,
    get_trace_scores,
    record_score,
)
from src.observability.metrics import (
    ObservabilityMetrics,
    calculate_cost,
    get_session_metrics,
)
from src.observability.setup import (
    get_observability_status,
    get_tracer,
    is_observability_enabled,
    reinitialize_observability,
    setup_observability,
    shutdown_observability,
)
from src.observability.utils import (
    create_trace_context,
    format_span_attributes,
    sanitize_pii,
)

__all__ = [
    # Setup functions
    "setup_observability",
    "shutdown_observability",
    "is_observability_enabled",
    "get_tracer",
    "get_observability_status",
    "reinitialize_observability",
    # Decorators
    "trace_agent",
    "trace_tool",
    "trace_span",
    # Metrics (legacy)
    "ObservabilityMetrics",
    "calculate_cost",
    "get_session_metrics",
    # Cost Tracker (professional)
    "CostTracker",
    "CostRecord",
    "DailyCostSummary",
    "BudgetExceededError",
    "get_cost_tracker",
    "reset_cost_tracker",
    "calculate_request_cost",
    "get_daily_cost_summary",
    "get_budget_status",
    "is_budget_available",
    "COST_PER_1M_TOKENS",
    # Utilities
    "sanitize_pii",
    "format_span_attributes",
    "create_trace_context",
    "record_score",
    "create_dataset",
    "create_dataset_item",
    "get_current_trace_id",
    # Debug Loop (Doctor Agent)
    "get_trace",
    "get_trace_observations",
    "get_trace_scores",
]

__version__ = "2.0.0"
