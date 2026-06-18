"""
Temporal worker entrypoint — runs the registered workflows + activities.

Phase 1.5 P15-S9 D3 — the worker spawns inside the ai-orchestrator
process (lifespan-managed) so it shares the DB pool, Vault client, and
OTel context. Phase 2 P2-S19 extracts it to services/workflow-engine
where it gets its own pod + scaling tier.

Lifecycle
=========
The worker exposes a single async ``run_worker(stop_event)`` function
that registers workflows + activities, polls the configured task queue,
and exits cleanly when ``stop_event`` is set. main.py wires it as an
``asyncio.create_task(...)`` mirror of how pipeline_consumer is wired
today; cancelling the task on shutdown sets the event and the worker
shuts down within the SDK's poll cycle.

Disable flag
============
``TEMPORAL_ENABLE_WORKER`` (default 'false' Phase 1.5) gates the
worker. When the flag is false, ``run_worker()`` logs once and returns
immediately. This lets us merge the wiring without spinning a worker
in environments that haven't deployed Temporal yet — and lets us flip
it on per-environment via a single env-var change.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from .activities import ALL_ACTIVITIES
from .temporal_client import TemporalConfig, connect, reset_client
from .workflows import ALL_WORKFLOWS

log = structlog.get_logger()


async def run_worker(
    stop_event: asyncio.Event,
    config: Optional[TemporalConfig] = None,
) -> None:
    """Run the worker until stop_event is set.

    The function returns immediately if the worker is disabled by env;
    callers should still await it (no-op) so the lifespan code stays
    symmetric with other consumers.
    """
    cfg = config or TemporalConfig.from_env()

    if not cfg.enable_worker:
        log.info(
            "temporal.worker.disabled",
            reason="TEMPORAL_ENABLE_WORKER not truthy",
            address=cfg.address,
            namespace=cfg.namespace,
            task_queue=cfg.task_queue,
        )
        return

    # Lazy import — keeps `from .worker import run_worker` cheap for
    # environments that won't actually run the worker.
    from temporalio.worker import Worker

    client = await connect(cfg)

    log.info(
        "temporal.worker.starting",
        task_queue=cfg.task_queue,
        workflows=[w.__name__ for w in ALL_WORKFLOWS],
        activities=[a.__name__ for a in ALL_ACTIVITIES],
    )
    worker = Worker(
        client,
        task_queue=cfg.task_queue,
        workflows=list(ALL_WORKFLOWS),
        activities=list(ALL_ACTIVITIES),
    )

    # Worker.run() blocks until cancelled. Race it against stop_event so
    # the lifespan can request a clean shutdown without cancelling the
    # task externally (which would surface as an asyncio.CancelledError
    # in the wrong place).
    worker_task = asyncio.create_task(worker.run())
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        done, pending = await asyncio.wait(
            {worker_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop_task in done:
            log.info("temporal.worker.stop_requested")
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        # If worker_task finishes first, it likely raised — propagate.
        for t in done:
            if t is worker_task:
                exc = t.exception()
                if exc is not None:
                    raise exc
    finally:
        for t in (worker_task, stop_task):
            if not t.done():
                t.cancel()
        reset_client()
        log.info("temporal.worker.stopped")
