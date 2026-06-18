"""
Sprint 8 — P1 platform tool unit tests.

Migration 024 prep — platform tools now go through
``shared.db.acquire_cross_tenant()`` (async context manager that opens
a tx and ``SET LOCAL row_security = off``) instead of bare
``get_pool().fetchrow(...)``. The tests patch ``acquire_cross_tenant``
with a fake that yields a stub conn whose ``fetchrow`` / ``fetch``
return canned rows + capture the SQL + args.
"""
from __future__ import annotations

import contextlib
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from ai_orchestrator.chat.tools.base import ToolContext
from ai_orchestrator.chat.tools.platform import (
    CountRecentSignupsTool,
    FindWorkspacesInAlertTool,
    GetPlatformSummaryTool,
)

_CTX = ToolContext(scope="platform", role="ADMIN", user_id="u-1")


def _fake_conn(fetchrow_value=None, fetch_value=None, captured: dict | None = None):
    """Stub asyncpg connection — ``fetchrow`` / ``fetch`` return canned data
    and (optionally) record the SQL + args the tool issued."""
    conn = MagicMock()

    async def _fetchrow(sql, *args):
        if captured is not None:
            captured["sql"] = sql
            captured["args"] = args
        return fetchrow_value

    async def _fetch(sql, *args):
        if captured is not None:
            captured["sql"] = sql
            captured["args"] = args
        return fetch_value or []

    conn.fetchrow = _fetchrow
    conn.fetch = _fetch
    return conn


def _patch_acquire(conn):
    """Returns a context manager suitable for ``with ...`` that swaps
    ``acquire_cross_tenant`` for an async ctxmgr yielding the given
    stub conn. Equivalent to the previous ``patch(get_pool, return_value=...)``
    fixture but matches the new ``async with acquire_cross_tenant() as conn``
    call shape in the tools."""
    @contextlib.asynccontextmanager
    async def _ctx():
        yield conn
    return patch("ai_orchestrator.chat.tools.platform.acquire_cross_tenant",
                 lambda: _ctx())


# =========================================================================
# get_platform_summary
# =========================================================================

@pytest.mark.asyncio
async def test_get_platform_summary_returns_int_counts():
    conn = _fake_conn(fetchrow_value={
        "workspaces_active":     7,
        "enterprises_active":    9,
        "users_active":         42,
        "pipeline_runs_total": 250,
        "pipeline_runs_last_7d": 14,
    })
    with _patch_acquire(conn):
        out = await GetPlatformSummaryTool().execute({}, _CTX)
    assert out == {
        "workspaces_active":     7,
        "enterprises_active":    9,
        "users_active":         42,
        "pipeline_runs_total": 250,
        "pipeline_runs_last_7d": 14,
    }


# =========================================================================
# count_recent_signups
# =========================================================================

@pytest.mark.asyncio
async def test_count_recent_signups_default_window():
    captured: dict = {}
    conn = _fake_conn(
        fetchrow_value={"new_count": 3, "total_count": 100},
        captured=captured,
    )
    with _patch_acquire(conn):
        out = await CountRecentSignupsTool().execute({}, _CTX)
    assert out == {"window_days": 30, "new_signups": 3, "total_active": 100}
    # SQL receives ``days`` as string for the INTERVAL coercion
    assert captured["args"][0] == "30"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -5, 366, 10000])
async def test_count_recent_signups_rejects_out_of_range(bad):
    with pytest.raises(ValueError, match="days"):
        await CountRecentSignupsTool().execute({"days": bad}, _CTX)


# =========================================================================
# find_workspaces_in_alert
# =========================================================================

@pytest.mark.asyncio
async def test_find_workspaces_in_alert_default_threshold_any():
    rows = [
        {
            "enterprise_id":    UUID("11111111-1111-1111-1111-111111111111"),
            "enterprise_name":  "Tenant A",
            "billing_month":    date(2026, 4, 1),
            "unique_customers": 950,
            "quota":            1000,
            "alert_80_fired":   True,
            "alert_95_fired":   True,
        },
    ]
    conn = _fake_conn(fetch_value=rows)
    with _patch_acquire(conn):
        out = await FindWorkspacesInAlertTool().execute({}, _CTX)

    assert out["threshold"] == "any"
    assert out["count"] == 1
    ws = out["workspaces"][0]
    assert ws["enterprise_id"] == "11111111-1111-1111-1111-111111111111"
    assert ws["enterprise_name"] == "Tenant A"
    assert ws["billing_month"] == "2026-04-01"
    assert ws["usage_pct"] == 95.0
    assert ws["alert_80_fired"] is True
    assert ws["alert_95_fired"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["50", "100", "any_thing", ""])
async def test_find_workspaces_in_alert_rejects_unknown_threshold(bad):
    with pytest.raises(ValueError, match="threshold"):
        await FindWorkspacesInAlertTool().execute({"threshold": bad}, _CTX)


@pytest.mark.asyncio
@pytest.mark.parametrize("threshold,expected_fragment", [
    ("80", "alert_80_fired = TRUE"),
    ("95", "alert_95_fired = TRUE"),
    ("any", "alert_80_fired = TRUE OR b.alert_95_fired = TRUE"),
])
async def test_find_workspaces_in_alert_sql_filter_per_threshold(threshold, expected_fragment):
    captured: dict = {}
    conn = _fake_conn(fetch_value=[], captured=captured)
    with _patch_acquire(conn):
        await FindWorkspacesInAlertTool().execute({"threshold": threshold}, _CTX)
    assert expected_fragment in captured["sql"]


@pytest.mark.asyncio
async def test_find_workspaces_in_alert_handles_zero_quota_safely():
    """Defence against div-by-zero — quota=0 row in the result must not
    crash the projection (the SQL guards with NULLIF, the Python guards
    with ``if quota else 0.0``)."""
    rows = [{
        "enterprise_id":    UUID("11111111-1111-1111-1111-111111111111"),
        "enterprise_name":  "Edge",
        "billing_month":    date(2026, 4, 1),
        "unique_customers": 5,
        "quota":            0,
        "alert_80_fired":   True,
        "alert_95_fired":   False,
    }]
    conn = _fake_conn(fetch_value=rows)
    with _patch_acquire(conn):
        out = await FindWorkspacesInAlertTool().execute({"threshold": "80"}, _CTX)
    assert out["workspaces"][0]["usage_pct"] == 0.0
