"""Observability decorators for custom tracing.

This module provides decorators for manual tracing of functions that
are not automatically instrumented by AgnoInstrumentor.

Note:
    Most Agno Teams, Agents, and Tools are automatically traced by
    AgnoInstrumentor. Use these decorators only for custom functions
    or when you need additional tracing granularity.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, ParamSpec, TypeVar

from src.observability.setup import get_tracer, is_observability_enabled

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def trace_agent(
    name: str,
    team: str | None = None,
    **attributes: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace agent functions with OpenTelemetry.

    Creates a span with agent-specific attributes following OpenInference
    semantic conventions.

    Args:
        name: Name of the agent.
        team: Name of the team this agent belongs to.
        **attributes: Additional span attributes.

    Returns:
        Decorated function with tracing.

    Example:
        >>> @trace_agent(name="research_agent", team="research")
        ... def research_agent(query: str) -> str:
        ...     return "research results"
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not is_observability_enabled():
                return func(*args, **kwargs)

            tracer = get_tracer()
            if tracer is None:
                return func(*args, **kwargs)

            span_name = f"agent.{name}"
            with tracer.start_as_current_span(span_name) as span:
                # Set agent attributes (OpenInference semantic conventions)
                span.set_attribute("agent.name", name)
                if team:
                    span.set_attribute("agent.team", team)
                span.set_attribute("agent.type", "custom")

                # Add custom attributes
                for key, value in attributes.items():
                    span.set_attribute(f"agent.{key}", str(value))

                # Track execution time
                start_time = time.perf_counter()

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("agent.status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("agent.status", "error")
                    span.set_attribute("agent.error.type", type(e).__name__)
                    span.set_attribute("agent.error.message", str(e))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("agent.duration_ms", duration_ms)

        return wrapper

    return decorator


def trace_tool(
    name: str,
    **attributes: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace tool functions with OpenTelemetry.

    Creates a span with tool-specific attributes following OpenInference
    semantic conventions.

    Args:
        name: Name of the tool.
        **attributes: Additional span attributes.

    Returns:
        Decorated function with tracing.

    Example:
        >>> @trace_tool(name="web_search")
        ... def web_search(query: str) -> list[dict]:
        ...     return [{"title": "Result", "url": "http://..."}]
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not is_observability_enabled():
                return func(*args, **kwargs)

            tracer = get_tracer()
            if tracer is None:
                return func(*args, **kwargs)

            span_name = f"tool.{name}"
            with tracer.start_as_current_span(span_name) as span:
                # Set tool attributes (OpenInference semantic conventions)
                span.set_attribute("tool.name", name)
                span.set_attribute("tool.type", "function")

                # Add custom attributes
                for key, value in attributes.items():
                    span.set_attribute(f"tool.{key}", str(value))

                # Capture input (first positional arg or kwargs)
                if args:
                    span.set_attribute("tool.input", str(args[0])[:1000])
                elif kwargs:
                    span.set_attribute("tool.input", str(list(kwargs.values())[0])[:1000])

                # Track execution time
                start_time = time.perf_counter()

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("tool.status", "success")

                    # Capture output (truncated)
                    if result is not None:
                        span.set_attribute("tool.output", str(result)[:1000])

                    return result
                except Exception as e:
                    span.set_attribute("tool.status", "error")
                    span.set_attribute("tool.error.type", type(e).__name__)
                    span.set_attribute("tool.error.message", str(e))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("tool.duration_ms", duration_ms)

        return wrapper

    return decorator


def trace_span(
    name: str,
    kind: str = "internal",
    **attributes: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Generic decorator to create a traced span around a function.

    Use this for any function that doesn't fit the agent or tool categories.

    Args:
        name: Name of the span.
        kind: Kind of span (internal, client, server, producer, consumer).
        **attributes: Additional span attributes.

    Returns:
        Decorated function with tracing.

    Example:
        >>> @trace_span(name="process_response", kind="internal")
        ... def process_response(response: dict) -> dict:
        ...     return {"processed": True, **response}
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not is_observability_enabled():
                return func(*args, **kwargs)

            tracer = get_tracer()
            if tracer is None:
                return func(*args, **kwargs)

            with tracer.start_as_current_span(name) as span:
                # Set basic attributes
                span.set_attribute("span.kind", kind)
                span.set_attribute("code.function", func.__name__)
                span.set_attribute("code.module", func.__module__)

                # Add custom attributes
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))

                # Track execution time
                start_time = time.perf_counter()

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise
                finally:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    span.set_attribute("duration_ms", duration_ms)

        return wrapper

    return decorator


class TracedContext:
    """Context manager for creating traced spans manually.

    Use this when you need more control over span creation than
    decorators provide.

    Example:
        >>> with TracedContext("complex_operation") as span:
        ...     span.set_attribute("step", "initialization")
        ...     # ... initialization code ...
        ...     span.set_attribute("step", "processing")
        ...     # ... processing code ...
    """

    def __init__(
        self,
        name: str,
        **attributes: Any,
    ) -> None:
        """Initialize traced context.

        Args:
            name: Name of the span.
            **attributes: Initial span attributes.
        """
        self.name = name
        self.attributes = attributes
        self._span = None
        self._token = None
        self._start_time: float | None = None

    def __enter__(self):
        """Enter the traced context."""
        if not is_observability_enabled():
            return self

        tracer = get_tracer()
        if tracer is None:
            return self

        from opentelemetry import trace

        self._span = tracer.start_span(self.name)
        self._token = trace.use_span(self._span, end_on_exit=False)
        self._token.__enter__()

        # Set initial attributes
        for key, value in self.attributes.items():
            self._span.set_attribute(key, str(value))

        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the traced context."""
        if self._span is None:
            return False

        # Record duration
        if self._start_time is not None:
            duration_ms = (time.perf_counter() - self._start_time) * 1000
            self._span.set_attribute("duration_ms", duration_ms)

        # Record exception if any
        if exc_val is not None:
            self._span.set_attribute("status", "error")
            self._span.set_attribute("error.type", type(exc_val).__name__)
            self._span.set_attribute("error.message", str(exc_val))
            self._span.record_exception(exc_val)
        else:
            self._span.set_attribute("status", "success")

        # End span and exit context
        self._span.end()
        if self._token is not None:
            self._token.__exit__(exc_type, exc_val, exc_tb)

        return False

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key.
            value: Attribute value.
        """
        if self._span is not None:
            self._span.set_attribute(key, str(value))

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the current span.

        Args:
            name: Event name.
            attributes: Optional event attributes.
        """
        if self._span is not None:
            self._span.add_event(
                name,
                attributes={k: str(v) for k, v in (attributes or {}).items()},
            )
