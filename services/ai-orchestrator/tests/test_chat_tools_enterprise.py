"""
Sprint 8 — P2 enterprise tool unit tests.

Each tool is exercised through ``BaseTool.execute`` with a fake
``acquire_for_tenant`` so no real DB is touched. Goals:

  * the SQL placeholders match the args we hand in
  * the projection shape matches the docstring (FE relies on it)
  * arg validation rejects out-of-range values with ValueError so
    the registry surfaces a friendly message (see registry tests)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.chat.tools.base import ToolContext
from ai_orchestrator.chat.tools.enterprise import (
    GetBillingQuotaStatusTool,
    GetTopAtRiskCustomersTool,
    SummarizeRecentDecisionsTool,
)

_EID = "11111111-1111-1111-1111-111111111111"
_CTX = ToolContext(scope="enterprise", enterprise_id=_EID, role="MANAGER")


def _fake_acquire(fetch_value=None, fetchrow_value=None, captured: dict | None = None):
    """Build an async-context-manager that yields a connection whose
    ``fetch`` / ``fetchrow`` return the supplied values.

    ``captured`` (optional) is mutated with ``sql`` and ``args`` so a
    test can assert the placeholders the tool actually sent."""

    @asynccontextmanager
    async def _ctx(enterprise_id):
        conn = AsyncMock()

        async def _fetch(sql, *args):
            if captured is not None:
                captured["sql"] = sql
                captured["args"] = args
            return fetch_value or []

        async def _fetchrow(sql, *args):
            if captured is not None:
                captured["sql"] = sql
                captured["args"] = args
            return fetchrow_value

        conn.fetch = _fetch
        conn.fetchrow = _fetchrow
        yield conn

    return _ctx


# =========================================================================
# summarize_recent_decisions
# =========================================================================

@pytest.mark.asyncio
async def test_summarize_recent_decisions_happy_path():
    rows = [
        {"decision_type": "schema_mapping",  "n": 12},
        {"decision_type": "cleaning_rule",   "n": 5},
    ]
    captured: dict = {}
    fake = _fake_acquire(fetch_value=rows, captured=captured)
    with patch("ai_orchestrator.chat.tools.enterprise.acquire_for_tenant", fake):
        out = await SummarizeRecentDecisionsTool().execute({"days": 14}, _CTX)

    assert out["window_days"] == 14
    assert out["total_decisions"] == 17
    assert out["by_type"][0]["decision_type"] == "schema_mapping"
    assert out["by_type"][0]["count"] == 12
    # SQL parameter order: enterprise_id, then days-as-string for INTERVAL
    assert captured["args"][0] == _EID
    assert captured["args"][1] == "14"


@pytest.mark.asyncio
async def test_summarize_recent_decisions_default_days_is_seven():
    fake = _fake_acquire(fetch_value=[])
    with patch("ai_orchestrator.chat.tools.enterprise.acquire_for_tenant", fake):
        out = await SummarizeRecentDecisionsTool().execute({}, _CTX)
    assert out["window_days"] == 7
    assert out["total_decisions"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -1, 91, 1000])
async def test_summarize_recent_decisions_rejects_out_of_range_days(bad):
    with pytest.raises(ValueError, match="days"):
        await SummarizeRecentDecisionsTool().execute({"days": bad}, _CTX)


@pytest.mark.asyncio
async def test_summarize_recent_decisions_requires_enterprise_in_ctx():
    bad_ctx = ToolContext(scope="enterprise", enterprise_id=None)
    with pytest.raises(ValueError, match="enterprise_id"):
        await SummarizeRecentDecisionsTool().execute({}, bad_ctx)


# =========================================================================
# get_top_at_risk_customers
# =========================================================================

@pytest.mark.asyncio
async def test_get_top_at_risk_customers_projects_view_shape():
    rows = [
        {
            "customer_external_id": "C001",
            "revenue_at_risk":      Decimal("1234.5670"),
            "last_purchase_at":     datetime(2026, 4, 1, tzinfo=timezone.utc),
            "purchase_count":       4,
        },
        {
            "customer_external_id": "C002",
            "revenue_at_risk":      Decimal("999.0000"),
            "last_purchase_at":     None,
            "purchase_count":       1,
        },
    ]
    captured: dict = {}
    fake = _fake_acquire(fetch_value=rows, captured=captured)
    with patch("ai_orchestrator.chat.tools.enterprise.acquire_for_tenant", fake):
        out = await GetTopAtRiskCustomersTool().execute({"limit": 5}, _CTX)

    assert out["count"] == 2
    assert out["customers"][0]["customer_external_id"] == "C001"
    assert out["customers"][0]["revenue_at_risk"] == 1234.567
    assert out["customers"][0]["last_purchase_at"] == "2026-04-01T00:00:00+00:00"
    # Second row: null last_purchase_at survives the projection
    assert out["customers"][1]["last_purchase_at"] is None
    assert captured["args"][0] == _EID
    assert captured["args"][1] == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -1, 21, 100])
async def test_get_top_at_risk_customers_rejects_out_of_range_limit(bad):
    with pytest.raises(ValueError, match="limit"):
        await GetTopAtRiskCustomersTool().execute({"limit": bad}, _CTX)


@pytest.mark.asyncio
async def test_get_top_at_risk_customers_default_limit_is_five():
    fake = _fake_acquire(fetch_value=[])
    captured: dict = {}
    fake = _fake_acquire(fetch_value=[], captured=captured)
    with patch("ai_orchestrator.chat.tools.enterprise.acquire_for_tenant", fake):
        await GetTopAtRiskCustomersTool().execute({}, _CTX)
    assert captured["args"][1] == 5


# =========================================================================
# get_billing_quota_status
# =========================================================================

@pytest.mark.asyncio
async def test_get_billing_quota_status_projects_view_shape():
    row = {
        "plan_code":            "BUSINESS",
        "quota":                2000,
        "current_month_usage":  1700,
        "usage_pct":            Decimal("85.00"),
        "alert_80":             True,
        "alert_95":             False,
    }
    fake = _fake_acquire(fetchrow_value=row)
    with patch("ai_orchestrator.chat.tools.enterprise.acquire_for_tenant", fake):
        out = await GetBillingQuotaStatusTool().execute({}, _CTX)

    assert out == {
        "found": True,
        "plan_code": "BUSINESS",
        "quota": 2000,
        "current_month_usage": 1700,
        "usage_pct": 85.0,
        "alert_80_fired": True,
        "alert_95_fired": False,
    }


@pytest.mark.asyncio
async def test_get_billing_quota_status_returns_found_false_when_no_row():
    fake = _fake_acquire(fetchrow_value=None)
    with patch("ai_orchestrator.chat.tools.enterprise.acquire_for_tenant", fake):
        out = await GetBillingQuotaStatusTool().execute({}, _CTX)
    assert out == {"found": False}
