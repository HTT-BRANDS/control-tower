"""
Distributed Tracing Configuration

OpenTelemetry integration for request tracing and observability.
"""

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import get_settings


def setup_tracing(app) -> Optional[trace.Tracer]:
    """
    Configure OpenTelemetry tracing for the application.

    Args:
        app: FastAPI application instance

    Returns:
        Tracer instance or None if tracing disabled
    """
    settings = get_settings()
    if not settings.enable_tracing:
        return None

    # Configure resource
    resource = Resource.create({
        SERVICE_NAME: "azure-governance-platform",
        SERVICE_VERSION: settings.app_version,
        "deployment.environment": settings.environment,
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Configure exporter
    if settings.otel_exporter_endpoint:
        # OTLP exporter (for Jaeger, Honeycomb, etc.)
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_endpoint,
            headers=settings.otel_exporter_headers
        )
    else:
        # Console exporter for development
        exporter = ConsoleSpanExporter()

    # Add span processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    return trace.get_tracer(__name__)


def get_tracer(name: str) -> Optional[trace.Tracer]:
    """Get a tracer for the current module."""
    try:
        return trace.get_tracer(name)
    except Exception:
        return None


class TracedContext:
    """Context manager for manual span creation."""

    def __init__(self, tracer: trace.Tracer, name: str, attributes: Optional[dict] = None):
        self.tracer = tracer
        self.name = name
        self.attributes = attributes or {}
        self.span = None

    def __enter__(self):
        if self.tracer:
            self.span = self.tracer.start_as_current_span(self.name)
            self.span.__enter__()
            for key, value in self.attributes.items():
                self.span.set_attribute(key, value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_val:
                self.span.set_attribute("error", True)
                self.span.set_attribute("error.message", str(exc_val))
            self.span.__exit__(exc_type, exc_val, exc_tb)
