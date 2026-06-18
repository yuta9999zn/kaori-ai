"""
Shared Kafka producer for data-pipeline service.
Produces events to pipeline.* topics (K-11: immutable contract — add fields only).
"""
import asyncio
import json
import os
from typing import Optional

import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

log = structlog.get_logger()

_producer: Optional[AIOKafkaProducer] = None

# `docker compose restart` (not `up`) skips depends_on healthcheck gating, so
# data-pipeline can come up before Kafka finishes electing a controller — the
# AIOKafkaProducer.start() call then raises KafkaConnectionError and the
# FastAPI lifespan aborts. Retry a handful of times before giving up so the
# normal restart-after-host-reboot path doesn't strand the container in
# "Up (unhealthy)" with no app process.
_BOOTSTRAP_RETRY_ATTEMPTS = 10
_BOOTSTRAP_RETRY_DELAY_SEC = 3.0


async def init_kafka():
    global _producer
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    last_err: Optional[Exception] = None
    for attempt in range(1, _BOOTSTRAP_RETRY_ATTEMPTS + 1):
        _producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            enable_idempotence=True,
        )
        try:
            await _producer.start()
            log.info("kafka.producer.started", bootstrap=bootstrap, attempt=attempt)
            return
        except KafkaConnectionError as e:
            last_err = e
            log.warning(
                "kafka.producer.bootstrap_retry",
                bootstrap=bootstrap,
                attempt=attempt,
                max_attempts=_BOOTSTRAP_RETRY_ATTEMPTS,
                error=str(e),
            )
            # Producer left in failed state — close it before next attempt
            # to avoid leaking the inner client.
            try:
                await _producer.stop()
            except Exception:
                pass
            _producer = None
            if attempt < _BOOTSTRAP_RETRY_ATTEMPTS:
                await asyncio.sleep(_BOOTSTRAP_RETRY_DELAY_SEC)
    log.error("kafka.producer.bootstrap_exhausted", bootstrap=bootstrap)
    raise last_err if last_err else KafkaConnectionError("Unable to bootstrap Kafka")


async def close_kafka():
    if _producer:
        await _producer.stop()
        log.info("kafka.producer.stopped")


async def send_event(topic: str, payload: dict):
    if _producer is None:
        log.warning("kafka.producer.not_initialized", topic=topic)
        return

    # Issue #4 — schema validation. The two failure shapes are
    # treated very differently:
    #
    #   InvalidEventError / UnknownTopicError  → caller bug. Raise so
    #     the request handler returns 5xx and the developer notices
    #     during dev/CI rather than three hops later in a consumer
    #     log. Consistent with the outbox enqueue path.
    #
    #   Kafka send failure (network, broker down) → log and swallow,
    #     the pipeline keeps running. This is the existing contract;
    #     the comment below is preserved as the reason it stays.
    from .event_schema import validate_event  # local import to keep circular-safe
    validate_event(topic, payload)

    try:
        # Pass headers=[] explicitly so opentelemetry-instrumentation-aiokafka
        # 0.49b2 doesn't trip "got multiple values for argument 'headers'" by
        # injecting trace-context headers on top of an unset kwarg.
        await _producer.send_and_wait(topic, value=payload, headers=[])
        log.debug("kafka.event.sent", topic=topic, run_id=payload.get("run_id"))
    except Exception as e:
        log.error("kafka.event.failed", topic=topic, error=str(e))
        # Don't raise — pipeline continues even if Kafka is unavailable


# Alias — routers/clean.py and routers/analyze.py import under the legacy name
# `emit` (from a pre-refactor API). Keeps both names pointing at the same impl
# so the Kafka outbox refactor (ARCHITECTURE_REVIEW.md item C) can later change
# behavior in exactly one place.
emit = send_event
