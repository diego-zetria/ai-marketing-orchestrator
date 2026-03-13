"""Observability utility functions.

This module provides utility functions for:
- PII sanitization in trace data
- Span attribute formatting
- Trace context creation and management
- Helper functions for observability operations
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# PII Patterns for Sanitization
# =============================================================================

PII_PATTERNS: list[tuple[str, str, str]] = [
    # Email addresses
    (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "[EMAIL_REDACTED]",
        "email",
    ),
    # Phone numbers (various formats)
    (
        r"\b(\+\d{1,3}[-.\s]?)?\(?\d{2,3}\)?[-.\s]?\d{4,5}[-.\s]?\d{4}\b",
        "[PHONE_REDACTED]",
        "phone",
    ),
    # Brazilian CPF
    (
        r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        "[CPF_REDACTED]",
        "cpf",
    ),
    # Credit card numbers (basic pattern)
    (
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "[CARD_REDACTED]",
        "credit_card",
    ),
    # IP addresses
    (
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "[IP_REDACTED]",
        "ip_address",
    ),
    # API keys (common patterns)
    (
        r"\b(sk-|pk-|api_|key_)[A-Za-z0-9]{20,}\b",
        "[API_KEY_REDACTED]",
        "api_key",
    ),
    # JWT tokens
    (
        r"\beyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b",
        "[JWT_REDACTED]",
        "jwt",
    ),
    # Bearer tokens
    (
        r"\bBearer\s+[A-Za-z0-9_-]+\b",
        "[BEARER_REDACTED]",
        "bearer_token",
    ),
]


def sanitize_pii(
    text: str,
    patterns: list[tuple[str, str, str]] | None = None,
    hash_redacted: bool = False,
) -> str:
    """Sanitize PII from text for safe logging/tracing.

    Args:
        text: Text to sanitize.
        patterns: Optional custom patterns. Uses defaults if None.
        hash_redacted: If True, append hash suffix for correlation.

    Returns:
        Sanitized text with PII replaced.

    Example:
        >>> text = "Contact john@example.com or call 555-1234"
        >>> sanitized = sanitize_pii(text)
        >>> print(sanitized)
        Contact [EMAIL_REDACTED] or call [PHONE_REDACTED]
    """
    if not text:
        return text

    patterns_to_use = patterns or PII_PATTERNS
    result = text

    for pattern, replacement, pii_type in patterns_to_use:
        try:
            if hash_redacted:
                # Add hash suffix for correlation without revealing PII
                def replace_with_hash(match):
                    original = match.group(0)
                    hash_suffix = hashlib.sha256(original.encode()).hexdigest()[:8]
                    return f"{replacement}_{hash_suffix}"

                result = re.sub(pattern, replace_with_hash, result)
            else:
                result = re.sub(pattern, replacement, result)
        except re.error as e:
            logger.warning(f"Invalid regex pattern for {pii_type}: {e}")
            continue

    return result


def format_span_attributes(
    attributes: dict[str, Any],
    max_value_length: int = 1000,
    sanitize: bool = True,
) -> dict[str, str]:
    """Format attributes for OpenTelemetry spans.

    Converts all values to strings and applies length limits
    and optional PII sanitization.

    Args:
        attributes: Dictionary of attributes to format.
        max_value_length: Maximum length for string values.
        sanitize: Whether to apply PII sanitization.

    Returns:
        Formatted attributes dictionary.

    Example:
        >>> attrs = {"user_input": "Search for john@example.com", "count": 42}
        >>> formatted = format_span_attributes(attrs)
        >>> print(formatted)
        {'user_input': 'Search for [EMAIL_REDACTED]', 'count': '42'}
    """
    formatted: dict[str, str] = {}

    for key, value in attributes.items():
        # Convert to string
        if value is None:
            str_value = ""
        elif isinstance(value, (dict, list)):
            import json

            try:
                str_value = json.dumps(value, default=str)
            except (TypeError, ValueError):
                str_value = str(value)
        else:
            str_value = str(value)

        # Apply length limit
        if len(str_value) > max_value_length:
            str_value = str_value[:max_value_length] + "...[TRUNCATED]"

        # Apply PII sanitization
        if sanitize:
            str_value = sanitize_pii(str_value)

        formatted[key] = str_value

    return formatted


def create_trace_context(
    session_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
    **extra_context: Any,
) -> dict[str, str]:
    """Create a standard trace context dictionary.

    This provides a consistent set of context attributes
    for correlation across traces.

    Args:
        session_id: Session identifier.
        user_id: User identifier.
        request_id: Request identifier.
        **extra_context: Additional context attributes.

    Returns:
        Trace context dictionary.

    Example:
        >>> context = create_trace_context(
        ...     session_id="sess_123",
        ...     user_id="user_456",
        ...     feature="research",
        ... )
        >>> print(context)
        {'session.id': 'sess_123', 'user.id': 'user_456', ...}
    """
    context: dict[str, str] = {
        "trace.timestamp": datetime.utcnow().isoformat(),
    }

    if session_id:
        context["session.id"] = session_id
    else:
        context["session.id"] = str(uuid.uuid4())

    if user_id:
        context["user.id"] = user_id

    if request_id:
        context["request.id"] = request_id
    else:
        context["request.id"] = str(uuid.uuid4())

    # Add extra context
    for key, value in extra_context.items():
        context[f"context.{key}"] = str(value)

    return context


def extract_model_info(model_id: str) -> dict[str, str]:
    """Extract information from a model identifier.

    Args:
        model_id: Model identifier (e.g., "claude-opus-4-5-20251101").

    Returns:
        Dictionary with extracted model information.

    Example:
        >>> info = extract_model_info("claude-opus-4-5-20251101")
        >>> print(info)
        {'provider': 'anthropic', 'family': 'claude', 'tier': 'opus', ...}
    """
    info = {
        "provider": "unknown",
        "family": "unknown",
        "tier": "unknown",
        "version": "unknown",
        "full_id": model_id,
    }

    model_lower = model_id.lower()

    # Detect provider
    if "claude" in model_lower:
        info["provider"] = "anthropic"
        info["family"] = "claude"

        # Detect tier
        if "opus" in model_lower:
            info["tier"] = "opus"
        elif "sonnet" in model_lower:
            info["tier"] = "sonnet"
        elif "haiku" in model_lower:
            info["tier"] = "haiku"

        # Extract version (date pattern)
        version_match = re.search(r"\d{8}$", model_id)
        if version_match:
            info["version"] = version_match.group(0)

    elif "gpt" in model_lower:
        info["provider"] = "openai"
        info["family"] = "gpt"

    return info


def truncate_for_logging(
    text: str,
    max_length: int = 500,
    suffix: str = "...",
) -> str:
    """Truncate text for safe logging.

    Args:
        text: Text to truncate.
        max_length: Maximum length.
        suffix: Suffix to add when truncated.

    Returns:
        Truncated text.
    """
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def generate_trace_id() -> str:
    """Generate a unique trace ID.

    Returns:
        UUID-based trace identifier.
    """
    return str(uuid.uuid4())


def generate_span_id() -> str:
    """Generate a unique span ID.

    Returns:
        Short UUID-based span identifier.
    """
    return uuid.uuid4().hex[:16]


def calculate_latency_percentile(
    latencies: list[float],
    percentile: int = 95,
) -> float:
    """Calculate latency percentile.

    Args:
        latencies: List of latency values in milliseconds.
        percentile: Percentile to calculate (0-100).

    Returns:
        Percentile value.
    """
    if not latencies:
        return 0.0

    sorted_latencies = sorted(latencies)
    index = int(len(sorted_latencies) * percentile / 100)
    index = min(index, len(sorted_latencies) - 1)

    return sorted_latencies[index]


def format_duration(duration_ms: float) -> str:
    """Format duration for human-readable display.

    Args:
        duration_ms: Duration in milliseconds.

    Returns:
        Formatted duration string.

    Example:
        >>> format_duration(1500.5)
        '1.50s'
        >>> format_duration(250.0)
        '250ms'
    """
    if duration_ms < 1:
        return f"{duration_ms * 1000:.2f}us"
    elif duration_ms < 1000:
        return f"{duration_ms:.0f}ms"
    elif duration_ms < 60000:
        return f"{duration_ms / 1000:.2f}s"
    else:
        minutes = int(duration_ms / 60000)
        seconds = (duration_ms % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"


def format_tokens(tokens: int) -> str:
    """Format token count for human-readable display.

    Args:
        tokens: Token count.

    Returns:
        Formatted token string.

    Example:
        >>> format_tokens(1500)
        '1.5K'
        >>> format_tokens(1500000)
        '1.5M'
    """
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1000000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1000000:.2f}M"


def format_cost(cost: float) -> str:
    """Format cost for human-readable display.

    Args:
        cost: Cost in USD.

    Returns:
        Formatted cost string.

    Example:
        >>> format_cost(0.0025)
        '$0.0025'
        >>> format_cost(1.50)
        '$1.50'
    """
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"
