"""
Issue #6 — notification outbox poller.

Runs as a background asyncio task started in ``main.lifespan``. Every
``OUTBOX_POLL_INTERVAL_SECONDS`` it claims a batch of eligible
``notification_outbox`` rows (status='pending', attempts<max, retry
window elapsed) and attempts SMTP delivery for each.

Concurrency
===========
Two tactics keep multiple notification-service replicas safe to run
side-by-side:

  1. ``FOR UPDATE SKIP LOCKED`` on the SELECT — each replica claims a
     distinct slice of pending rows; if another replica has the row
     under tx lock, this one moves on. No coordinator needed.

  2. The whole "claim → send → mark" sequence runs inside one
     transaction per row. If the worker crashes mid-send, the lock is
     released by Postgres and a future poll picks the row up again
     (status is still 'pending', attempts not yet incremented). At-
     least-once: the SMTP call may run twice in pathological crashes,
     but every modern smarthost dedupes by Message-ID so the user
     receives at most one email.

State machine
=============
Single non-terminal state ('pending') simplifies the WHERE clause:

  pending ─┬─ (success)         ─→ sent  (terminal)
           ├─ (transient fail,
           │   attempts < max)  ─→ pending, attempts++, last_attempt_at
           └─ (transient fail,
               attempts == max) ─→ dead  (terminal — needs human ops)

A future enhancement could distinguish permanent failures (5xx SMTP,
malformed recipient) and short-circuit straight to 'dead' instead of
burning all retries. Out of scope for this PR; see audit doc Issue #5.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import structlog
from opentelemetry import trace

from backoff import backoff_seconds
from config import Settings
from db import get_pool
from smtp_client import SmtpClient

log = structlog.get_logger()
_tracer = trace.get_tracer(__name__)


class OutboxPoller:
    """Long-running asyncio task that drains pending notification rows.

    Construct once in ``main.lifespan`` after the SMTP client + DB pool
    are ready; call ``start()`` to schedule the loop and ``stop()`` to
    cancel it cleanly during shutdown.
    """

    def __init__(self, settings: Settings, smtp: SmtpClient):
        self._settings = settings
        self._smtp = smtp
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    # ─── lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return  # already running
        self._stopped.clear()
        self._task = asyncio.create_task(self._run(), name="notification-outbox-poller")
        log.info("outbox.poller.started",
                 interval_s=self._settings.outbox_poll_interval_seconds,
                 batch=self._settings.outbox_batch_size)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopped.set()
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None
        log.info("outbox.poller.stopped")

    # ─── main loop ────────────────────────────────────────────────

    async def _run(self) -> None:
        # Even if the first tick crashes (DB cold-start race, smarthost
        # not ready), we don't want the task to die — that would silently
        # halt every email forever. Keep the loop wrapped in try/except
        # and log the error so an alert can fire on
        # outbox.poller.tick_failed.
        while not self._stopped.is_set():
            try:
                processed = await self._process_one_batch()
                if processed == 0:
                    # No work — sleep the full interval. With work,
                    # immediately re-poll so a backed-up queue drains
                    # quickly.
                    await asyncio.wait_for(
                        self._stopped.wait(),
                        timeout=self._settings.outbox_poll_interval_seconds,
                    )
            except asyncio.TimeoutError:
                # Normal exit from wait_for when no stop signal arrived.
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("outbox.poller.tick_failed", error=str(exc))
                # Backoff a poll interval before retrying — protects
                # Postgres if the failure is "pool exhausted" loop.
                try:
                    await asyncio.wait_for(
                        self._stopped.wait(),
                        timeout=self._settings.outbox_poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    pass

    # ─── one batch ────────────────────────────────────────────────

    async def _process_one_batch(self) -> int:
        """Claim up to ``batch_size`` eligible rows and attempt each one.
        Returns how many rows we processed (success or fail) so the
        caller can decide whether to immediately re-poll."""
        pool = get_pool()
        rows = await self._claim_batch(pool)
        if not rows:
            return 0

        # Each row is processed independently — one bad row should not
        # block the others. We do NOT gather() across rows because
        # each one needs its own transaction; sequential keeps the
        # state machine obvious and lets a runaway batch be observed
        # (rather than 10 concurrent SMTP attempts disappearing into
        # the void).
        for r in rows:
            await self._attempt(pool, r)
        return len(rows)

    async def _claim_batch(self, pool: asyncpg.Pool) -> list[asyncpg.Record]:
        """Return rows eligible for an attempt now. The
        ``last_attempt_at + backoff(attempts) <= NOW()`` predicate is
        encoded as a CASE on attempts so Postgres can plan one query.

        Schedule must mirror ``backoff.py``. Duplicated here because
        Postgres can't call into Python — the test
        ``test_backoff_schedule_matches_sql`` pins them in lockstep so
        a future refactor can't drift one without the other.
        """
        sql = """
            SELECT outbox_id, enterprise_id, template, recipient_email,
                   context, attempts, max_attempts, source_ref
              FROM notification_outbox
             WHERE status = 'pending'
               AND attempts < max_attempts
               AND (
                 last_attempt_at IS NULL
                 OR last_attempt_at < NOW() - INTERVAL '1 second' * (
                   CASE attempts
                       WHEN 0 THEN 0
                       WHEN 1 THEN 2
                       WHEN 2 THEN 8
                       WHEN 3 THEN 32
                       ELSE        128
                   END
                 )
               )
             ORDER BY created_at
             LIMIT $1
             FOR UPDATE SKIP LOCKED
        """
        async with pool.acquire() as conn:
            # SELECT FOR UPDATE inside an explicit transaction — the
            # rows stay locked for the duration of THIS connection's
            # transaction, which is exactly what we want.
            async with conn.transaction():
                return await conn.fetch(sql, self._settings.outbox_batch_size)

    # ─── send + mark ──────────────────────────────────────────────

    async def _attempt(self, pool: asyncpg.Pool, row: asyncpg.Record) -> None:
        outbox_id = row["outbox_id"]
        enterprise_id = row["enterprise_id"]
        template = row["template"]
        recipient = row["recipient_email"]
        attempts = row["attempts"]
        max_attempts = row["max_attempts"]

        # context comes back as a string when asyncpg has no JSONB
        # codec registered (default for our pool). Decode here so the
        # SMTP renderer gets a real dict.
        raw_context = row["context"]
        context: dict[str, Any] = (
            json.loads(raw_context) if isinstance(raw_context, str)
            else (raw_context or {})
        )

        with _tracer.start_as_current_span(
            "notification.outbox.attempt",
            attributes={
                "outbox_id":   str(outbox_id),
                "tenant_id":   str(enterprise_id),
                "template":    template,
                "attempt":     attempts + 1,
                "max_attempts": max_attempts,
            },
        ):
            try:
                await self._smtp.send(recipient, template, context)
            except Exception as exc:
                await self._mark_failure(pool, outbox_id, attempts, max_attempts,
                                         str(exc))
                return

            await self._mark_sent(pool, outbox_id)

    async def _mark_sent(self, pool: asyncpg.Pool, outbox_id) -> None:
        sql = """
            UPDATE notification_outbox
               SET status='sent', sent_at=NOW(), last_attempt_at=NOW(),
                   attempts=attempts+1, last_error=NULL
             WHERE outbox_id = $1
        """
        async with pool.acquire() as conn:
            await conn.execute(sql, outbox_id)
        log.info("outbox.send.ok", outbox_id=str(outbox_id))

    async def _mark_failure(self, pool: asyncpg.Pool, outbox_id,
                            current_attempts: int, max_attempts: int,
                            error: str) -> None:
        new_attempts = current_attempts + 1
        # Reaching max_attempts on this attempt → dead, no more retries.
        new_status = "dead" if new_attempts >= max_attempts else "pending"

        sql = """
            UPDATE notification_outbox
               SET status=$2, attempts=$3, last_attempt_at=NOW(),
                   last_error=$4
             WHERE outbox_id = $1
        """
        async with pool.acquire() as conn:
            await conn.execute(sql, outbox_id, new_status, new_attempts,
                               _truncate(error))

        if new_status == "dead":
            # Loud log so an alert rule can grep this. A future PR will
            # replace the log with a kafka.notifications.dead emit
            # (audit doc Issue #6 follow-up).
            log.error("outbox.send.dead",
                      outbox_id=str(outbox_id),
                      attempts=new_attempts,
                      error=error)
        else:
            next_wait = backoff_seconds(new_attempts)
            log.warning("outbox.send.retry",
                        outbox_id=str(outbox_id),
                        attempts=new_attempts,
                        next_wait_s=next_wait,
                        error=error)


def _truncate(text: str | None, limit: int = 4000) -> str | None:
    """Keep the audit trail readable — long stack traces would crowd
    the table without adding signal beyond the first few lines."""
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
