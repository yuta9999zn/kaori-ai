"""
Tests for shared.audit (K-6 decision_audit_log helper).

Verifies:
  - happy path INSERT goes through with the expected SQL + params;
  - missing / malformed enterprise_id is dropped with a warning,
    never raises;
  - DB error is swallowed (best-effort guarantee);
  - long text fields are truncated;
  - the write goes through ``acquire_for_tenant`` so the RLS GUC
    (``app.enterprise_id``) is set — otherwise the FORCED row-level
    policy on decision_audit_log fails with
    ``invalid input syntax for type uuid: ""`` (K-1).
"""
from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.shared import audit


class _FakeAcquire:
    """Stand-in for ``acquire_for_tenant``: callable that returns an async
    context manager yielding ``conn``. Records the tenant ids it was
    called with so tests can assert the write was (or wasn't) attempted."""

    def __init__(self, conn, raise_on_enter: Exception | None = None):
        self.conn = conn
        self.raise_on_enter = raise_on_enter
        self.calls: list[str] = []

    def __call__(self, enterprise_id):
        self.calls.append(enterprise_id)
        return self

    async def __aenter__(self):
        if self.raise_on_enter is not None:
            raise self.raise_on_enter
        return self.conn

    async def __aexit__(self, *exc):
        return False


def _conn():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    return conn


# ─── Happy path ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inserts_row_with_normalised_uuids():
    conn = _conn()
    acq = _FakeAcquire(conn)

    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", acq):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            run_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            decision_type="llm_call",
            subject="insight",
            chosen_value="some result",
            method="internal",
            llm_provider="qwen2.5:14b",
            reasoning="prompt_chars=42 response_chars=137",
        )

    # Write went through the tenant-scoped connection (RLS GUC set).
    assert acq.calls == ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    sql = args[0]
    assert "INSERT INTO decision_audit_log" in sql
    # enterprise_id and run_id are converted to UUID objects before SQL
    from uuid import UUID
    assert isinstance(args[1], UUID)
    assert isinstance(args[2], UUID)
    assert args[3] == "llm_call"      # decision_type
    assert args[4] == "insight"       # subject
    assert args[5] == "some result"   # chosen_value


@pytest.mark.asyncio
async def test_run_id_is_optional_and_nulled():
    conn = _conn()
    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", _FakeAcquire(conn)):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="llm_call",
            subject="insight",
        )
    args = conn.execute.await_args.args
    assert args[2] is None  # run_id


# ─── Skip cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skips_when_enterprise_id_missing():
    conn = _conn()
    acq = _FakeAcquire(conn)
    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", acq):
        await audit.log_decision(
            enterprise_id="",
            decision_type="llm_call",
            subject="x",
        )
    assert acq.calls == []            # never opened a connection
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_enterprise_id_invalid_uuid():
    conn = _conn()
    acq = _FakeAcquire(conn)
    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", acq):
        await audit.log_decision(
            enterprise_id="not-a-uuid",
            decision_type="llm_call",
            subject="x",
        )
    assert acq.calls == []
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_pool_uninitialised():
    """If acquire_for_tenant raises (lifespan never started), the audit call
    must still return cleanly — never propagate the error."""
    conn = _conn()
    acq = _FakeAcquire(conn, raise_on_enter=RuntimeError("DB pool not initialized"))
    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", acq):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="llm_call",
            subject="x",
        )
    # Returns None, no exception — test passes by reaching this line.


# ─── Best-effort guarantee ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_db_error_is_swallowed():
    """K-6 audit must never break the caller's primary path."""
    conn = _conn()
    conn.execute = AsyncMock(side_effect=Exception("connection refused"))

    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", _FakeAcquire(conn)):
        # Should NOT raise.
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="llm_call",
            subject="x",
        )


# ─── Truncation ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_long_chosen_value_is_truncated():
    conn = _conn()
    big = "x" * 10_000
    with patch("ai_orchestrator.shared.audit.acquire_for_tenant", _FakeAcquire(conn)):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="llm_call",
            subject="big",
            chosen_value=big,
        )
    chosen_value = conn.execute.await_args.args[5]
    assert len(chosen_value) <= 4100  # 4000 + truncation marker
    assert chosen_value.endswith("...[truncated]")
