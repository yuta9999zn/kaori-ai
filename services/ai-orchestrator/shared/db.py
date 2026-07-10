"""Async PostgreSQL connection pool — shared across all orchestrator routes.

Mirrors services/data-pipeline/shared/db.py — see that module's docstring
for the full G4a / G4b reasoning. Briefly:

* ``get_pool().acquire()`` — legacy raw acquisition. Bypasses RLS today
  because the pool connects as the Postgres superuser. All current
  routers use this.
* ``acquire_for_tenant(enterprise_id)`` — G4a addition. Sets
  ``app.enterprise_id`` via ``set_config(..., is_local=true)`` inside
  an explicit transaction so the RLS policies declared in the
  infrastructure migrations actually filter by tenant. Nobody calls
  this yet — G4b's job to migrate handlers.
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

_pool: asyncpg.Pool | None = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://kaori_user:kaori_pass@localhost:5432/kaori",
)


# Phase 2 #6 (B2 PR #5) — asyncpg pool gauges. Sampled by a background
# task on a 5s tick so /metrics always shows fresh numbers without
# instrumenting every acquire/release call site. ``service`` label is
# hard-coded per-mirror because the gauges live in different processes
# scraped separately by Prometheus.
#
# ``_get_or_register`` is a guard for the rare case where both Python
# service mirrors (this module + data-pipeline/shared/db.py) get imported
# into the same Python process — eg. scripts/dump_openapi.py during the
# CI drift check. prometheus_client raises ValueError on duplicate metric
# names; in that case we just hand back the already-registered collector
# instead of crashing.
def _get_or_register(name: str, doc: str, labelnames):
    try:
        return Gauge(name, doc, labelnames=labelnames)
    except ValueError:
        # Documented escape hatch — _names_to_collectors is the dict the
        # registry uses internally for the dedup check we just tripped.
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
_SERVICE_LABEL = "ai-orchestrator"
_sampler_task: asyncio.Task | None = None
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
            # Don't kill the sampler on a transient hiccup — log + retry.
            log.warning("orchestrator.db.pool_sampler_error", error=str(exc))
            await asyncio.sleep(_SAMPLE_INTERVAL_S)


async def init_db_pool() -> None:
    global _pool, _sampler_task
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    _pool_max_gauge.labels(_SERVICE_LABEL).set(_pool.get_max_size())
    _sampler_task = asyncio.create_task(
        _sample_pool_metrics(), name="db-pool-metrics-sampler"
    )
    log.info("orchestrator.db.pool_ready")


async def close_db_pool() -> None:
    global _pool, _sampler_task
    if _sampler_task is not None:
        _sampler_task.cancel()
        try:
            await _sampler_task
        except (asyncio.CancelledError, Exception):
            pass
        _sampler_task = None
    if _pool:
        await _pool.close()
        _pool = None


def _acquire_timeout_s() -> float:
    """Bounded pool-acquire wait (incident 2026-07-10, run d3d2e493):
    asyncpg's default acquire() waits forever on an exhausted pool — a
    runner coroutine then parks silently between nodes with no log. A
    finite wait surfaces exhaustion as TimeoutError, which callers'
    retry/degrade paths already handle. Read per call so ops can tune
    without a restart-order trap."""
    return float(os.getenv("KAORI_DB_ACQUIRE_TIMEOUT_S", "30"))


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db_pool() first.")
    return _pool


# ---------------------------------------------------------------------------
# G4a — tenant-scoped connection wrapper.
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def acquire_for_tenant(
    enterprise_id: Union[str, UUID],
) -> AsyncIterator[asyncpg.Connection]:
    """Yield a Postgres connection scoped to a single tenant via RLS.

    See services/data-pipeline/shared/db.py::acquire_for_tenant for the
    transaction-vs-LOCAL design rationale.
    """
    if isinstance(enterprise_id, UUID):
        eid_str = str(enterprise_id)
    else:
        eid_str = str(UUID(enterprise_id))

    pool = get_pool()
    async with pool.acquire(timeout=_acquire_timeout_s()) as conn:
        async with conn.transaction():
            # P15-S11 live-test 2026-05-15: must set BOTH legacy + new-style
            # GUCs. Migs ≤045 use app.enterprise_id; migs 046+ (branches,
            # departments, workflows, corporate_groups, …) use
            # app.current_enterprise_id. Mig 059 added workspace-aware
            # policies that also read app.current_workspace_id.
            #
            # Order matters: enterprise GUCs must be set BEFORE we read
            # enterprises (RLS on enterprises after mig 059 — without GUC
            # set the bootstrap SELECT returns 0 rows).
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


@contextlib.asynccontextmanager
async def acquire_for_tenant_dept(
    enterprise_id: Union[str, UUID],
    department_id: Optional[Union[str, UUID]] = None,
) -> AsyncIterator[asyncpg.Connection]:
    """Like acquire_for_tenant but ALSO sets app.current_department_id so the
    mig-053 ABAC dept-scope policies engage (ADR-0037). When department_id is
    None the dept GUC is left empty → those policies allow all departments
    (enterprise-wide, the existing behavior). Use for department-scoped reads."""
    async with acquire_for_tenant(enterprise_id) as conn:
        did = ""
        if department_id is not None:
            did = str(department_id) if isinstance(department_id, UUID) else str(UUID(str(department_id)))
        await conn.execute(
            "SELECT set_config('app.current_department_id', $1, true)", did)
        yield conn


async def tenant_conn(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency: yields a tenant-scoped connection.

    See services/data-pipeline/shared/db.py::tenant_conn for usage.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        yield conn


# ---------------------------------------------------------------------------
# P1-MTNT-001 — cross-tenant access attempt audit helpers.
#
# RLS rejects mismatched INSERT/UPDATE with Postgres SQLSTATE 42501
# (insufficient_privilege). asyncpg surfaces these as
# ``asyncpg.exceptions.InsufficientPrivilegeError``. Catching the
# exception at the application layer lets us write a row to
# ``cross_tenant_attempts`` (migration 040) before re-raising, so ops
# can see frequency + which table + which tenant attempted what.
#
# Usage::
#
#     try:
#         async with acquire_for_tenant(tenant_a) as conn:
#             await conn.execute("INSERT INTO foo ... ", ..., tenant_b)
#     except asyncpg.exceptions.InsufficientPrivilegeError as exc:
#         await log_cross_tenant_attempt(
#             guc_tenant=tenant_a,
#             row_tenant=tenant_b,
#             operation="INSERT",
#             table_name="public.foo",
#             reason="rls_reject",
#             detail=str(exc),
#         )
#         raise
#
# We use a fresh non-tenant-scoped connection for the audit write so the
# log row lands even if the original transaction is doomed. The audit
# table is intentionally NOT under RLS (see migration 040 comment), so
# the runtime kaori_app role can INSERT into it without a GUC.
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

    Best-effort: any error during the audit write is swallowed (a
    failing audit log must never mask the original RLS rejection that
    triggered it). Failures emit a warn log so SREs notice silent gaps.

    Returns the inserted id on success, ``None`` on swallowed failure.
    """
    try:
        pool = get_pool()
        async with pool.acquire(timeout=_acquire_timeout_s()) as conn:
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
    except Exception as exc:  # noqa: BLE001 — see docstring
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
    """Normalise UUID-like inputs to canonical string form for asyncpg.

    asyncpg accepts UUID objects directly but mixed types in the same
    callsite are easy to fumble — this helper flattens str/UUID/None to
    a string asyncpg can bind cleanly.
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    return str(UUID(value))


# ---------------------------------------------------------------------------
# Migration 024 prep — cross-tenant aggregation helper.
# ---------------------------------------------------------------------------

@contextlib.asynccontextmanager
async def acquire_cross_tenant() -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection authorised for cross-tenant aggregation under
    NOBYPASSRLS. Use ONLY on documented platform-admin / cross-tenant
    aggregation paths — the same set of files in
    ``scripts/check-tenant-filter.py``'s PATH_ALLOWLIST.

    Mechanism: ``SET LOCAL app.is_admin = 'true'`` matches the
    ``admin_bypass_*`` permissive RLS policies installed by migration
    025. Postgres applies multiple permissive policies as OR, so a row
    becomes visible when the GUC is set even though the per-tenant
    ``enterprise_id = app.enterprise_id`` predicate evaluates false.

    Why not ``row_security = off``: Postgres' ``row_security`` is NOT a
    bypass — set to ``off`` it raises an error on any query that would
    be affected by an RLS policy. The ``app.is_admin`` policy is the
    intended escape hatch.

    Setting expires on transaction commit/rollback (LOCAL), so the
    connection returns to the pool with no lingering admin state.
    """
    pool = get_pool()
    async with pool.acquire(timeout=_acquire_timeout_s()) as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.is_admin = 'true'")
            yield conn
