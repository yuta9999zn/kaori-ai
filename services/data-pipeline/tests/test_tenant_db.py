"""
Tests for the G4a additive RLS scaffolding in shared.db.

Confirms:
  - ``acquire_for_tenant`` sets ``app.enterprise_id`` via the
    ``set_config(name, value, is_local=true)`` form inside an explicit
    transaction (so the LOCAL setting clears on transaction end and
    the connection returns to the pool clean).
  - Both UUID objects and strings are accepted.
  - Malformed enterprise_id raises ValueError before any DB call.
  - The FastAPI dependency forwards the header value through.

No real Postgres needed — the pool + connection are mocked. The arch-
guards G4 check still flags the broader gap (DSN still uses superuser
``kaori``); that flips to hard-fail only when G4b migrates handlers.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from data_pipeline.shared import db


# ---------------------------------------------------------------------------
# Fixtures — minimal asyncpg mock that supports `pool.acquire() as conn`
# and `conn.transaction() as tx`.
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_conn() -> AsyncMock:
    """A connection mock with the right context-manager wiring."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    # P15-S11 mig 059 wire-in 2026-05-15 added a workspace lookup
    # inside acquire_for_tenant. Default fetchrow to None so the
    # workspace SET happens with empty string and no MagicMock leak
    # into the second execute call's args. Tests that care about the
    # workspace path override this on their own.
    conn.fetchrow = AsyncMock(return_value=None)

    # `async with conn.transaction():` — transaction() is a SYNC method
    # returning an async context manager. AsyncMock would auto-make it
    # async; explicit MagicMock keeps it sync.
    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)
    return conn


@pytest.fixture
def mock_pool(mock_conn) -> MagicMock:
    """A pool mock whose `acquire()` yields the connection mock."""
    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_for_tenant_sets_app_enterprise_id_via_set_config(mock_pool, mock_conn):
    eid = uuid4()
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as conn:
            assert conn is mock_conn

    # P15-S11 mig 059 (2026-05-15) — acquire_for_tenant now issues 2
    # set_config calls: enterprise_id first, workspace_id second
    # (after a fetchrow workspace lookup). Pin both:
    assert mock_conn.execute.await_count == 2
    first_call_args = mock_conn.execute.await_args_list[0].args
    sql = first_call_args[0]
    assert "set_config('app.enterprise_id'" in sql, f"unexpected SQL: {sql}"
    # Third positional arg in SQL is `true` — verify the SQL form not a parameter
    assert "true" in sql, f"set_config must use is_local=true: {sql}"
    # Second arg is the tenant id (parameter $1)
    assert first_call_args[1] == str(eid)

    # Second execute is the workspace_id SET — confirm it fired with
    # an empty workspace (mock_conn.fetchrow returns None → ws_str='').
    second_call_args = mock_conn.execute.await_args_list[1].args
    assert "set_config('app.current_workspace_id'" in second_call_args[0]
    assert second_call_args[1] == ""


@pytest.mark.asyncio
async def test_acquire_for_tenant_runs_inside_a_transaction(mock_pool, mock_conn):
    """
    Regression guard for the LOCAL-vs-pool-leak issue: set_config(...,true)
    only persists for the current transaction. If the wrapper ever drops
    the explicit transaction, the setting would leak to the next
    pool checkout.
    """
    eid = uuid4()
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as _:
            pass

    # transaction() called exactly once; aenter / aexit fired
    mock_conn.transaction.assert_called_once()
    tx = mock_conn.transaction.return_value
    tx.__aenter__.assert_awaited_once()
    tx.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_acquire_for_tenant_accepts_string(mock_pool, mock_conn):
    eid_str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid_str) as _:
            pass
    # First execute is the enterprise_id SET — workspace SET comes second.
    args = mock_conn.execute.await_args_list[0].args
    assert args[1] == eid_str


@pytest.mark.asyncio
async def test_acquire_for_tenant_accepts_uuid_object(mock_pool, mock_conn):
    eid = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as _:
            pass
    args = mock_conn.execute.await_args_list[0].args
    assert args[1] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_for_tenant_rejects_malformed_uuid_before_db_call(mock_pool, mock_conn):
    """
    Garbage in → ValueError out, before any pool acquisition. This
    keeps malformed input out of the SET LOCAL command (where it
    would either error or — depending on the cast site — silently
    match nothing at row-level filter time).
    """
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        with pytest.raises(ValueError):
            async with db.acquire_for_tenant("not-a-uuid") as _:
                pass

    # No SQL was issued
    mock_conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Pool wiring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_for_tenant_raises_when_pool_uninit():
    """If init_db_pool() never ran, acquire_for_tenant must raise the
    same RuntimeError as the legacy get_pool() — a fast, loud failure
    is preferable to silently bypassing tenant scoping."""
    # Module-level _pool starts None unless a previous test left state.
    # Force the not-initialised path explicitly.
    with patch("data_pipeline.shared.db.get_pool",
               side_effect=RuntimeError("DB pool not initialized")):
        with pytest.raises(RuntimeError, match="not initialized"):
            async with db.acquire_for_tenant(uuid4()) as _:
                pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_conn_forwards_header_to_acquire(mock_pool, mock_conn):
    """The FastAPI dependency just adapts the header into acquire_for_tenant."""
    eid = uuid4()
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        gen = db.tenant_conn(x_enterprise_id=eid)
        conn = await gen.__anext__()
        assert conn is mock_conn
        # Cleanup the dependency generator to fire the __aexit__
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    args = mock_conn.execute.await_args_list[0].args
    assert args[1] == str(eid)


# ---------------------------------------------------------------------------
# Workspace lookup (P15-S11 mig 059 — added 2026-05-15)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_for_tenant_propagates_workspace_id_when_found(mock_pool, mock_conn):
    """When the enterprise has a workspace, the second SET fires with
    the workspace UUID string — this is what mig 059 wired in."""
    ws_id = uuid4()
    mock_conn.fetchrow = AsyncMock(return_value={"workspace_id": ws_id})

    eid = uuid4()
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool):
        async with db.acquire_for_tenant(eid) as _:
            pass

    # Second execute carries the workspace_id SET
    ws_call_args = mock_conn.execute.await_args_list[1].args
    assert "set_config('app.current_workspace_id'" in ws_call_args[0]
    assert ws_call_args[1] == str(ws_id)


# ---------------------------------------------------------------------------
# P1-MTNT-001 — log_cross_tenant_attempt helper (mirror of ai-orchestrator)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pool_for_audit(mock_conn) -> MagicMock:
    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    pool = MagicMock()
    pool.acquire = _acquire
    mock_conn.fetchrow = AsyncMock(return_value={"id": 99})
    return pool


@pytest.mark.asyncio
async def test_log_cross_tenant_attempt_calls_postgres_function(mock_pool_for_audit, mock_conn):
    guc = uuid4()
    row = uuid4()
    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool_for_audit):
        result = await db.log_cross_tenant_attempt(
            guc_tenant=guc,
            row_tenant=row,
            operation="UPDATE",
            table_name="public.silver_pipeline_rows",
            pk_value="row-7",
            reason="rls_reject",
            detail="row level security",
        )

    assert result == 99
    sql, *args = mock_conn.fetchrow.await_args.args
    assert "log_rls_attempt" in sql
    assert args[0] == str(guc)
    assert args[1] == str(row)
    assert args[2] == "UPDATE"
    assert args[3] == "public.silver_pipeline_rows"


@pytest.mark.asyncio
async def test_log_cross_tenant_attempt_swallows_audit_failure(mock_pool_for_audit, mock_conn):
    mock_conn.fetchrow = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("data_pipeline.shared.db.get_pool", return_value=mock_pool_for_audit):
        result = await db.log_cross_tenant_attempt(
            operation="DELETE",
            table_name="public.bronze_files",
        )

    assert result is None
