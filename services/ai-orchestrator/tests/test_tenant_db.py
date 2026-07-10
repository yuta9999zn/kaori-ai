"""
Tests for the G4a additive RLS scaffolding in shared.db (ai-orchestrator).

Mirrors services/data-pipeline/tests/test_tenant_db.py — same wrapper
contract; the duplicate file matches how kafka_topics + audit are
mirrored across the two services. See the data-pipeline copy's
docstring for the full motivation.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.shared import db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)

    # After mig 059 + the workspace-aware GUC bootstrap, acquire_for_tenant
    # does: execute(set_config app.enterprise_id) → fetchrow(workspace_id)
    # → execute(set_config app.current_workspace_id). The fetchrow MUST
    # return a row containing 'workspace_id' or the helper raises KeyError.
    ws_row = MagicMock()
    ws_row.__getitem__ = lambda _self, k: (
        UUID("cccccccc-cccc-cccc-cccc-cccccccccccc") if k == "workspace_id" else None
    )
    conn.fetchrow = AsyncMock(return_value=ws_row)

    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)
    return conn


@pytest.fixture
def mock_pool(mock_conn) -> MagicMock:
    @asynccontextmanager
    async def _acquire(*, timeout=None):
        yield mock_conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_for_tenant_sets_app_enterprise_id_via_set_config(mock_pool, mock_conn):
    """After mig 059 the bootstrap fires TWO execute() calls:
        1. set_config('app.enterprise_id' + 'app.current_enterprise_id')
        2. set_config('app.current_workspace_id') after workspace_id lookup
    We verify the FIRST call carries the tenant id."""
    eid = uuid4()
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as conn:
            assert conn is mock_conn

    assert mock_conn.execute.await_count == 2
    first_call = mock_conn.execute.await_args_list[0]
    sql = first_call.args[0]
    assert "set_config('app.enterprise_id'" in sql, f"unexpected SQL: {sql}"
    assert "true" in sql, f"set_config must use is_local=true: {sql}"
    assert first_call.args[1] == str(eid)


@pytest.mark.asyncio
async def test_acquire_for_tenant_runs_inside_a_transaction(mock_pool, mock_conn):
    eid = uuid4()
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as _:
            pass

    mock_conn.transaction.assert_called_once()
    tx = mock_conn.transaction.return_value
    tx.__aenter__.assert_awaited_once()
    tx.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_acquire_for_tenant_accepts_string(mock_pool, mock_conn):
    eid_str = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid_str) as _:
            pass
    # First execute carries enterprise_id (workspace_id GUC is second call)
    first_call = mock_conn.execute.await_args_list[0]
    assert first_call.args[1] == eid_str


@pytest.mark.asyncio
async def test_acquire_for_tenant_accepts_uuid_object(mock_pool, mock_conn):
    eid = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as _:
            pass
    first_call = mock_conn.execute.await_args_list[0]
    assert first_call.args[1] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_for_tenant_rejects_malformed_uuid_before_db_call(mock_pool, mock_conn):
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool):
        with pytest.raises(ValueError):
            async with db.acquire_for_tenant("not-a-uuid") as _:
                pass
    mock_conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Pool wiring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_for_tenant_raises_when_pool_uninit():
    with patch("ai_orchestrator.shared.db.get_pool",
               side_effect=RuntimeError("DB pool not initialised")):
        with pytest.raises(RuntimeError, match="not initialised"):
            async with db.acquire_for_tenant(uuid4()) as _:
                pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_conn_forwards_header_to_acquire(mock_pool, mock_conn):
    eid = uuid4()
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool):
        gen = db.tenant_conn(x_enterprise_id=eid)
        conn = await gen.__anext__()
        assert conn is mock_conn
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    first_call = mock_conn.execute.await_args_list[0]
    assert "set_config('app.enterprise_id'" in first_call.args[0]
    assert first_call.args[1] == str(eid)


# ---------------------------------------------------------------------------
# P1-MTNT-001 — log_cross_tenant_attempt helper
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pool_for_audit(mock_conn) -> MagicMock:
    """Pool that yields a mock conn with fetchrow returning {id: 42}."""
    @asynccontextmanager
    async def _acquire(*, timeout=None):
        yield mock_conn

    pool = MagicMock()
    pool.acquire = _acquire
    mock_conn.fetchrow = AsyncMock(return_value={"id": 42})
    return pool


@pytest.mark.asyncio
async def test_log_cross_tenant_attempt_calls_postgres_function(mock_pool_for_audit, mock_conn):
    """Helper must call SELECT log_rls_attempt(...) with the 8 args
    in the right order (matches migration 040 signature)."""
    guc = uuid4()
    row = uuid4()
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool_for_audit):
        result = await db.log_cross_tenant_attempt(
            guc_tenant=guc,
            row_tenant=row,
            operation="INSERT",
            table_name="public.gold_features",
            pk_value="abc-123",
            reason="rls_reject",
            detail="duplicate key violation",
            ip_address="10.0.0.1",
        )

    assert result == 42
    mock_conn.fetchrow.assert_awaited_once()
    sql, *args = mock_conn.fetchrow.await_args.args
    assert "log_rls_attempt" in sql
    assert args == [
        str(guc), str(row), "INSERT", "public.gold_features",
        "abc-123", "rls_reject", "duplicate key violation", "10.0.0.1",
    ]


@pytest.mark.asyncio
async def test_log_cross_tenant_attempt_swallows_audit_failure(mock_pool_for_audit, mock_conn):
    """If the audit insert itself fails, the helper returns None and
    logs a warning — it MUST NOT propagate. The original RLS exception
    that triggered the call is the load-bearing signal; a broken audit
    log writer must not eat it."""
    mock_conn.fetchrow = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool_for_audit):
        result = await db.log_cross_tenant_attempt(
            operation="UPDATE",
            table_name="public.foo",
        )

    assert result is None  # swallowed


@pytest.mark.asyncio
async def test_log_cross_tenant_attempt_accepts_string_uuids(mock_pool_for_audit, mock_conn):
    """Callers occasionally have UUIDs as strings (from headers, from
    error messages); helper must coerce them, not raise."""
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool_for_audit):
        await db.log_cross_tenant_attempt(
            guc_tenant="11111111-1111-1111-1111-111111111111",
            row_tenant="22222222-2222-2222-2222-222222222222",
            operation="DELETE",
            table_name="public.bar",
        )

    sql, *args = mock_conn.fetchrow.await_args.args
    assert args[0] == "11111111-1111-1111-1111-111111111111"
    assert args[1] == "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_log_cross_tenant_attempt_accepts_none_tenants(mock_pool_for_audit, mock_conn):
    """Some attempts (admin bypass, app-layer proactive checks) don't
    have both tenant ids; the helper passes NULLs through to Postgres."""
    with patch("ai_orchestrator.shared.db.get_pool", return_value=mock_pool_for_audit):
        await db.log_cross_tenant_attempt(
            operation="SELECT",
            table_name="public.workspaces",
            reason="admin_bypass",
        )

    sql, *args = mock_conn.fetchrow.await_args.args
    assert args[0] is None
    assert args[1] is None
    assert args[5] == "admin_bypass"


# ---------------------------------------------------------------------------
# Bounded pool acquire (incident 2026-07-10, run d3d2e493)
# ---------------------------------------------------------------------------
# pool.acquire() without a timeout parks the caller forever when the pool
# is exhausted — a workflow-runner coroutine then hangs silently between
# nodes with no log and no error. The wait must be finite so exhaustion
# surfaces as TimeoutError, which the runner's DbWriteExhausted machinery
# already converts into a logged, failed run.


class _AcquireCalled(Exception):
    """Sentinel — aborts acquire_for_tenant right after pool.acquire()."""


def _timeout_capturing_pool(captured: dict) -> MagicMock:
    def _acquire(*, timeout=None):
        captured["timeout"] = timeout
        raise _AcquireCalled()

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


@pytest.mark.asyncio
async def test_acquire_for_tenant_passes_env_timeout_to_pool_acquire(monkeypatch):
    monkeypatch.setenv("KAORI_DB_ACQUIRE_TIMEOUT_S", "7.5")
    captured: dict = {}
    with patch("ai_orchestrator.shared.db.get_pool",
               return_value=_timeout_capturing_pool(captured)):
        with pytest.raises(_AcquireCalled):
            async with db.acquire_for_tenant(uuid4()):
                pass
    assert captured["timeout"] == 7.5


@pytest.mark.asyncio
async def test_acquire_for_tenant_default_timeout_is_30s(monkeypatch):
    monkeypatch.delenv("KAORI_DB_ACQUIRE_TIMEOUT_S", raising=False)
    captured: dict = {}
    with patch("ai_orchestrator.shared.db.get_pool",
               return_value=_timeout_capturing_pool(captured)):
        with pytest.raises(_AcquireCalled):
            async with db.acquire_for_tenant(uuid4()):
                pass
    assert captured["timeout"] == 30.0
