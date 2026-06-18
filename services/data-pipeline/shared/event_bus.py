"""
F-NEW2 — In-process pub/sub for pipeline status SSE.

Producer call sites (clean.py, analyze.py, bronze/ingestor.py) hand a
status-transition event to ``event_bus.publish(run_id, payload)`` right
after they UPDATE ``pipeline_runs.status``. The SSE handler in
``routers/enterprise_pipelines.py`` subscribes per request and yields
each event as a ``text/event-stream`` chunk.

Why in-process and not Kafka / Redis pub/sub:
  * Phase 1 ships a single data-pipeline process per tenant tier; the
    producer (status writer) and the consumer (SSE handler) always
    share an event loop, so an asyncio queue is the simplest correct
    answer.
  * Going to Kafka would mean a new topic + a new consumer wiring +
    SSE delivery would no longer be ordered per-run-id without effort.
    The trade is worth re-evaluating in Phase 2 when the service starts
    horizontally scaling — until then this stays in-memory.

Concurrency model:
  * Each subscribe() opens its own ``asyncio.Queue`` so slow consumers
    never block fast ones (back-pressure is per-subscriber).
  * publish() never awaits — it ``put_nowait`` into every subscriber's
    queue and drops on overflow with a structured-log warning. SSE is
    advisory; the next polling fallback (``GET /upload/{run_id}/status``)
    is the source of truth.
  * No global lock is needed because all mutations of the subscriber
    set happen on the event loop thread.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import AsyncIterator
from uuid import UUID

import structlog

log = structlog.get_logger()

# Per-subscriber queue depth. 32 is enough for an SSE consumer to absorb a
# burst of status transitions without dropping; the handler drains it on
# every loop iteration so the queue almost never holds more than 1 item.
_QUEUE_MAXSIZE = 32


class EventBus:
    """Single-process fan-out keyed by ``run_id``.

    The bus is intentionally minimal — start a queue when the first
    subscriber arrives, drop the bookkeeping when the last one leaves so
    publish() to a run with no listeners is a constant-time no-op.
    """

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    @contextlib.asynccontextmanager
    async def subscribe(self, run_id: UUID | str) -> AsyncIterator[asyncio.Queue]:
        """Register a queue for ``run_id`` for the duration of the block."""
        key = str(run_id)
        queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subs.setdefault(key, set()).add(queue)
        try:
            yield queue
        finally:
            self._subs.get(key, set()).discard(queue)
            if key in self._subs and not self._subs[key]:
                del self._subs[key]

    def publish(self, run_id: UUID | str, payload: dict) -> None:
        """Fan-out a status-transition payload to every subscriber.

        Non-blocking: drops + logs a warning when a subscriber's queue is
        full. SSE is best-effort; the polling endpoint stays authoritative.
        """
        key = str(run_id)
        subs = self._subs.get(key)
        if not subs:
            return
        for queue in list(subs):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                log.warning("event_bus.queue_full",
                            run_id=key, dropped_status=payload.get("status"))

    def subscriber_count(self, run_id: UUID | str) -> int:
        """Test hook — how many open SSE streams currently watch this run."""
        return len(self._subs.get(str(run_id), set()))


# Singleton — import as ``from ..shared.event_bus import event_bus``.
event_bus = EventBus()
