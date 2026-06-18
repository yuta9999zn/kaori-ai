"""Kafka producer for ai-orchestrator events."""
import json
import os

import structlog
from aiokafka import AIOKafkaProducer

log = structlog.get_logger()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

_producer: AIOKafkaProducer | None = None


async def init_kafka() -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
        enable_idempotence=True,
    )
    await _producer.start()
    log.info("orchestrator.kafka.producer_ready")


async def close_kafka() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


async def emit(topic: str, payload: dict) -> None:
    if _producer is None:
        log.warning("orchestrator.kafka.not_ready", topic=topic)
        return

    # Issue #4 — validate against the topic schema. A bad payload
    # raises InvalidEventError / UnknownTopicError; the calling
    # handler returns 5xx so the developer sees the bug during dev,
    # not three hops later in a consumer log. Same contract as the
    # data-pipeline producer + outbox enqueue path.
    from .event_schema import validate_event  # local import keeps circular-safe
    validate_event(topic, payload)

    # headers=[] explicit — opentelemetry-instrumentation-aiokafka 0.49b2
    # otherwise raises "got multiple values for argument 'headers'".
    await _producer.send_and_wait(topic, value=payload, headers=[])
    log.debug("orchestrator.kafka.emitted", topic=topic)
