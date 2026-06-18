"""Shared DB pool for data-pipeline service.

This module exposes two ways to get a connection:

1. ``get_pool().acquire()`` — the legacy, raw pool acquisition. Returns a
   connection without setting any session-level state. Today every router
   uses this. **It bypasses RLS** because the asyncpg pool currently
   connects as the Postgres superuser; the documented K-1 invariant
   (every SELECT filtered by tenant_id) is enforced only at the
   application-layer SQL strings.

2. ``acquire_for_tenant(enterprise_id)`` — the tenant-scoped acquisition
   added in G4a. Wraps the connection in an explicit transaction and
   sets ``app.enterprise_id`` via ``set_config(..., is_local=true)`` so
   that the RLS policies declared in
   ``infrastructure/postgres/migrations/001_init.sql:316-339`` and
   ``005_rls.sql`` evaluate correctly:

       USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID)

   The connection returns to the pool with no lingering session state
   because LOCAL settings expire when the transaction ends.

   Nothing in the codebase calls this yet — that's G4b's cutover. G4a
   adds the scaffolding so when G4b switches the DSN to ``kaori_app``
   (a non-superuser role that no longer bypasses RLS), every handler
   has a one-line migration path:

       async with get_pool().acquire() as conn:        # before
           rows = await conn.fetch(...)

       async with acquire_for_tenant(eid) as conn:     # after
           rows = await conn.fetch(...)

The G4 arch-guards check (in ``.github/workflows/arch-guards.yml``)
flips to hard-fail only after G4b lands and the DSN no longer points
at the superuser.
"""
import asyncio
import contextlib
import os
from typing import AsyncIterator, Optional, Union
from uuid import UUID

import asyncpg
import structlog
from fastapi import Header
from prometheus_client import REGISTRY, Gauge

log = structlog.get_logger()

_pool: Optional[asyncpg.Pool] = None


# Phase 2 #6 (B2 PR #5) — asyncpg pool gauges. Background sampler ticks
# every 5s so /metrics always shows fresh numbers without instrumenting
# every acquire/release. Hard-coded ``service`` label per-mirror because
# the ai-orchestrator + data-pipeline pools live in different processes
# scraped separately by Prometheus.
#
# ``_get_or_register`` is a guard for the rare case where both Python
# service mirrors (this module + ai-orchestrator/shared/db.py) get
# imported into the same Python process — eg. scripts/dump_openapi.py
# during the CI drift check. prometheus_client raises ValueError on
# duplicate metric names; in that case we just hand back the already-
# registered collector.
def _get_or_register(name: str, doc: str, labelnames):
    try:
        return Gauge(name, doc, labelnames=labelnames)
    except ValueError:
        return REGISTRY._names_to_collectors[name]


_pool_size_gauge = _get_or_register(
    "kaori_db_pool_size",
    "asyncpg pool current size (open connections, idle + busy)",
    ["service"],
)
_pool_idle_gauge = _get_or_register(
    "kaori_db_pool_idle",
    "asyncpg pool idle connections — high steady value = headroom; "
    "low + climbing pending = saturation",
    ["service"],
)
_pool_max_gauge = _get_or_register(
    "kaori_db_pool_max",
    "asyncpg pool configured ceiling (max_size constructor arg)",
    ["service"],
)
_SERVICE_LABEL = "data-pipeline"
_sampler_task: Optional[asyncio.Task] = None
_SAMPLE_INTERVAL_S = 5.0


async def _sample_pool_metrics() -> None:
    """Background loop — refresh the gauges every 5 seconds. Cheap
    because asyncpg keeps the counts in memory; no DB round-trip."""
    while True:
        try:
            if _pool is not None:
                _pool_size_gauge.labels(_SERVICE_LABEL).set(_pool.get_size())
                _pool_idle_gauge.labels(_SERVICE_LABEL).set(_pool.get_idle_size())
                _pool_max_gauge.labels(_SERVICE_LABEL).set(_pool.get_max_size())
            await asyncio.sleep(_SAMPLE_INTERVAL_S)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("pipeline.db.pool_sampler_error", error=str(exc))
            await asyncio.sleep(_SAMPLE_INTERVAL_S)


async def init_db_pool():
    global _pool, _sampler_task
    dsn = os.getenv("DATABASE_URL", "postgresql://kaori:kaori@localhost:5432/kaori")
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    _pool_max_gauge.labels(_SERVICE_LABEL).set(_pool.get_max_size())
    _sampler_task = asyncio.create_task(
        _sample_pool_metrics(), name="db-pool-metrics-sampler"
    )
    log.info("db.pool.started")


async def close_db_pool():
    global _sampler_task
    if _sampler_task is not None:
        _sampler_task.cancel()
        try:
            await _sampler_task
        except (asyncio.CancelledError, Exception):
            pass
        _sampler_task = None
    if _pool:
        await _pool.close()
        log.info("db.pool.closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool


# ---------------------------------------------------------------------------
# G4a — tenant-scoped connection wrapper.
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def acquire_for_tenant(
    enterprise_id: Union[str, UUID],
) -> AsyncIterator[asyncpg.Connection]:
    """Yield a Postgres connection scoped to a single tenant via RLS.

    Implementation detail — why a transaction wraps the work:

      Postgres' ``SET LOCAL`` (and equivalently ``set_config(name, value,
      true)``) only persists for the *current* transaction. asyncpg's
      pool has no per-checkout reset hook, so if we set ``app.enterprise_id``
      at the SESSION level the value would leak to the *next* request that
      checks the same connection out of the pool. Wrapping the work in an
      explicit transaction guarantees the value clears on commit / rollback
      and the connection returns to the pool with clean state.

    Caller contract:

      async with acquire_for_tenant(enterprise_id) as conn:
          row = await conn.fetchrow("SELECT ... FROM pipeline_runs WHERE run_id=$1", run_id)
          # NB: NO need to add `AND enterprise_id=$N` — RLS does that.

      A ValueError is raised if ``enterprise_id`` cannot be parsed as a
      UUID, mirroring the validation contract of the rest of the API.
    """
    # Coerce + validate. Reject obviously bad input here so RLS never
    # sees garbage (a malformed enterprise_id would either error in the
    # SET or — worse — silently match nothing because the cast fails at
    # row-level filter time).
    if isinstance(enterprise_id, UUID):
        eid_str = str(enterprise_id)
    else:
        # Throws ValueError on bad input — let the caller decide how to surface.
        eid_str = str(UUID(enterprise_id))

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # P15-S11 live-test 2026-05-15: set BOTH legacy + new-style
            # GUCs + the workspace_id GUC mig 059 introduced.
            await conn.execute(
                "SELECT set_config('app.enterprise_id',         $1, true), "
                "       set_config('app.current_enterprise_id', $1, true)",
                eid_str,
            )
            ws_row = await conn.fetchrow(
                "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
                eid_str,
            )
            ws_str = str(ws_row["workspace_id"]) if ws_row and ws_row["workspace_id"] else ""
            await conn.execute(
                "SELECT set_config('app.current_workspace_id', $1, true)",
                ws_str,
            )
            yield conn
        # Transaction commits here on normal exit; LOCAL setting clears.
        # On exception the transaction rolls back — same effect.


async def tenant_conn(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency: yields a tenant-scoped connection.

    Reads ``X-Enterprise-ID`` from the gateway-injected request headers
    (validated by FastAPI as a UUID; non-UUID values return 422 before
    the dependency runs) and threads it into ``acquire_for_tenant``.

    Usage in a router::

        @router.get("/runs")
        async def list_runs(conn: asyncpg.Connection = Depends(tenant_conn)):
            return await conn.fetch("SELECT * FROM pipeline_runs")
            # RLS filters by enterprise_id automatically.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        yield conn


# ---------------------------------------------------------------------------
# P1-MTNT-001 — cross-tenant access attempt audit helpers.
# Mirror of services/ai-orchestrator/shared/db.py log_cross_tenant_attempt.
# Kept synchronised — see that module's docstring.
# ---------------------------------------------------------------------------

async def log_cross_tenant_attempt(
    *,
    guc_tenant: Union[str, UUID, None] = None,
    row_tenant: Union[str, UUID, None] = None,
    operation: str,
    table_name: str,
    pk_value: str | None = None,
    reason: str = "rls_reject",
    detail: str | None = None,
    ip_address: str | None = None,
) -> int | None:
    """Insert a row into ``cross_tenant_attempts`` and return the id.

    Best-effort: errors are swallowed + warn-logged. Mirror of
    ai-orchestrator's helper (migration 040 owns the function).
    """
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT log_rls_attempt($1, $2, $3, $4, $5, $6, $7, $8) AS id",
                _coerce_uuid(guc_tenant),
                _coerce_uuid(row_tenant),
                operation,
                table_name,
                pk_value,
                reason,
                detail,
                ip_address,
            )
            return int(row["id"]) if row else None
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "cross_tenant.audit.write_failed",
            err=str(exc),
            operation=operation,
            table_name=table_name,
            guc_tenant=str(guc_tenant) if guc_tenant else None,
            row_tenant=str(row_tenant) if row_tenant else None,
        )
        return None


def _coerce_uuid(value: Union[str, UUID, None]) -> str | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    return str(UUID(value))
