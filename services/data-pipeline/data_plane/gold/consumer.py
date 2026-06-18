"""
F-032 — Kafka consumer that triggers the Gold aggregator on
``kaori.pipeline.silver.complete``.

Mirrors the shape of ai-orchestrator/consumers/pipeline_consumer.py:
  * separate consumer group (``kaori-gold-aggregator``) so it doesn't
    fight the orchestrator's auto-analysis flow for offsets;
  * outbox-based dedup using the Kafka message key (G5 pattern);
  * per-message try/catch so one bad payload doesn't stall the partition.

Failure handling: if the aggregator raises, the consumer logs to
``kaori.dlq.gold-aggregator`` (intentionally a separate DLQ from the
orchestrator's). The DLQ producer is best-effort; we never re-raise to
the consumer loop.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .aggregator import aggregate_for_tenant
from ...shared import kafka_topics
from ...shared.db import get_pool
from ...shared.event_schema import raise_or_dlq
from ...shared.outbox import DuplicateEvent, mark_processed

log = structlog.get_logger()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP  = "kaori-gold-aggregator"
DLQ_TOPIC       = "kaori.dlq.gold-aggregator"

_running = True


async def start_gold_consumer() -> None:
    """Run the consumer loop until :func:`stop_gold_consumer` flips the
    stop flag. Designed to be launched via ``asyncio.create_task`` from
    the FastAPI lifespan."""
    # Phase 2 #8 — manual offset commits. Previously enable_auto_commit=True
    # with auto_offset_reset='latest' meant a restart mid-batch silently
    # skipped events because aiokafka had already moved the committed
    # offset forward. Now we commit ONLY after _dispatch succeeds (or after
    # a DLQ write completes, since the DLQ is the durable record we use to
    # retry later — we don't want a DLQ-failed message redelivered forever).
    # 'earliest' is safe because outbox dedup rejects re-processing.
    consumer = AIOKafkaConsumer(
        kafka_topics.PIPELINE_SILVER_COMPLETE,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    dlq = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
    )

    await consumer.start()
    await dlq.start()
    log.info("gold.consumer.started")

    try:
        async for msg in consumer:
            if not _running:
                break
            commit = False
            try:
                # Issue #4 — schema validation runs first. A bad payload
                # is sent to ``kaori.dlq.<topic>`` (with the schema error
                # in headers) and the offset is committed; we skip the
                # business work but never crash the consumer or burn
                # CPU re-DLQing the same message on every redelivery.
                ok = await _validate_or_dlq(msg, dlq)
                if ok:
                    await _dispatch(msg.topic, msg.value, msg.key)
                commit = True
            except Exception as exc:
                log.error("gold.consumer.dispatch_error",
                          topic=msg.topic, offset=msg.offset, error=str(exc))
                # DLQ write determines whether we advance the offset. If
                # DLQ accepts the failure record, the original message is
                # safely captured and we move on; if DLQ ALSO fails, we
                # leave the offset behind so the message reappears next
                # poll instead of disappearing forever.
                dlq_ok = await _send_dlq(dlq, msg.value, str(exc))
                commit = dlq_ok
            if commit:
                await consumer.commit()
    finally:
        await consumer.stop()
        await dlq.stop()
        log.info("gold.consumer.stopped")


async def _validate_or_dlq(msg, dlq: AIOKafkaProducer) -> bool:
    """Thin wrapper around ``shared.event_schema.raise_or_dlq`` so the
    DLQ producer + consumer-group label are owned in one place.
    Returns True when the payload is valid (continue with dispatch),
    False when it was DLQ'd (skip dispatch, commit offset)."""
    return await raise_or_dlq(
        msg.topic, msg.value, dlq,
        consumer_group=CONSUMER_GROUP,
        headers=list(msg.headers or []),
        key=msg.key,
    )


async def stop_gold_consumer() -> None:
    global _running
    _running = False


# =========================================================================
# Dispatch + DLQ
# =========================================================================

async def _dispatch(topic: str, payload: dict, message_key: Optional[bytes]) -> None:
    # G5 dedup — same pattern as orchestrator/consumers/pipeline_consumer.
    # The mark_processed write is system-level; intentional raw pool.acquire().
    if message_key is not None:
        event_id = message_key.decode()
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await mark_processed(conn, event_id, CONSUMER_GROUP)
        except DuplicateEvent:
            log.info("gold.consumer.duplicate_skipped",
                     event_id=event_id, topic=topic)
            return

    enterprise_id = payload.get("enterprise_id")
    if not enterprise_id:
        log.warning("gold.consumer.missing_enterprise_id", payload=payload)
        return

    # Fire-and-don't-wait so a slow aggregator doesn't block the next
    # message — the aggregator itself is idempotent so worst case is one
    # extra pass per redelivery.
    asyncio.create_task(_run_aggregate_safely(enterprise_id))


async def _run_aggregate_safely(enterprise_id: str) -> None:
    try:
        await aggregate_for_tenant(enterprise_id)
    except Exception as exc:
        log.error("gold.consumer.aggregate_failed",
                  enterprise_id=enterprise_id, error=str(exc))


async def _send_dlq(producer: AIOKafkaProducer, payload: dict, reason: str) -> bool:
    """Forward a failed message to the DLQ topic.

    Returns True on success, False on failure. The caller uses the result
    to decide whether to advance the consumer offset — a False return keeps
    the original message in the queue for the next poll attempt instead of
    losing it after a DLQ outage.
    """
    try:
        await producer.send_and_wait(DLQ_TOPIC, {
            "original_payload": payload,
            "error_reason":     reason,
            "consumer_group":   CONSUMER_GROUP,
        })
        return True
    except Exception as exc:
        log.error("gold.consumer.dlq_send_failed", error=str(exc))
        return False
