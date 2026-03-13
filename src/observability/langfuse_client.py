"""Langfuse client helpers for scoring and datasets.

These helpers provide optional Langfuse SDK integration. If the SDK or
credentials are missing, functions become no-ops.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client = None


def _get_settings():
    """Get settings instance, returns None if unavailable."""
    try:
        from src.config.settings import Settings

        return Settings()
    except Exception:
        return None


def _is_configured() -> bool:
    settings = _get_settings()
    if settings is None:
        return False
    return bool(
        getattr(settings, "langfuse_host", "")
        and getattr(settings, "langfuse_public_key", "")
        and getattr(settings, "langfuse_secret_key", "")
    )


def _get_client():
    global _client
    if _client is not None:
        return _client

    if not _is_configured():
        return None

    try:
        from langfuse import Langfuse

        settings = _get_settings()
        if settings is None:
            return None

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return _client
    except Exception as e:
        logger.debug(f"Langfuse SDK not available or failed to initialize: {e}")
        return None


def get_current_trace_id() -> str | None:
    """Get current OpenTelemetry trace ID (hex), if any."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:
        return None
    return None


def record_score(
    name: str,
    value: float,
    trace_id: str | None = None,
    comment: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record a Langfuse score for the current trace.

    Returns True if the score was sent, False otherwise.
    """
    client = _get_client()
    if client is None:
        return False

    trace_id = trace_id or get_current_trace_id()
    if not trace_id:
        return False

    payload = {
        "name": name,
        "value": value,
        "trace_id": trace_id,
        "comment": comment,
        "metadata": metadata or {},
    }

    try:
        if hasattr(client, "score"):
            client.score(**payload)
            return True
        if hasattr(client, "api") and hasattr(client.api, "score"):
            client.api.score.create(**payload)
            return True
    except Exception as e:
        logger.debug(f"Failed to record Langfuse score: {e}")
        return False

    return False


def create_dataset(
    name: str,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Create a Langfuse dataset (idempotent if supported by SDK)."""
    client = _get_client()
    if client is None:
        return False

    payload = {
        "name": name,
        "description": description,
        "metadata": metadata or {},
    }

    try:
        if hasattr(client, "dataset") and hasattr(client.dataset, "create"):
            client.dataset.create(**payload)
            return True
        if hasattr(client, "api") and hasattr(client.api, "dataset"):
            client.api.dataset.create(**payload)
            return True
    except Exception as e:
        logger.debug(f"Failed to create Langfuse dataset: {e}")
        return False

    return False


def create_dataset_item(
    dataset_name: str,
    input_data: dict[str, Any],
    expected_output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Create a Langfuse dataset item."""
    client = _get_client()
    if client is None:
        return False

    payload = {
        "dataset_name": dataset_name,
        "input": input_data,
        "expected_output": expected_output,
        "metadata": metadata or {},
    }

    try:
        if hasattr(client, "dataset_item") and hasattr(client.dataset_item, "create"):
            client.dataset_item.create(**payload)
            return True
        if hasattr(client, "api") and hasattr(client.api, "dataset_item"):
            client.api.dataset_item.create(**payload)
            return True
    except Exception as e:
        logger.debug(f"Failed to create Langfuse dataset item: {e}")
        return False

    return False


# ============================================================================
# Trace Retrieval (for Debug Loop / Doctor Agent)
# ============================================================================


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert an object to dict using .dict() or dict()."""
    return obj.dict() if hasattr(obj, "dict") else dict(obj)


def get_trace(trace_id: str) -> dict[str, Any] | None:
    """Retrieve a full trace from Langfuse by ID.

    Used by the Doctor Agent to analyze failed traces and diagnose issues.

    Args:
        trace_id: The Langfuse trace ID to retrieve

    Returns:
        Full trace data including observations, scores, and metadata.
        None if not found or client unavailable.
    """
    client = _get_client()
    if client is None:
        logger.debug("Langfuse client not configured, cannot fetch trace")
        return None

    try:
        # Langfuse Python SDK fetch_trace method
        if hasattr(client, "fetch_trace"):
            trace = client.fetch_trace(trace_id)
            if trace:
                return _to_dict(trace)

        # Alternative: Use API client directly
        if hasattr(client, "api") and hasattr(client.api, "trace"):
            trace = client.api.trace.get(trace_id)
            if trace:
                return _to_dict(trace)

        # Fallback: Direct HTTP request
        settings = _get_settings()
        if settings is None:
            return None

        import httpx

        response = httpx.get(
            f"{settings.langfuse_host}/api/public/traces/{trace_id}",
            headers={
                "Authorization": f"Basic {_get_auth_header()}",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        logger.warning(f"Failed to fetch Langfuse trace {trace_id}: {e}")
        return None


def get_trace_observations(
    trace_id: str,
) -> list[dict[str, Any]]:
    """Get all observations (spans, generations, events) for a trace.

    Args:
        trace_id: The Langfuse trace ID

    Returns:
        List of observation dictionaries with type, input, output, etc.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        # Use API client to fetch observations
        if hasattr(client, "api") and hasattr(client.api, "observations"):
            result = client.api.observations.get_many(trace_id=trace_id)
            if result and hasattr(result, "data"):
                return [_to_dict(obs) for obs in result.data]

        # Fallback: Direct HTTP request
        settings = _get_settings()
        if settings is None:
            return []

        import httpx

        response = httpx.get(
            f"{settings.langfuse_host}/api/public/observations",
            params={"traceId": trace_id},
            headers={
                "Authorization": f"Basic {_get_auth_header()}",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    except Exception as e:
        logger.warning(f"Failed to fetch observations for trace {trace_id}: {e}")
        return []


def get_trace_scores(trace_id: str) -> list[dict[str, Any]]:
    """Get all scores for a trace.

    Args:
        trace_id: The Langfuse trace ID

    Returns:
        List of score dictionaries with name, value, comment, etc.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        # Use API client to fetch scores
        if hasattr(client, "api") and hasattr(client.api, "scores"):
            result = client.api.scores.get_many(trace_id=trace_id)
            if result and hasattr(result, "data"):
                return [_to_dict(score) for score in result.data]

        # Fallback: Direct HTTP request
        settings = _get_settings()
        if settings is None:
            return []

        import httpx

        response = httpx.get(
            f"{settings.langfuse_host}/api/public/scores",
            params={"traceId": trace_id},
            headers={
                "Authorization": f"Basic {_get_auth_header()}",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])

    except Exception as e:
        logger.warning(f"Failed to fetch scores for trace {trace_id}: {e}")
        return []


def _get_auth_header() -> str:
    """Generate Basic auth header for Langfuse API."""
    import base64

    settings = _get_settings()
    if settings is None:
        return ""

    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}"
    return base64.b64encode(credentials.encode()).decode()
