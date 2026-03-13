"""Observability metrics and cost tracking.

This module provides:
- Cost calculation per model (Anthropic Claude models)
- Session metrics aggregation
- Token usage tracking
- Performance metrics collection

Pricing Reference (January 2026):
    - Claude Opus 4.5: $0.015/1K input, $0.075/1K output
    - Claude Sonnet 4.5: $0.003/1K input, $0.015/1K output
    - Claude Haiku 4.5: $0.0008/1K input, $0.004/1K output
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Model Pricing Configuration (January 2026)
# =============================================================================

MODEL_PRICING: dict[str, dict[str, float]] = {
    # Claude Opus 4.5 (2025 version)
    "claude-opus-4-5-20251101": {
        "input": 0.015,  # $0.015 per 1K input tokens
        "output": 0.075,  # $0.075 per 1K output tokens
    },
    # Claude Sonnet 4.5 (2025 version)
    "claude-sonnet-4-5-20250929": {
        "input": 0.003,  # $0.003 per 1K input tokens
        "output": 0.015,  # $0.015 per 1K output tokens
    },
    # Claude Haiku 4.5 (2025 version)
    "claude-haiku-4-5-20251001": {
        "input": 0.0008,  # $0.0008 per 1K input tokens
        "output": 0.004,  # $0.004 per 1K output tokens
    },
    # Legacy aliases (mapped to equivalent models)
    "claude-3-opus-latest": {
        "input": 0.015,
        "output": 0.075,
    },
    "claude-3-5-sonnet-latest": {
        "input": 0.003,
        "output": 0.015,
    },
    "claude-3-5-haiku-latest": {
        "input": 0.0008,
        "output": 0.004,
    },
}

# Default pricing for unknown models
DEFAULT_PRICING = {
    "input": 0.003,  # Conservative Sonnet pricing
    "output": 0.015,
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate the cost for a model invocation.

    Args:
        model: Model identifier (e.g., "claude-opus-4-5-20251101").
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Estimated cost in USD.

    Example:
        >>> cost = calculate_cost(
        ...     model="claude-haiku-4-5-20251001",
        ...     input_tokens=1000,
        ...     output_tokens=500
        ... )
        >>> print(f"Cost: ${cost:.6f}")
        Cost: $0.002800
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]

    return input_cost + output_cost


@dataclass
class AgentMetrics:
    """Metrics for a single agent execution."""

    agent_name: str
    team: str | None = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0
    cost: float = 0.0
    status: str = "unknown"
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "team": self.team,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "cost": self.cost,
            "status": self.status,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SessionMetrics:
    """Aggregated metrics for a session."""

    session_id: str
    user_id: str | None = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_duration_ms: float = 0.0
    agent_metrics: list[AgentMetrics] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_agent_metrics(self, metrics: AgentMetrics) -> None:
        """Add agent metrics and update aggregates."""
        self.agent_metrics.append(metrics)
        self.total_requests += 1
        self.total_input_tokens += metrics.input_tokens
        self.total_output_tokens += metrics.output_tokens
        self.total_tokens += metrics.total_tokens
        self.total_cost += metrics.cost
        self.total_duration_ms += metrics.duration_ms

        if metrics.error:
            self.errors.append(metrics.error)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "total_duration_ms": self.total_duration_ms,
            "agent_count": len(self.agent_metrics),
            "error_count": len(self.errors),
            "agent_metrics": [m.to_dict() for m in self.agent_metrics],
            "errors": self.errors,
        }


class ObservabilityMetrics:
    """Centralized metrics collection and aggregation.

    This class provides session-level metrics tracking with cost calculation
    and performance monitoring.

    Example:
        >>> metrics = ObservabilityMetrics(session_id="sess_123")
        >>> metrics.record_agent_call(
        ...     agent_name="research_agent",
        ...     model="claude-haiku-4-5-20251001",
        ...     input_tokens=500,
        ...     output_tokens=1000,
        ...     duration_ms=250.5,
        ... )
        >>> summary = metrics.get_summary()
        >>> print(f"Total cost: ${summary['total_cost']:.4f}")
    """

    def __init__(
        self,
        session_id: str,
        user_id: str | None = None,
    ) -> None:
        """Initialize metrics collector.

        Args:
            session_id: Unique session identifier.
            user_id: Optional user identifier for personalization.
        """
        self._session_metrics = SessionMetrics(
            session_id=session_id,
            user_id=user_id,
        )
        self._start_time = time.perf_counter()

    def record_agent_call(
        self,
        agent_name: str,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: float = 0.0,
        team: str | None = None,
        status: str = "success",
        error: str | None = None,
    ) -> AgentMetrics:
        """Record metrics for an agent call.

        Args:
            agent_name: Name of the agent.
            model: Model used for the call.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            duration_ms: Execution time in milliseconds.
            team: Team the agent belongs to.
            status: Call status (success, error).
            error: Error message if status is error.

        Returns:
            The recorded agent metrics.
        """
        cost = calculate_cost(model, input_tokens, output_tokens)
        total_tokens = input_tokens + output_tokens

        metrics = AgentMetrics(
            agent_name=agent_name,
            team=team,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            cost=cost,
            status=status,
            error=error,
        )

        self._session_metrics.add_agent_metrics(metrics)
        return metrics

    def get_summary(self) -> dict[str, Any]:
        """Get session metrics summary.

        Returns:
            Dictionary with aggregated session metrics.
        """
        # Update end time
        self._session_metrics.end_time = datetime.utcnow()

        return self._session_metrics.to_dict()

    def get_cost_breakdown(self) -> dict[str, float]:
        """Get cost breakdown by model.

        Returns:
            Dictionary mapping model names to total costs.
        """
        breakdown: dict[str, float] = {}

        for metrics in self._session_metrics.agent_metrics:
            model = metrics.model or "unknown"
            if model not in breakdown:
                breakdown[model] = 0.0
            breakdown[model] += metrics.cost

        return breakdown

    def get_agent_breakdown(self) -> dict[str, dict[str, Any]]:
        """Get metrics breakdown by agent.

        Returns:
            Dictionary mapping agent names to their aggregated metrics.
        """
        breakdown: dict[str, dict[str, Any]] = {}

        for metrics in self._session_metrics.agent_metrics:
            agent = metrics.agent_name
            if agent not in breakdown:
                breakdown[agent] = {
                    "calls": 0,
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "total_duration_ms": 0.0,
                    "errors": 0,
                }

            breakdown[agent]["calls"] += 1
            breakdown[agent]["total_tokens"] += metrics.total_tokens
            breakdown[agent]["total_cost"] += metrics.cost
            breakdown[agent]["total_duration_ms"] += metrics.duration_ms
            if metrics.error:
                breakdown[agent]["errors"] += 1

        return breakdown

    @property
    def total_cost(self) -> float:
        """Get total session cost."""
        return self._session_metrics.total_cost

    @property
    def total_tokens(self) -> int:
        """Get total tokens used in session."""
        return self._session_metrics.total_tokens

    @property
    def request_count(self) -> int:
        """Get total number of requests in session."""
        return self._session_metrics.total_requests


# =============================================================================
# Session Metrics Storage (In-Memory Cache)
# =============================================================================

_session_metrics_cache: dict[str, ObservabilityMetrics] = {}


def get_session_metrics(
    session_id: str,
    user_id: str | None = None,
) -> ObservabilityMetrics:
    """Get or create metrics collector for a session.

    Args:
        session_id: Unique session identifier.
        user_id: Optional user identifier.

    Returns:
        ObservabilityMetrics instance for the session.
    """
    if session_id not in _session_metrics_cache:
        _session_metrics_cache[session_id] = ObservabilityMetrics(
            session_id=session_id,
            user_id=user_id,
        )

    return _session_metrics_cache[session_id]


def clear_session_metrics(session_id: str) -> None:
    """Clear metrics for a session.

    Args:
        session_id: Session identifier to clear.
    """
    if session_id in _session_metrics_cache:
        del _session_metrics_cache[session_id]


def get_all_session_summaries() -> list[dict[str, Any]]:
    """Get summaries for all active sessions.

    Returns:
        List of session summary dictionaries.
    """
    return [metrics.get_summary() for metrics in _session_metrics_cache.values()]
