"""
Cartographer — OpenTelemetry Configuration.

Initialises OpenTelemetry tracing and propagation.
Instruments FastAPI, SQLAlchemy, and Redis automatically.
Falls back to a no-op tracer when OTEL_ENABLED=false (default in dev).

Usage:
    configure_telemetry(settings)  # called once in lifespan startup
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def configure_telemetry(settings: object) -> None:  # type: ignore[type-arg]
    """
    Set up OpenTelemetry SDK based on application settings.

    Args:
        settings: Application Settings instance (typed as object to avoid
                  circular imports; accesses attributes directly).
    """
    otel_enabled: bool = getattr(settings, "otel_enabled", False)

    if not otel_enabled:
        logger.debug("telemetry.disabled", reason="OTEL_ENABLED=false")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {SERVICE_NAME: getattr(settings, "otel_service_name", "cartographer")}
        )

        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(
            endpoint=getattr(settings, "otel_exporter_otlp_endpoint", "http://localhost:4317"),
            insecure=True,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # Auto-instrument supported libraries
        FastAPIInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()
        RedisInstrumentor().instrument()

        logger.info(
            "telemetry.configured",
            service=getattr(settings, "otel_service_name", "cartographer"),
            endpoint=getattr(settings, "otel_exporter_otlp_endpoint", ""),
        )

    except ImportError as exc:
        logger.warning(
            "telemetry.import_failed",
            error=str(exc),
            hint="Install opentelemetry packages or set OTEL_ENABLED=false",
        )
    except Exception as exc:
        logger.error("telemetry.configure_failed", error=str(exc))


def get_tracer(name: str) -> object:
    """
    Return an OpenTelemetry Tracer for the given instrumentation scope.

    Returns a no-op tracer when OTel is disabled.

    Args:
        name: Usually __name__ of the calling module.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:

        class _NoOpTracer:
            def start_as_current_span(self, *_: object, **__: object) -> object:
                from contextlib import contextmanager

                @contextmanager  # type: ignore[arg-type]
                def _noop(*_a: object, **_kw: object):  # type: ignore[misc]
                    yield None

                return _noop()

        return _NoOpTracer()
