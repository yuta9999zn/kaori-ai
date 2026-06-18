"""
Transactional outbox helpers (G5).

The contract:

  Producer side
  -------------
  Inside the SAME transaction that writes business data, call
  ``enqueue_event(conn, enterprise_id, topic, event_type, payload)``.
  Both the business row and the outbox row commit together — or
  neither does. No more silent dual-write loss.

      async with pool.acquire() as conn:
          async with conn.transaction():
              await conn.execute("INSERT INTO pipeline_runs ...")
              await enqueue_event(
                  conn,
                  enterprise_id,
                  kafka_topics.PIPELINE_UPLOAD_RECEIVED,
                  event_type="upload.received",
                  payload={"run_id": str(run_id), ...},
              )

  A background ``OutboxPublisher`` loop (started in main.py's
  lifespan) polls event_outbox WHERE published_at IS NULL, sends each
  row to Kafka with the outbox_id as the message key, and marks
  published_at. ``FOR UPDATE SKIP LOCKED`` lets multiple service
  instances share the work without contention.

  Delivery is at-least-once: if the relay crashes between the Kafka
  send and the published_at UPDATE, the row stays unpublished and
  gets re-sent next poll. Consumers MUST dedupe — see
  ``mark_processed`` below.

  Consumer side
  -------------
  Wrap each event's handler in a transaction; first call
  ``mark_processed(conn, event_id, consumer_group)``. If it raises
  ``DuplicateEvent`` the event has already been handled by a prior
  delivery — log and skip. Otherwise proceed with the business work
  in the same transaction; rollback on failure leaves processed_events
  empty so the next delivery retries cleanly.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional, Union
from uuid import UUID

import asyncpg
import structlog
from opentelemetry import trace

log = structlog.get_logger()


def _current_trace_context() -> Optional[dict]:
    """Capture the active span as a W3C traceparent so the consumer
    on the other side of Kafka can continue the trace.

    Returns ``None`` when no span is active (background callers, tests
    with tracing off) — the column accepts NULL.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx is None or not ctx.is_valid:
        return None
    # W3C: ``version-trace_id-span_id-flags`` (RFC editor's draft).
    return {
        "traceparent": "00-{trace_id:032x}-{span_id:016x}-{flags:02x}".format(
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            flags=int(ctx.trace_flags) & 0xFF,
        ),
    }


# ============================================================
# PRODUCE SIDE
# ============================================================

async def enqueue_event(
    conn: asyncpg.Connection,
    enterprise_id: Union[str, UUID],
    topic: str,
    event_type: str,
    payload: dict,
) -> UUID:
    """Insert one outbox row in the caller's transaction; return its id.

    Caller is responsible for the surrounding ``async with
    conn.transaction():`` so the outbox row commits atomically with
    the business write.

    Issue #4 — payload is validated against the JSON schema at
    ``infrastructure/kafka/schemas/<topic>.json`` before INSERT. A
    missing required field or wrong type raises
    ``InvalidEventError`` from ``shared.event_schema``; the
    surrounding transaction rolls back and the bug surfaces at the
    producer site instead of three hops later in a consumer log.
    Unknown topics raise ``UnknownTopicError`` for the same reason —
    a typo'd topic constant should fail loud.
    """
    from .event_schema import validate_event  # local import to keep circular-safe
    validate_event(topic, payload)

    eid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))
    # Phase 2 #2/#5 — store the current trace context with the row so the
    # OutboxReconciliationJob (auth-service, 02:30 ICT) can include it when
    # warning about stale rows. The aiokafka producer injects W3C headers
    # automatically via OTel auto-instrumentation; the DB copy is for
    # operator visibility (SELECT outbox_id, trace_context->>'traceparent' …).
    tc = _current_trace_context()
    row = await conn.fetchrow(
        """
        INSERT INTO event_outbox (enterprise_id, topic, event_type, payload, trace_context)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
        RETURNING outbox_id
        """,
        eid,
        topic,
        event_type,
        json.dumps(payload, default=str),
        json.dumps(tc) if tc is not None else None,
    )
    return row["outbox_id"]


# ============================================================
# RELAY — moves outbox rows into Kafka
# ============================================================

class OutboxPublisher:
    """Background poll loop that ships pending outbox rows to Kafka.

    Constructor takes the asyncpg pool and an aiokafka producer (or
    anything with ``async send_and_wait(topic, value, key=...)``).
    Call ``start()`` in lifespan startup, ``stop()`` in shutdown.

    Tunables:
      poll_interval — seconds between polls when the previous batch
                      was empty. Defaults to 1.0; on a busy queue we
                      drain a batch then immediately poll again.
      batch_size    — max rows per poll cycle. Keeps the FOR UPDATE
                      SKIP LOCKED window bounded.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        producer,
        *,
        poll_interval: float = 1.0,
        batch_size: int = 100,
    ):
        self._pool = pool
        self._producer = producer
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="outbox-publisher")
        log.info("outbox.publisher.started", batch_size=self._batch_size)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("outbox.publisher.stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                published = await self._publish_batch()
            except Exception as exc:
                log.error("outbox.publisher.batch_error", error=str(exc))
                published = 0
            # Empty batch ⇒ wait. Non-empty ⇒ keep draining.
            if published == 0:
                try:
                    await asyncio.sleep(self._poll_interval)
                except asyncio.CancelledError:
                    break

    async def _publish_batch(self) -> int:
        """Process up to batch_size pending rows. Returns count published."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    SELECT outbox_id, topic, payload
                    FROM event_outbox
                    WHERE published_at IS NULL
                    ORDER BY created_at
                    LIMIT $1
                    FOR UPDATE SKIP LOCKED
                    """,
                    self._batch_size,
                )
                if not rows:
                    return 0

                published = 0
                for row in rows:
                    outbox_id = row["outbox_id"]
                    topic = row["topic"]
                    payload = json.loads(row["payload"])
                    try:
                        await self._producer.send_and_wait(
                            topic,
                            value=payload,
                            key=str(outbox_id).encode(),
                        )
                    except Exception as exc:
                        log.error(
                            "outbox.publisher.send_failed",
                            outbox_id=str(outbox_id),
                            topic=topic,
                            error=str(exc),
                        )
                        await conn.execute(
                            """
                            UPDATE event_outbox
                               SET attempts = attempts + 1, last_error = $2
                             WHERE outbox_id = $1
                            """,
                            outbox_id,
                            str(exc),
                        )
                        continue

                    await conn.execute(
                        "UPDATE event_outbox SET published_at = NOW() WHERE outbox_id = $1",
                        outbox_id,
                    )
                    published += 1

                if published:
                    log.info("outbox.publisher.batch", published=published)
                return published


# ============================================================
# CONSUME SIDE
# ============================================================

class DuplicateEvent(Exception):
    """Raised by ``mark_processed`` when (event_id, consumer_group) was
    already recorded — i.e. this is a redelivery of an event we've
    already handled. Caller should log and skip the business work.
    """


async def mark_processed(
    conn: asyncpg.Connection,
    event_id: Union[str, UUID],
    consumer_group: str,
) -> None:
    """Idempotence primitive — call inside the consumer's txn before
    doing the work. Raises DuplicateEvent on redelivery.

    Use the Kafka message key (the producer-side outbox_id) as
    event_id for end-to-end dedupe.
    """
    eid = event_id if isinstance(event_id, UUID) else UUID(str(event_id))
    try:
        await conn.execute(
            "INSERT INTO processed_events (event_id, consumer_group) VALUES ($1, $2)",
            eid,
            consumer_group,
        )
    except asyncpg.UniqueViolationError as e:
        raise DuplicateEvent(f"event {eid} already processed by {consumer_group}") from e
