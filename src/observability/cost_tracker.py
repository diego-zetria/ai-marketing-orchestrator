"""Professional LLM Cost Tracking System.

This module provides comprehensive cost tracking for the LLM Resilience System,
supporting all providers in the fallback chain:
- Claude (Anthropic)
- OpenRouter
- Groq
- OpenAI
- Ollama (local, free)

Features:
- Per-request cost calculation with provider awareness
- Budget tracking with daily/weekly/monthly limits
- Alert system for budget thresholds
- Per-agent and per-team cost attribution
- Langfuse trace integration
- Real-time cost monitoring

Usage:
    from src.observability.cost_tracker import (
        CostTracker,
        calculate_request_cost,
        get_daily_cost_summary,
    )

    # Track a request
    cost = calculate_request_cost(
        provider="claude",
        model="claude-haiku-4-5-20251001",
        input_tokens=1000,
        output_tokens=500,
        agent_name="research_agent",
        team_name="research_department",
    )

    # Check budget status
    summary = get_daily_cost_summary()
    if summary["percentage_used"] > 0.8:
        logger.warning("Budget alert: 80% of daily budget used")
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _get_settings():
    """Get settings instance, returns None if unavailable."""
    try:
        from src.config.settings import Settings

        return Settings()
    except Exception:
        return None


# =============================================================================
# Provider and Model Cost Definitions (Per 1M Tokens)
# =============================================================================


class LLMProvider(str, Enum):
    """LLM providers supported by the cost tracking system."""

    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    OPENAI = "openai"
    OLLAMA = "ollama"


# Cost per 1M tokens for each model
COST_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    # Claude (Anthropic) - Updated January 2026
    "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    # Legacy Claude aliases
    "claude-3-opus-latest": {"input": 15.00, "output": 75.00},
    "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-latest": {"input": 1.00, "output": 5.00},
    # OpenRouter model IDs (prefixed with provider)
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-haiku-4": {"input": 1.00, "output": 5.00},
    "anthropic/claude-opus-4": {"input": 15.00, "output": 75.00},
    # Groq - Llama models (fast inference, lower cost)
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.3-70b-specdec": {"input": 0.59, "output": 0.79},
    "llama-3.2-90b-vision-preview": {"input": 0.90, "output": 0.90},
    "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
    # OpenAI - GPT models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Ollama (local) - FREE
    "qwen3:8b": {"input": 0.00, "output": 0.00},
    "qwen3:14b": {"input": 0.00, "output": 0.00},
    "qwen3:32b": {"input": 0.00, "output": 0.00},
    "deepseek-r1:32b": {"input": 0.00, "output": 0.00},
    "llama3.2:latest": {"input": 0.00, "output": 0.00},
    "mistral:latest": {"input": 0.00, "output": 0.00},
}

# Default costs for unknown models (conservative estimate)
DEFAULT_COSTS = {
    LLMProvider.CLAUDE: {"input": 3.00, "output": 15.00},
    LLMProvider.OPENROUTER: {"input": 3.00, "output": 15.00},
    LLMProvider.GROQ: {"input": 0.59, "output": 0.79},
    LLMProvider.OPENAI: {"input": 2.50, "output": 10.00},
    LLMProvider.OLLAMA: {"input": 0.00, "output": 0.00},
}


# =============================================================================
# Cost Calculation Functions
# =============================================================================


def get_model_cost(model: str, provider: LLMProvider | str | None = None) -> dict[str, float]:
    """Get cost per 1M tokens for a model.

    Args:
        model: Model identifier.
        provider: Optional provider hint for default costs.

    Returns:
        Dictionary with 'input' and 'output' costs per 1M tokens.
    """
    if model in COST_PER_1M_TOKENS:
        return COST_PER_1M_TOKENS[model]

    # Try to infer provider from model name
    if provider is None:
        if "/" in model:
            # OpenRouter-style model ID (e.g., "anthropic/claude-sonnet-4")
            provider = LLMProvider.OPENROUTER
        elif "claude" in model.lower():
            provider = LLMProvider.CLAUDE
        elif "gpt" in model.lower():
            provider = LLMProvider.OPENAI
        elif "llama" in model.lower() or "mixtral" in model.lower():
            provider = LLMProvider.GROQ
        elif any(x in model.lower() for x in ["qwen", "deepseek", "mistral"]):
            provider = LLMProvider.OLLAMA
        else:
            provider = LLMProvider.CLAUDE  # Conservative default

    if isinstance(provider, str):
        provider = LLMProvider(provider)

    return DEFAULT_COSTS.get(provider, DEFAULT_COSTS[LLMProvider.CLAUDE])


def calculate_request_cost(
    provider: LLMProvider | str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    agent_name: str | None = None,
    team_name: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    record: bool = True,
) -> float:
    """Calculate and optionally record the cost of an LLM request.

    Args:
        provider: LLM provider used.
        model: Model identifier.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        agent_name: Optional agent that made the request.
        team_name: Optional team the agent belongs to.
        user_id: Optional user identifier.
        session_id: Optional session identifier.
        record: Whether to record the cost in the tracker.

    Returns:
        Cost in USD.

    Example:
        >>> cost = calculate_request_cost(
        ...     provider="claude",
        ...     model="claude-haiku-4-5-20251001",
        ...     input_tokens=1000,
        ...     output_tokens=500,
        ...     agent_name="research_agent",
        ...     team_name="research_department",
        ... )
        >>> print(f"Cost: ${cost:.6f}")
        Cost: $0.003500
    """
    costs = get_model_cost(model, provider)

    # Cost per 1M tokens -> per token
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    total_cost = input_cost + output_cost

    # Record in cost tracker if enabled
    if record:
        tracker = get_cost_tracker()
        tracker.record_request(
            provider=(provider if isinstance(provider, LLMProvider) else LLMProvider(provider)),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=total_cost,
            agent_name=agent_name,
            team_name=team_name,
            user_id=user_id,
            session_id=session_id,
        )

    return total_cost


# =============================================================================
# Cost Record Data Classes
# =============================================================================


@dataclass
class CostRecord:
    """Individual cost record for an LLM request."""

    timestamp: datetime
    provider: LLMProvider
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    agent_name: str | None = None
    team_name: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    fallback_used: bool = False
    original_provider: LLMProvider | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "provider": self.provider.value,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost": self.cost,
            "agent_name": self.agent_name,
            "team_name": self.team_name,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "fallback_used": self.fallback_used,
            "original_provider": (self.original_provider.value if self.original_provider else None),
        }

    def to_langfuse_attributes(self) -> dict[str, Any]:
        """Convert to Langfuse trace attributes."""
        attrs = {
            "llm.provider": self.provider.value,
            "llm.model": self.model,
            "llm.input_tokens": self.input_tokens,
            "llm.output_tokens": self.output_tokens,
            "llm.total_tokens": self.input_tokens + self.output_tokens,
            "llm.cost_usd": self.cost,
            "llm.is_local": self.provider == LLMProvider.OLLAMA,
        }

        if self.agent_name:
            attrs["agent.name"] = self.agent_name
        if self.team_name:
            attrs["agent.team"] = self.team_name
        if self.user_id:
            attrs["user.id"] = self.user_id
        if self.session_id:
            attrs["session.id"] = self.session_id
        if self.fallback_used:
            attrs["llm.fallback_used"] = True
            if self.original_provider:
                attrs["llm.original_provider"] = self.original_provider.value

        return attrs


@dataclass
class DailyCostSummary:
    """Daily cost summary with budget tracking."""

    date: date
    total_cost: float = 0.0
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cost_by_provider: dict[str, float] = field(default_factory=dict)
    cost_by_agent: dict[str, float] = field(default_factory=dict)
    cost_by_team: dict[str, float] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    budget_limit: float = 50.0
    alert_threshold: float = 0.8

    @property
    def percentage_used(self) -> float:
        """Get budget usage percentage."""
        if self.budget_limit <= 0:
            return 0.0
        return self.total_cost / self.budget_limit

    @property
    def is_over_alert_threshold(self) -> bool:
        """Check if budget usage exceeds alert threshold."""
        return self.percentage_used >= self.alert_threshold

    @property
    def is_over_budget(self) -> bool:
        """Check if budget is exceeded."""
        return self.percentage_used >= 1.0

    @property
    def remaining_budget(self) -> float:
        """Get remaining budget in USD."""
        return max(0.0, self.budget_limit - self.total_cost)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "date": self.date.isoformat(),
            "total_cost": round(self.total_cost, 6),
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "cost_by_provider": {k: round(v, 6) for k, v in self.cost_by_provider.items()},
            "cost_by_agent": {k: round(v, 6) for k, v in self.cost_by_agent.items()},
            "cost_by_team": {k: round(v, 6) for k, v in self.cost_by_team.items()},
            "cost_by_model": {k: round(v, 6) for k, v in self.cost_by_model.items()},
            "budget": {
                "limit_usd": self.budget_limit,
                "used_usd": round(self.total_cost, 6),
                "remaining_usd": round(self.remaining_budget, 6),
                "percentage_used": round(self.percentage_used * 100, 2),
                "alert_threshold": self.alert_threshold,
                "is_over_alert": self.is_over_alert_threshold,
                "is_over_budget": self.is_over_budget,
            },
        }


# =============================================================================
# Cost Tracker Service
# =============================================================================


class CostTracker:
    """Professional LLM cost tracking service.

    This class provides comprehensive cost tracking with:
    - Real-time cost calculation
    - Budget monitoring with alerts
    - Per-agent and per-team attribution
    - Langfuse trace integration
    - Daily/weekly/monthly summaries

    Example:
        >>> tracker = CostTracker(
        ...     daily_budget=50.0, alert_threshold=0.8
        ... )
        >>> tracker.record_request(
        ...     provider=LLMProvider.CLAUDE,
        ...     model="claude-haiku-4-5-20251001",
        ...     input_tokens=1000,
        ...     output_tokens=500,
        ...     cost=0.0035,
        ...     agent_name="research_agent",
        ... )
        >>> summary = tracker.get_daily_summary()
        >>> print(f"Daily cost: ${summary.total_cost:.4f}")
    """

    def __init__(
        self,
        daily_budget: float | None = None,
        alert_threshold: float | None = None,
        hard_limit: bool = False,
        alert_callback: (Callable[[str, float, float], None] | None) = None,
    ) -> None:
        """Initialize cost tracker.

        Args:
            daily_budget: Daily budget limit in USD.
            alert_threshold: Percentage (0-1) at which to trigger alerts.
            hard_limit: If True, raises exception when budget exceeded.
            alert_callback: Callback on budget alerts (message, current, limit).
        """
        # Load from settings if not provided
        settings = _get_settings()
        if settings is not None:
            self._daily_budget = (
                daily_budget
                if daily_budget is not None
                else getattr(settings, "llm_budget_daily_usd", 50.0)
            )
            self._alert_threshold = (
                alert_threshold
                if alert_threshold is not None
                else getattr(settings, "llm_budget_alert_threshold", 0.8)
            )
            self._hard_limit = hard_limit or getattr(settings, "llm_budget_hard_limit", False)
        else:
            self._daily_budget = daily_budget or 50.0
            self._alert_threshold = alert_threshold or 0.8
            self._hard_limit = hard_limit

        self._alert_callback = alert_callback
        self._lock = threading.Lock()

        # Storage
        self._records: list[CostRecord] = []
        self._daily_summaries: dict[date, DailyCostSummary] = {}

        # Alert state
        self._alert_50_sent = False
        self._alert_80_sent = False
        self._alert_100_sent = False

    def record_request(
        self,
        provider: LLMProvider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        agent_name: str | None = None,
        team_name: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        fallback_used: bool = False,
        original_provider: LLMProvider | None = None,
    ) -> CostRecord:
        """Record an LLM request cost.

        Args:
            provider: LLM provider used.
            model: Model identifier.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            cost: Calculated cost in USD.
            agent_name: Optional agent name.
            team_name: Optional team name.
            user_id: Optional user identifier.
            session_id: Optional session identifier.
            fallback_used: Whether this was a fallback request.
            original_provider: Original provider if fallback was used.

        Returns:
            The created CostRecord.

        Raises:
            BudgetExceededError: If hard limit is enabled and budget exceeded.
        """
        with self._lock:
            # Check budget before recording
            if self._hard_limit:
                today = date.today()
                summary = self._get_or_create_daily_summary(today)
                if summary.is_over_budget:
                    raise BudgetExceededError(
                        f"Daily budget of "
                        f"${self._daily_budget:.2f} exceeded. "
                        f"Current usage: "
                        f"${summary.total_cost:.2f}"
                    )

            # Create record
            record = CostRecord(
                timestamp=datetime.utcnow(),
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                agent_name=agent_name,
                team_name=team_name,
                user_id=user_id,
                session_id=session_id,
                fallback_used=fallback_used,
                original_provider=original_provider,
            )
            self._records.append(record)

            # Update daily summary
            today = date.today()
            summary = self._get_or_create_daily_summary(today)
            self._update_daily_summary(summary, record)

            # Check budget alerts
            self._check_budget_alerts(summary)

            # Add to Langfuse trace if available
            self._add_to_langfuse_trace(record)

            return record

    def _get_or_create_daily_summary(self, day: date) -> DailyCostSummary:
        """Get or create daily summary for a date."""
        if day not in self._daily_summaries:
            self._daily_summaries[day] = DailyCostSummary(
                date=day,
                budget_limit=self._daily_budget,
                alert_threshold=self._alert_threshold,
            )
        return self._daily_summaries[day]

    def _update_daily_summary(self, summary: DailyCostSummary, record: CostRecord) -> None:
        """Update daily summary with new record."""
        summary.total_cost += record.cost
        summary.total_requests += 1
        summary.total_input_tokens += record.input_tokens
        summary.total_output_tokens += record.output_tokens

        # Update breakdowns
        provider_key = record.provider.value
        summary.cost_by_provider[provider_key] = (
            summary.cost_by_provider.get(provider_key, 0.0) + record.cost
        )

        if record.agent_name:
            summary.cost_by_agent[record.agent_name] = (
                summary.cost_by_agent.get(record.agent_name, 0.0) + record.cost
            )

        if record.team_name:
            summary.cost_by_team[record.team_name] = (
                summary.cost_by_team.get(record.team_name, 0.0) + record.cost
            )

        summary.cost_by_model[record.model] = (
            summary.cost_by_model.get(record.model, 0.0) + record.cost
        )

    def _check_budget_alerts(self, summary: DailyCostSummary) -> None:
        """Check and send budget alerts."""
        percentage = summary.percentage_used

        # Reset alerts for new day
        if summary.date != date.today():
            self._alert_50_sent = False
            self._alert_80_sent = False
            self._alert_100_sent = False

        # 50% alert
        if percentage >= 0.5 and not self._alert_50_sent:
            self._send_alert(
                "Budget 50% alert",
                summary.total_cost,
                summary.budget_limit,
                "info",
            )
            self._alert_50_sent = True

        # 80% alert (threshold)
        if percentage >= self._alert_threshold and not self._alert_80_sent:
            self._send_alert(
                f"Budget {int(self._alert_threshold * 100)}% alert",
                summary.total_cost,
                summary.budget_limit,
                "warning",
            )
            self._alert_80_sent = True

        # 100% alert
        if percentage >= 1.0 and not self._alert_100_sent:
            self._send_alert(
                "Budget EXCEEDED",
                summary.total_cost,
                summary.budget_limit,
                "error",
            )
            self._alert_100_sent = True

    def _send_alert(
        self,
        message: str,
        current: float,
        limit: float,
        level: str = "warning",
    ) -> None:
        """Send a budget alert."""
        full_message = (
            f"[LLM Cost Alert] {message}: "
            f"${current:.2f} / ${limit:.2f} "
            f"({current / limit * 100:.1f}%)"
        )

        # Log the alert
        if level == "error":
            logger.error(full_message)
        elif level == "warning":
            logger.warning(full_message)
        else:
            logger.info(full_message)

        # Call custom callback if provided
        if self._alert_callback:
            try:
                self._alert_callback(message, current, limit)
            except Exception as e:
                logger.error(f"Budget alert callback failed: {e}")

    def _add_to_langfuse_trace(self, record: CostRecord) -> None:
        """Add cost record to current Langfuse trace."""
        try:
            from src.observability.setup import get_tracer

            tracer = get_tracer()
            if tracer is None:
                return

            # Get current span and add attributes
            from opentelemetry import trace

            current_span = trace.get_current_span()

            if current_span and current_span.is_recording():
                attrs = record.to_langfuse_attributes()
                for key, value in attrs.items():
                    current_span.set_attribute(key, value)

        except Exception as e:
            logger.debug(f"Failed to add cost to Langfuse trace: {e}")

    def get_daily_summary(self, day: date | None = None) -> DailyCostSummary:
        """Get daily cost summary.

        Args:
            day: Date to get summary for. Defaults to today.

        Returns:
            DailyCostSummary for the specified day.
        """
        with self._lock:
            target_day = day or date.today()
            return self._get_or_create_daily_summary(target_day)

    def get_records(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        provider: LLMProvider | None = None,
        agent_name: str | None = None,
        team_name: str | None = None,
        limit: int = 1000,
    ) -> list[CostRecord]:
        """Get cost records with optional filtering.

        Args:
            start_date: Filter records from this date.
            end_date: Filter records until this date.
            provider: Filter by provider.
            agent_name: Filter by agent name.
            team_name: Filter by team name.
            limit: Maximum number of records to return.

        Returns:
            List of matching CostRecords.
        """
        with self._lock:
            records = self._records.copy()

        # Apply filters
        if start_date:
            records = [r for r in records if r.timestamp.date() >= start_date]
        if end_date:
            records = [r for r in records if r.timestamp.date() <= end_date]
        if provider:
            records = [r for r in records if r.provider == provider]
        if agent_name:
            records = [r for r in records if r.agent_name == agent_name]
        if team_name:
            records = [r for r in records if r.team_name == team_name]

        return records[-limit:]

    def get_total_cost(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> float:
        """Get total cost for a date range.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Total cost in USD.
        """
        records = self.get_records(
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )
        return sum(r.cost for r in records)

    def get_cost_by_provider(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, float]:
        """Get cost breakdown by provider.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Dictionary mapping provider names to costs.
        """
        records = self.get_records(
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )
        breakdown: dict[str, float] = {}
        for r in records:
            key = r.provider.value
            breakdown[key] = breakdown.get(key, 0.0) + r.cost
        return breakdown

    def get_cost_by_agent(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, float]:
        """Get cost breakdown by agent.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Dictionary mapping agent names to costs.
        """
        records = self.get_records(
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )
        breakdown: dict[str, float] = {}
        for r in records:
            key = r.agent_name or "unknown"
            breakdown[key] = breakdown.get(key, 0.0) + r.cost
        return breakdown

    def get_cost_by_team(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, float]:
        """Get cost breakdown by team.

        Args:
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Dictionary mapping team names to costs.
        """
        records = self.get_records(
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )
        breakdown: dict[str, float] = {}
        for r in records:
            key = r.team_name or "unknown"
            breakdown[key] = breakdown.get(key, 0.0) + r.cost
        return breakdown

    def reset_daily_alerts(self) -> None:
        """Reset alert flags for testing or new day."""
        with self._lock:
            self._alert_50_sent = False
            self._alert_80_sent = False
            self._alert_100_sent = False

    def clear_records(self, before_date: date | None = None) -> int:
        """Clear cost records, optionally before a date.

        Args:
            before_date: Clear records before this date. If None, clears all.

        Returns:
            Number of records cleared.
        """
        with self._lock:
            if before_date is None:
                count = len(self._records)
                self._records.clear()
                self._daily_summaries.clear()
                return count

            original_count = len(self._records)
            self._records = [r for r in self._records if r.timestamp.date() >= before_date]

            # Clear old daily summaries
            to_remove = [d for d in self._daily_summaries if d < before_date]
            for d in to_remove:
                del self._daily_summaries[d]

            return original_count - len(self._records)


# =============================================================================
# Exceptions
# =============================================================================


class BudgetExceededError(Exception):
    """Raised when LLM budget is exceeded and hard limit is enabled."""

    pass


# =============================================================================
# Singleton Instance
# =============================================================================

_cost_tracker: CostTracker | None = None
_tracker_lock = threading.Lock()


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance.

    Returns:
        The singleton CostTracker instance.
    """
    global _cost_tracker

    if _cost_tracker is None:
        with _tracker_lock:
            if _cost_tracker is None:
                _cost_tracker = CostTracker()

    return _cost_tracker


def reset_cost_tracker(
    daily_budget: float | None = None,
    alert_threshold: float | None = None,
    hard_limit: bool = False,
    alert_callback: (Callable[[str, float, float], None] | None) = None,
) -> CostTracker:
    """Reset the global cost tracker with new configuration.

    Args:
        daily_budget: Daily budget limit in USD.
        alert_threshold: Percentage (0-1) at which to trigger alerts.
        hard_limit: If True, raises exception when budget exceeded.
        alert_callback: Function called on budget alerts.

    Returns:
        The new CostTracker instance.
    """
    global _cost_tracker

    with _tracker_lock:
        _cost_tracker = CostTracker(
            daily_budget=daily_budget,
            alert_threshold=alert_threshold,
            hard_limit=hard_limit,
            alert_callback=alert_callback,
        )

    return _cost_tracker


# =============================================================================
# Convenience Functions
# =============================================================================


def get_daily_cost_summary(
    day: date | None = None,
) -> dict[str, Any]:
    """Get daily cost summary as dictionary.

    Args:
        day: Date to get summary for. Defaults to today.

    Returns:
        Dictionary with daily cost summary.
    """
    tracker = get_cost_tracker()
    summary = tracker.get_daily_summary(day)
    return summary.to_dict()


def get_budget_status() -> dict[str, Any]:
    """Get current budget status.

    Returns:
        Dictionary with budget status information.
    """
    tracker = get_cost_tracker()
    summary = tracker.get_daily_summary()

    return {
        "date": summary.date.isoformat(),
        "budget_limit_usd": summary.budget_limit,
        "current_usage_usd": round(summary.total_cost, 6),
        "remaining_usd": round(summary.remaining_budget, 6),
        "percentage_used": round(summary.percentage_used * 100, 2),
        "is_over_alert_threshold": summary.is_over_alert_threshold,
        "is_over_budget": summary.is_over_budget,
        "alert_threshold": summary.alert_threshold,
        "total_requests": summary.total_requests,
    }


def is_budget_available(required_cost: float = 0.0) -> bool:
    """Check if budget is available for a request.

    Args:
        required_cost: Estimated cost of the request.

    Returns:
        True if budget is available (or hard limit disabled).
    """
    settings = _get_settings()
    if settings is not None:
        if not getattr(settings, "llm_budget_hard_limit", False):
            return True
    else:
        return True

    tracker = get_cost_tracker()
    summary = tracker.get_daily_summary()
    return summary.total_cost + required_cost <= summary.budget_limit
