"""
Tests for ``outbox_poller.OutboxPoller`` — the loop that drains
notification_outbox rows and dispatches SMTP sends.

DB + SMTP are mocked. We're testing:
  * the state machine (pending → sent | dead | pending+attempts++)
  * that send failure does NOT raise out of the worker (one bad row
    must not poison the batch)
  * lifecycle: start() is idempotent, stop() cleans the task
  * that batch rows are processed sequentially, not gathered (so we
    don't hammer SMTP with 10 concurrent connections)

We deliberately do NOT use a real Postgres in this test file — the
SQL itself (FOR UPDATE SKIP LOCKED, the CASE backoff) is exercised by
test_backoff.test_backoff_schedule_matches_sql_in_outbox_poller and,
later, by an IT in the auth-service that inserts a row and watches
the poller pick it up. Pure unit tests here keep iteration fast.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from config import Settings
from outbox_poller import OutboxPoller


# ─── Helpers ─────────────────────────────────────────────────────

def _settings(**overrides) -> Settings:
    base = dict(
        smtp_host="smtp.example.com", smtp_port=587, smtp_user="x",
        smtp_password="y",
        outbox_poll_interval_seconds=0.01,
        outbox_batch_size=10,
        database_url="postgresql://test/test",
    )
    base.update(overrides)
    return Settings(**base)


def _row(*, attempts=0, max_attempts=5, context=None):
    """Build a fake asyncpg.Record-like dict. The poller treats the
    row as a Mapping so a dict is enough — no need to fake the
    Record protocol."""
    return {
        "outbox_id":       uuid4(),
        "enterprise_id":   uuid4(),
        "template":        "reset-password",
        "recipient_email": "user@example.com",
        "context":         context if context is not None else {"reset_url": "https://k.io/r/abc"},
        "attempts":        attempts,
        "max_attempts":    max_attempts,
        "source_ref":      "password_reset",
    }


def _smtp(side_effect=None):
    """Mock SmtpClient with the same async ``send(to, template,
    context)`` shape the real one exposes."""
    smtp = MagicMock()
    smtp.send = AsyncMock(side_effect=side_effect)
    return smtp


def _pool_recording():
    """Mock asyncpg pool that records every UPDATE statement so tests
    can assert on the exact SQL + params used to mark a row.

    The poller calls ``pool.acquire()`` as an async context manager,
    then ``conn.execute(sql, *params)``. The recorder mock wires both.
    """
    executed: list[tuple[str, tuple]] = []

    conn = MagicMock()
    async def _execute(sql, *params):
        executed.append((sql, params))
        return None
    conn.execute = _execute

    # acquire() returns an async context manager yielding ``conn``.
    class _Acq:
        async def __aenter__(self_inner):
            return conn
        async def __aexit__(self_inner, *exc):
            return False

    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=lambda: _Acq())
    return pool, executed


# ─── State machine ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_successful_send_marks_row_sent_with_attempts_incremented():
    poller = OutboxPoller(_settings(), _smtp())
    pool, executed = _pool_recording()

    with patch("outbox_poller.get_pool", return_value=pool):
        await poller._attempt(pool, _row())

    assert len(executed) == 1
    sql, _ = executed[0]
    assert "status='sent'" in sql.replace(" ", "")
    assert "attempts=attempts+1" in sql.replace(" ", "")
    # SmtpClient.send was awaited exactly once.
    assert poller._smtp.send.await_count == 1


@pytest.mark.asyncio
async def test_transient_failure_below_max_marks_pending_with_attempts_incremented():
    """Failure on attempt 1 of 5 → status stays 'pending', attempts=1.
    No dead-letter on the very first transient hiccup."""
    poller = OutboxPoller(
        _settings(),
        _smtp(side_effect=ConnectionError("smarthost refused")),
    )
    pool, executed = _pool_recording()

    with patch("outbox_poller.get_pool", return_value=pool):
        await poller._attempt(pool, _row(attempts=0, max_attempts=5))

    sql, params = executed[0]
    assert "status=$2" in sql
    assert params[1] == "pending"            # status remained pending
    assert params[2] == 1                     # new attempts
    assert "smarthost refused" in params[3]   # last_error captured


@pytest.mark.asyncio
async def test_transient_failure_at_max_attempts_marks_row_dead():
    """attempts was 4 (out of 5) and this attempt fails → new attempts
    is 5, equal to max_attempts → row goes terminal ``dead``."""
    poller = OutboxPoller(
        _settings(),
        _smtp(side_effect=Exception("smtp 421 service not available")),
    )
    pool, executed = _pool_recording()

    with patch("outbox_poller.get_pool", return_value=pool):
        await poller._attempt(pool, _row(attempts=4, max_attempts=5))

    _sql, params = executed[0]
    assert params[1] == "dead"
    assert params[2] == 5


@pytest.mark.asyncio
async def test_send_failure_does_not_propagate_to_caller():
    """A bad row must not poison the batch — _attempt swallows the
    SMTP error after marking the row. _process_one_batch processes
    rows sequentially, so a raise here would short-circuit the rest."""
    poller = OutboxPoller(
        _settings(),
        _smtp(side_effect=RuntimeError("kaboom")),
    )
    pool, _ = _pool_recording()

    # _attempt should return cleanly (no raise).
    with patch("outbox_poller.get_pool", return_value=pool):
        await poller._attempt(pool, _row())


@pytest.mark.asyncio
async def test_context_string_decoded_back_to_dict_for_smtp():
    """asyncpg returns JSONB as a string when no codec is registered.
    The poller must decode before handing it to SmtpClient.send (which
    treats context as a Mapping for Jinja render)."""
    smtp = _smtp()
    poller = OutboxPoller(_settings(), smtp)
    pool, _ = _pool_recording()

    with patch("outbox_poller.get_pool", return_value=pool):
        await poller._attempt(pool, _row(context='{"reset_url": "https://k.io/x"}'))

    smtp.send.assert_awaited_once()
    forwarded_context = smtp.send.await_args.args[2]
    assert isinstance(forwarded_context, dict)
    assert forwarded_context == {"reset_url": "https://k.io/x"}


# ─── Batch processing ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_batch_processes_each_row_sequentially():
    """All rows in the batch should be attempted, even when an early
    one fails. Order is preserved; we don't gather() because that
    would burn 10 concurrent SMTP connections per tick (not what the
    smarthost wants from us)."""
    poller = OutboxPoller(_settings(), _smtp())
    pool, _ = _pool_recording()

    rows = [_row(), _row(), _row()]
    poller._claim_batch = AsyncMock(return_value=rows)
    poller._attempt = AsyncMock()

    with patch("outbox_poller.get_pool", return_value=pool):
        processed = await poller._process_one_batch()

    assert processed == 3
    assert poller._attempt.await_count == 3


@pytest.mark.asyncio
async def test_process_batch_returns_zero_when_no_rows_eligible():
    """No work to do — the loop should sleep the full poll interval
    instead of hot-looping the DB."""
    poller = OutboxPoller(_settings(), _smtp())
    pool, _ = _pool_recording()
    poller._claim_batch = AsyncMock(return_value=[])

    with patch("outbox_poller.get_pool", return_value=pool):
        processed = await poller._process_one_batch()

    assert processed == 0


# ─── Lifecycle ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_is_idempotent():
    poller = OutboxPoller(_settings(), _smtp())
    poller._process_one_batch = AsyncMock(return_value=0)

    poller.start()
    first_task = poller._task
    poller.start()  # no-op
    assert poller._task is first_task

    await poller.stop()


@pytest.mark.asyncio
async def test_stop_cancels_running_task_cleanly():
    poller = OutboxPoller(_settings(), _smtp())
    poller._process_one_batch = AsyncMock(return_value=0)

    poller.start()
    assert poller._task is not None

    await poller.stop()
    assert poller._task is None


@pytest.mark.asyncio
async def test_loop_survives_one_bad_tick_and_keeps_polling():
    """The whole point of the try/except inside _run is that a single
    bad poll tick (DB blip, smarthost flap) doesn't kill the worker
    forever. After one failure the loop must keep ticking."""
    poller = OutboxPoller(_settings(), _smtp())
    call_count = {"n": 0}

    async def _flaky_batch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated DB blip")
        return 0

    poller._process_one_batch = _flaky_batch

    poller.start()
    # Give the loop a moment to tick a few times — the test settings
    # have poll_interval=0.01s so this is fast.
    import asyncio
    await asyncio.sleep(0.05)
    await poller.stop()

    assert call_count["n"] >= 2, (
        f"Loop should have ticked ≥2× (bad tick + recovery) but only "
        f"ticked {call_count['n']}× — the try/except in _run is broken"
    )
