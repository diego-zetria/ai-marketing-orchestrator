"""Observability setup and initialization.

This module handles the initialization of OpenTelemetry tracing with
Langfuse v3 as the backend and AgnoInstrumentor for automatic Agno tracing.

Pattern:
    Uses singleton pattern to prevent re-initialization and ensure
    consistent tracing across the application lifecycle.

Reference:
    - Agno docs: https://docs.agno.com/integrations/observability/langfuse
    - OpenInference: https://pypi.org/project/openinference-instrumentation-agno/
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)

# Singleton state
_initialized = False
_init_lock = threading.Lock()
_tracer: Tracer | None = None


def _get_settings():
    """Get settings instance, returns None if unavailable."""
    try:
        from src.config.settings import Settings

        return Settings()
    except Exception:
        return None


def is_observability_enabled() -> bool:
    """Check if observability is enabled via configuration.

    Returns:
        True if observability_enabled is set to true and required
        credentials are available.
    """
    try:
        settings = _get_settings()
        if settings is None:
            raise ImportError("Settings unavailable")

        # Check if explicitly enabled
        enabled = getattr(settings, "observability_enabled", False)
        if not enabled:
            return False

        # Verify required credentials are present
        host = getattr(settings, "langfuse_host", "")
        public_key = getattr(settings, "langfuse_public_key", "")
        secret_key = getattr(settings, "langfuse_secret_key", "")

        if not all([host, public_key, secret_key]):
            logger.warning(
                "Observability enabled but missing required credentials. "
                "Set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, and LANGFUSE_SECRET_KEY."
            )
            return False

        return True
    except ImportError:
        # Fallback to environment variables
        enabled = os.getenv("OBSERVABILITY_ENABLED", "false").lower() == "true"
        if not enabled:
            return False

        host = os.getenv("LANGFUSE_HOST", "")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

        return all([host, public_key, secret_key])


def setup_observability(
    service_name: str = "marketing-briefing-bot",
    force_reinit: bool = False,
) -> bool:
    """Initialize observability with Langfuse v3 + OpenTelemetry + AgnoInstrumentor.

    This function sets up:
    1. OpenTelemetry TracerProvider with BatchSpanProcessor
    2. OTLPSpanExporter configured for Langfuse OTLP endpoint
    3. AgnoInstrumentor for automatic Agno Teams/Agents/Tools tracing

    Args:
        service_name: Name of the service for tracing identification.
        force_reinit: Force re-initialization even if already initialized.

    Returns:
        True if initialization was successful, False otherwise.

    Example:
        >>> if is_observability_enabled():
        ...     setup_observability()
        ...     # Now all Agno operations are automatically traced
    """
    global _initialized, _tracer

    # Check if already initialized (singleton pattern)
    if _initialized and not force_reinit:
        logger.debug("Observability already initialized, skipping.")
        return True

    with _init_lock:
        # Double-check after acquiring lock
        if _initialized and not force_reinit:
            return True

        if not is_observability_enabled():
            logger.info("Observability is disabled. Skipping initialization.")
            return False

        try:
            # Import OpenTelemetry components
            # Import AgnoInstrumentor
            from openinference.instrumentation.agno import AgnoInstrumentor
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            # Get configuration
            settings = _get_settings()
            if settings is not None:
                langfuse_host = settings.langfuse_host
                public_key = settings.langfuse_public_key
                secret_key = settings.langfuse_secret_key
            else:
                langfuse_host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
                public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
                secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

            # Build OTLP endpoint URL
            # Langfuse v3 OTLP endpoint: /api/public/otel/v1/traces
            otlp_endpoint = f"{langfuse_host.rstrip('/')}/api/public/otel/v1/traces"

            logger.info(f"Initializing observability with endpoint: {otlp_endpoint}")

            # Create resource with service name
            resource = Resource.create(
                {
                    "service.name": service_name,
                    "service.version": "2.0.0",
                    "deployment.environment": os.getenv("ENVIRONMENT", "development"),
                }
            )

            # Create TracerProvider
            tracer_provider = TracerProvider(resource=resource)

            # Create OTLP exporter with Langfuse authentication
            # Langfuse uses Basic auth: public_key:secret_key
            import base64

            auth_string = f"{public_key}:{secret_key}"
            auth_bytes = auth_string.encode("utf-8")
            auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

            # Note: OTLPSpanExporter sends protobuf format by default
            # The endpoint should be the full path without adding /v1/traces
            # Langfuse v3 OTLP endpoint expects protobuf (application/x-protobuf)
            exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers={
                    "Authorization": f"Basic {auth_base64}",
                    "Content-Type": "application/x-protobuf",
                },
                timeout=30,  # Increase timeout for network latency
            )

            # Add BatchSpanProcessor for efficient span export
            span_processor = BatchSpanProcessor(
                exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                schedule_delay_millis=5000,  # Export every 5 seconds
            )
            tracer_provider.add_span_processor(span_processor)

            # Set the global TracerProvider
            trace.set_tracer_provider(tracer_provider)

            # Initialize AgnoInstrumentor for automatic Agno tracing
            # This automatically traces all Agno Teams, Agents, and Tools
            instrumentor = AgnoInstrumentor()
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument(tracer_provider=tracer_provider)
                logger.info("AgnoInstrumentor initialized successfully.")
            else:
                logger.debug("Agno already instrumented, skipping.")

            # Store tracer for custom spans
            _tracer = trace.get_tracer(service_name)
            _initialized = True

            logger.info(
                f"Observability initialized successfully. "
                f"Service: {service_name}, Endpoint: {otlp_endpoint}"
            )
            return True

        except ImportError as e:
            logger.error(
                f"Failed to import observability dependencies. "
                f"Install with: pip install -r requirements-observability.txt. "
                f"Error: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize observability: {e}", exc_info=True)
            return False


def shutdown_observability() -> None:
    """Gracefully shutdown observability and flush pending spans.

    Call this during application shutdown to ensure all spans are exported.
    """
    global _initialized, _tracer

    if not _initialized:
        return

    try:
        from opentelemetry import trace

        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "shutdown"):
            tracer_provider.shutdown()
            logger.info("Observability shutdown completed. All spans flushed.")

        _initialized = False
        _tracer = None
    except Exception as e:
        logger.error(f"Error during observability shutdown: {e}")


def get_tracer(name: str | None = None) -> Tracer | None:
    """Get the OpenTelemetry tracer instance.

    Args:
        name: Optional tracer name. If not provided, uses the default tracer.

    Returns:
        The tracer instance, or None if observability is not initialized.

    Example:
        >>> tracer = get_tracer()
        >>> if tracer:
        ...     with tracer.start_as_current_span("my_operation") as span:
        ...         span.set_attribute("custom.attribute", "value")
        ...         # ... your code ...
    """
    global _tracer

    if not _initialized:
        return None

    if name:
        from opentelemetry import trace

        return trace.get_tracer(name)

    return _tracer


def get_observability_status() -> dict:
    """Get current observability status and configuration.

    Returns:
        Dictionary with observability status information.
    """
    global _initialized

    settings = _get_settings()
    if settings is not None:
        langfuse_host = getattr(settings, "langfuse_host", "")
        public_key = getattr(settings, "langfuse_public_key", "")
        service_name = getattr(settings, "observability_service_name", "marketing-briefing-bot")
        sample_rate = getattr(settings, "observability_sample_rate", 1.0)
    else:
        langfuse_host = os.getenv("LANGFUSE_HOST", "")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        service_name = os.getenv("OBSERVABILITY_SERVICE_NAME", "marketing-briefing-bot")
        sample_rate = float(os.getenv("OBSERVABILITY_SAMPLE_RATE", "1.0"))

    return {
        "enabled": is_observability_enabled(),
        "initialized": _initialized,
        "langfuse_configured": bool(langfuse_host and public_key),
        "langfuse_host": langfuse_host,
        "service_name": service_name,
        "sample_rate": sample_rate,
    }


def reinitialize_observability() -> bool:
    """Reinitialize observability with current configuration.

    Useful when configuration changes at runtime.

    Returns:
        True if reinitialization was successful.
    """
    global _initialized

    # First shutdown existing
    if _initialized:
        shutdown_observability()

    # Then reinitialize
    return setup_observability(force_reinit=True)
