"""
OpenTelemetry tracing setup — Phase 2 #2/#5.

One ``setup_tracing(service_name, app)`` call from each service's
``main.py`` wires:
  * an OTLP HTTP exporter pointing at Tempo (``http://tempo:4318/v1/traces``
    by default, override via ``OTLP_ENDPOINT``);
  * batched span processor so we don't pay a network hop per span;
  * auto-instrumentation for FastAPI / asyncpg / aiokafka / httpx — every
    inbound request, DB query, Kafka produce/consume, and outgoing HTTP
    call gets a span without manual sprinkles;
  * a ``structlog`` processor (``trace_id_processor``) so every log line
    emitted while a request is in flight carries ``trace_id`` and
    ``span_id`` for Tempo↔log pivoting.

Mirror of services/data-pipeline/shared/tracing.py — kept synchronised
across both ai-orchestrator + data-pipeline (and the flat-layout root
copies in llm-gateway + notification-service).

Sampling: ``TRACING_SAMPLE_RATE`` env var (default 1.0 = capture all)
matches the Java side. Production tunes this down once trace volume
justifies the storage cost.

No-op safety: ``TRACING_ENABLED=false`` short-circuits the whole setup
so dev environments without a Tempo backend boot cleanly.
"""
from __future__ import annotations

import os
from typing import Any

import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from .kaori_sampler import build_sampler as _kaori_build_sampler

# aiokafka instrumentation is imported lazily inside setup_tracing because
# notification-service + llm-gateway don't ship the aiokafka instrumentor
# dependency (no Kafka in their dep tree).

log = structlog.get_logger()

_DEFAULT_OTLP_ENDPOINT = "http://tempo:4318/v1/traces"


def _is_enabled() -> bool:
    """``TRACING_ENABLED`` env var. Default ``true`` so the pilot stack
    captures spans out of the box; flip to ``false`` for unit-test runs
    or local dev without a Tempo container."""
    return os.getenv("TRACING_ENABLED", "true").lower() not in {"false", "0", "no"}


def _sample_rate() -> float:
    """``TRACING_SAMPLE_RATE`` env var. 1.0 captures everything (pilot
    default); production drops to 0.05–0.1 once volume justifies."""
    try:
        return float(os.getenv("TRACING_SAMPLE_RATE", "1.0"))
    except ValueError:
        return 1.0


def setup_tracing(
    service_name: str,
    app: FastAPI,
    *,
    instrument_kafka: bool = True,
) -> None:
    """Wire OpenTelemetry into a FastAPI service.

    Call from ``main.py`` AFTER the FastAPI app is constructed and
    BEFORE any request comes in (top-level module scope or at the start
    of the lifespan ``yield`` works equally well).

    Args:
        service_name: ``service.name`` resource attribute. Shows up as
                      the service label in Grafana Tempo.
        app:          The FastAPI instance — wraps it so every request
                      becomes a server span automatically.
        instrument_kafka: ``False`` for services without aiokafka in the
                      dependency tree (notification-service). Default ``True``.
    """
    if not _is_enabled():
        log.info("tracing.skipped reason=disabled")
        return

    endpoint = os.getenv("OTLP_ENDPOINT", _DEFAULT_OTLP_ENDPOINT)

    resource = Resource.create({SERVICE_NAME: service_name})
    # OBS-005 — path-aware head sampler. KAORI_USE_FLAT_SAMPLER=true env
    # escape hatch rolls back to flat ratio without code change.
    if os.getenv("KAORI_USE_FLAT_SAMPLER", "false").lower() in {"true", "1", "yes"}:
        sampler = TraceIdRatioBased(_sample_rate())
    else:
        sampler = _kaori_build_sampler()
    provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)

    # Auto-instrumentation hooks — wrap each library so spans are emitted
    # without changing call sites. AsyncPG + httpx + aiokafka cover the
    # service-to-service hops that PR #4 cares about; FastAPI covers the
    # inbound side.
    FastAPIInstrumentor.instrument_app(app)
    AsyncPGInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    if instrument_kafka:
        # Lazy import — services without aiokafka in their dep tree
        # (notification-service, llm-gateway) skip this branch and
        # never load the module.
        from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
        AIOKafkaInstrumentor().instrument()

    log.info(
        "tracing.ready",
        service=service_name,
        endpoint=endpoint,
        sample_rate=_sample_rate(),
        kafka_instrumented=instrument_kafka,
    )


def trace_id_processor(_logger: Any, _name: str, event_dict: dict) -> dict:
    """structlog processor — attach the active span's trace_id and
    span_id to every log entry. Tempo's "view logs for this trace"
    button uses these keys.

    Drop-in: register via :func:`configure_structlog_with_trace` (called
    once at process start) or manually in ``structlog.configure(processors
    =[..., trace_id_processor])`` BEFORE the renderer.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx is not None and ctx.is_valid:
        # 32-hex trace_id + 16-hex span_id, formatted to match Tempo's
        # display + the Spring Boot Logback pattern.
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def _make_service_name_processor(service_name: str):
    """Closure factory — returns a processor that stamps every log line
    with ``service.name``. K-19 (OBS-012) requires every log/span carry
    service identity so Loki/Jaeger queries can pivot by service.

    Key uses dot-separated form to match OTel resource attribute
    convention; Loki + LogQL handle dotted keys fine.
    """
    def processor(_logger: Any, _name: str, event_dict: dict) -> dict:
        event_dict.setdefault("service.name", service_name)
        return event_dict
    return processor


def configure_structlog_with_trace(service_name: str) -> None:
    """Set up a structlog pipeline that emits one JSON line per log
    record with ``trace_id``, ``span_id``, and ``service.name``
    populated.

    Idempotent — safe to call from main.py module scope. Services that
    already had a ``structlog.configure(...)`` call from before this PR
    can drop it in favour of this helper; the merge_contextvars +
    add_log_level + TimeStamper + format_exc_info processor chain
    matches what the old default emitted, plus the new trace_id +
    service_name steps.

    P1-S1 (OBS-012) — service.name added so Loki can filter logs per
    service; tenant_id / user_id / request_id are bound at request time
    via :mod:`shared.log_context` middleware (merge_contextvars picks
    them up).
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _make_service_name_processor(service_name),
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            trace_id_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    log.info("structlog.configured", service=service_name)
