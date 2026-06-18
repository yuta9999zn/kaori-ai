"""
Unit tests for shared.outbox (G5).

These exercise the helpers' contract using mocked asyncpg objects so
they run without a live Postgres or Kafka. The end-to-end "real
Kafka actually receives the event" check happens in the validation
script invoked manually after docker-compose up.
"""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import asyncpg
import pytest

from data_pipeline.shared import outbox


# ---------------------------------------------------------------------------
# enqueue_event — produce side
# ---------------------------------------------------------------------------

# A reusable payload that matches the kaori.pipeline.upload.received
# JSON schema. Used by every enqueue_event test below — Issue #4 added
# validate_event() inside enqueue_event, so a bare {} or fake topic
# would trip the validator before reaching the SQL we're trying to
# verify.
_VALID_UPLOAD_PAYLOAD = {
    "run_id":        "11111111-1111-1111-1111-111111111111",
    "enterprise_id": "22222222-2222-2222-2222-222222222222",
    "filename":      "demo.xlsx",
    "sha256":        "a" * 64,
    "size_bytes":    12345,
}


@pytest.mark.asyncio
async def test_enqueue_event_inserts_with_payload_and_returns_id():
    expected_id = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"outbox_id": expected_id})

    eid = uuid4()
    out = await outbox.enqueue_event(
        conn, eid, "kaori.pipeline.upload.received", "upload.received",
        _VALID_UPLOAD_PAYLOAD,
    )
    assert out == expected_id
    args = conn.fetchrow.await_args.args
    sql = args[0]
    assert "INSERT INTO event_outbox" in sql
    assert "RETURNING outbox_id" in sql
    # Param order: enterprise_id, topic, event_type, payload(json)
    assert args[1] == eid
    assert args[2] == "kaori.pipeline.upload.received"
    assert args[3] == "upload.received"
    assert json.loads(args[4]) == _VALID_UPLOAD_PAYLOAD


@pytest.mark.asyncio
async def test_enqueue_event_accepts_string_uuid():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"outbox_id": uuid4()})
    await outbox.enqueue_event(
        conn, "11111111-1111-1111-1111-111111111111",
        "kaori.pipeline.upload.received", "upload.received",
        _VALID_UPLOAD_PAYLOAD,
    )
    args = conn.fetchrow.await_args.args
    assert args[1] == UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_enqueue_event_rejects_payload_missing_required_field():
    """Issue #4 — bad payload at the producer is now caught here, not
    three hops downstream in a consumer log. The caller's transaction
    rolls back on the InvalidEventError raise.

    The import path matters: this test uses ``data_pipeline.shared``
    (matching the rest of the file) so the InvalidEventError class
    object matches the one ``outbox.py`` raises. Importing via the
    bare ``shared.event_schema`` would load the same module twice
    under different qualified names and ``pytest.raises`` would miss
    the match."""
    from data_pipeline.shared.event_schema import InvalidEventError

    conn = AsyncMock()
    bad_payload = dict(_VALID_UPLOAD_PAYLOAD)
    del bad_payload["sha256"]  # required

    with pytest.raises(InvalidEventError) as exc:
        await outbox.enqueue_event(
            conn, uuid4(), "kaori.pipeline.upload.received",
            "upload.received", bad_payload,
        )
    assert "sha256" in exc.value.reason
    # The SQL never ran — proves we fail-fast BEFORE the INSERT.
    conn.fetchrow.assert_not_called()


# ---------------------------------------------------------------------------
# OutboxPublisher — relay
# ---------------------------------------------------------------------------

def _make_pool(rows_to_return):
    """Build a pool whose acquire().__aenter__() yields a conn that
    returns `rows_to_return` from fetch and counts execute calls.
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows_to_return)
    conn.execute = AsyncMock(return_value=None)

    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool, conn


@pytest.mark.asyncio
async def test_publish_batch_returns_zero_when_no_pending_rows():
    pool, conn = _make_pool([])
    producer = AsyncMock()
    pub = outbox.OutboxPublisher(pool, producer)

    n = await pub._publish_batch()
    assert n == 0
    producer.send_and_wait.assert_not_called()


@pytest.mark.asyncio
async def test_publish_batch_sends_each_row_with_outbox_id_as_key_and_marks_published():
    oid1, oid2 = uuid4(), uuid4()
    rows = [
        {"outbox_id": oid1, "topic": "t1", "payload": '{"a":1}'},
        {"outbox_id": oid2, "topic": "t2", "payload": '{"b":2}'},
    ]
    pool, conn = _make_pool(rows)
    producer = AsyncMock()
    producer.send_and_wait = AsyncMock(return_value=None)
    pub = outbox.OutboxPublisher(pool, producer)

    n = await pub._publish_batch()
    assert n == 2

    # Each row got sent with its outbox_id as the Kafka message key.
    calls = producer.send_and_wait.await_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == "t1"
    assert calls[0].kwargs["value"] == {"a": 1}
    assert calls[0].kwargs["key"] == str(oid1).encode()
    assert calls[1].kwargs["key"] == str(oid2).encode()

    # Each row also got an UPDATE published_at = NOW().
    update_calls = [
        c for c in conn.execute.await_args_list
        if "UPDATE event_outbox SET published_at" in c.args[0]
    ]
    assert len(update_calls) == 2


@pytest.mark.asyncio
async def test_publish_batch_records_error_and_does_not_mark_published_on_send_failure():
    oid = uuid4()
    rows = [{"outbox_id": oid, "topic": "t", "payload": "{}"}]
    pool, conn = _make_pool(rows)
    producer = AsyncMock()
    producer.send_and_wait = AsyncMock(side_effect=RuntimeError("kafka down"))
    pub = outbox.OutboxPublisher(pool, producer)

    n = await pub._publish_batch()
    # Failure does not count as published; relay will retry next poll.
    assert n == 0

    # Row got attempts incremented with the error message.
    error_updates = [
        c for c in conn.execute.await_args_list
        if "attempts = attempts + 1" in c.args[0]
    ]
    assert len(error_updates) == 1
    assert error_updates[0].args[2] == "kafka down"

    # Critically: no published_at update was issued.
    published_updates = [
        c for c in conn.execute.await_args_list
        if "SET published_at" in c.args[0]
    ]
    assert published_updates == []


@pytest.mark.asyncio
async def test_publish_batch_uses_for_update_skip_locked_so_concurrent_workers_are_safe():
    pool, conn = _make_pool([])
    pub = outbox.OutboxPublisher(pool, AsyncMock())
    await pub._publish_batch()

    sql = conn.fetch.await_args.args[0]
    # The lock-and-skip is the whole point of allowing >1 instance.
    assert "FOR UPDATE SKIP LOCKED" in sql, sql
    assert "WHERE published_at IS NULL" in sql, sql
    assert "ORDER BY created_at" in sql, sql


# ---------------------------------------------------------------------------
# mark_processed — consume side
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_processed_inserts_event_id_and_consumer_group():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    eid = uuid4()
    await outbox.mark_processed(conn, eid, "kaori-orchestrator")
    args = conn.execute.await_args.args
    assert "INSERT INTO processed_events" in args[0]
    assert args[1] == eid
    assert args[2] == "kaori-orchestrator"


@pytest.mark.asyncio
async def test_mark_processed_raises_DuplicateEvent_on_unique_violation():
    conn = AsyncMock()

    # Build a real-looking UniqueViolationError. asyncpg's exception
    # constructor takes complex args; the simplest reliable mock is
    # to subclass it.
    class _UV(asyncpg.UniqueViolationError):
        pass

    conn.execute = AsyncMock(side_effect=_UV("dup"))
    with pytest.raises(outbox.DuplicateEvent):
        await outbox.mark_processed(conn, uuid4(), "g")


@pytest.mark.asyncio
async def test_mark_processed_accepts_string_uuid():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    await outbox.mark_processed(conn, "22222222-2222-2222-2222-222222222222", "g")
    args = conn.execute.await_args.args
    assert args[1] == UUID("22222222-2222-2222-2222-222222222222")
