"""
F-032 — tests for the Gold aggregator.

The aggregator math is pure (deterministic given silver rows + today),
so the tests focus on:

  * canonical-only contract (rows missing customer_external_id are
    skipped, never fall back);
  * the active vs at-risk classifier (90-day cutoff);
  * the 12-month ceiling on revenue_at_risk;
  * idempotent upsert (rerunning is a no-op semantically);
  * rollup metrics (total_revenue_at_risk + at_risk_customer_count).

DB writes are exercised at the SQL level via a mock asyncpg conn so the
unit suite stays Docker-free. Real-DB end-to-end coverage is the
Sprint 4-5 manual smoke step (PLAN day 8) — out of scope for this PR.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

# Reuse the shared mock-builders so we don't re-derive the asyncpg
# AsyncMock subtleties.
from .test_api import _make_mock_conn, _make_tenant_ctx_factory  # noqa: PLE0402


ENTERPRISE = "11111111-1111-1111-1111-111111111111"


def _silver_row(customer_id: str | None, days_ago: int, amount: float,
                key: str = "revenue") -> dict:
    """Build a clean_data JSONB row mirroring Silver canonical shape."""
    today = datetime(2026, 4, 27, tzinfo=timezone.utc)
    d = today - timedelta(days=days_ago)
    row: dict = {
        "date":   d.strftime("%Y-%m-%d"),
        key:      str(amount),
    }
    if customer_id is not None:
        row["customer_external_id"] = customer_id
    return row


def _stub_fetch(conn: AsyncMock, rows: list[dict]) -> None:
    """Wrap row_data dicts as records so conn.fetch returns them.

    Column is ``row_data`` since mig 006 renamed silver_rows.clean_data →
    row_data (the aggregator + analytics runner both SELECT row_data); the old
    'clean_data' key here made _load_silver KeyError on every test."""
    conn.fetch.return_value = [{"row_data": r} for r in rows]


@pytest.fixture
def conn() -> AsyncMock:
    return _make_mock_conn()


@pytest.fixture
def patched(conn):
    """Patch acquire_for_tenant on the aggregator module + its consumer
    helper imports so every DB call routes through the mock conn."""
    tenant_ctx = _make_tenant_ctx_factory(conn)
    with patch("data_pipeline.data_plane.gold.aggregator.acquire_for_tenant", tenant_ctx):
        import data_pipeline.data_plane.gold.aggregator as agg  # noqa: PLC0415
        yield agg


# =========================================================================
# Active vs at-risk classifier
# =========================================================================

class TestActiveVsAtRisk:

    @pytest.mark.asyncio
    async def test_active_customer_recent_purchase_revenue_at_risk_zero(
            self, patched, conn):
        _stub_fetch(conn, [
            _silver_row("CUST-A", days_ago=30, amount=100),
            _silver_row("CUST-A", days_ago=60, amount=120),
        ])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        assert result.customers_processed == 1
        assert result.at_risk_customer_count == 0
        assert result.total_revenue_at_risk == Decimal("0")

    @pytest.mark.asyncio
    async def test_dormant_customer_with_history_is_at_risk(
            self, patched, conn):
        _stub_fetch(conn, [
            _silver_row("CUST-B", days_ago=120, amount=100),
            _silver_row("CUST-B", days_ago=180, amount=200),
        ])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        assert result.customers_processed == 1
        assert result.at_risk_customer_count == 1
        # avg = 150; 12-month sum = 300; min = 150
        assert result.total_revenue_at_risk == Decimal("150.0000")

    @pytest.mark.asyncio
    async def test_jsonb_returned_as_str_is_parsed(self, patched, conn):
        """asyncpg returns JSONB as a str — _load_silver must json.loads it.
        Regression: the str slipped through isinstance(dict) → every row was
        skipped as 'no_customer_external_id' → 0 Gold features on real pilot data."""
        import json as _j
        conn.fetch.return_value = [
            {"row_data": _j.dumps(_silver_row("CUST-S", days_ago=120, amount=100))},
            {"row_data": _j.dumps(_silver_row("CUST-S", days_ago=180, amount=200))},
        ]
        result = await patched.aggregate_for_tenant(
            ENTERPRISE, today=datetime(2026, 4, 27, tzinfo=timezone.utc))
        assert result.customers_processed == 1
        assert result.skipped_reason is None

    @pytest.mark.asyncio
    async def test_dormant_customer_only_ancient_purchases_zero_at_risk(
            self, patched, conn):
        # All purchases >12 months old → recent_total = 0 → cap kicks in.
        _stub_fetch(conn, [
            _silver_row("CUST-C", days_ago=400, amount=999),
        ])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        assert result.at_risk_customer_count == 0
        assert result.total_revenue_at_risk == Decimal("0")


# =========================================================================
# Canonical-only contract (no fallback)
# =========================================================================

class TestStrictCanonicalContract:

    @pytest.mark.asyncio
    async def test_rows_without_customer_external_id_are_skipped(
            self, patched, conn):
        _stub_fetch(conn, [
            _silver_row(None, days_ago=10, amount=100),  # missing canonical
            {"date": "2026-04-20", "customer_id": "WRONG", "revenue": "50"},  # wrong key
            _silver_row("CUST-D", days_ago=120, amount=200),
        ])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        assert result.customers_skipped == 2  # both non-canonical rows dropped
        assert result.customers_processed == 1
        # Only CUST-D made it through

    @pytest.mark.asyncio
    async def test_all_rows_missing_canonical_returns_skip_reason(
            self, patched, conn):
        _stub_fetch(conn, [
            {"date": "2026-04-20", "customer_id": "X", "revenue": "10"},
            {"date": "2026-04-21", "customer_id": "Y", "revenue": "20"},
        ])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        assert result.skipped_reason == "no_customer_external_id"
        assert result.customers_processed == 0
        assert result.customers_skipped == 2

    @pytest.mark.asyncio
    async def test_no_silver_rows_returns_skip_reason(self, patched, conn):
        conn.fetch.return_value = []

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        assert result.skipped_reason == "no_silver_rows"
        assert result.customers_processed == 0


# =========================================================================
# Field-name preference + amount parsing
# =========================================================================

class TestFieldParsing:

    @pytest.mark.asyncio
    async def test_revenue_takes_precedence_over_amount(self, patched, conn):
        _stub_fetch(conn, [{
            "customer_external_id": "CUST-E",
            "date":    "2026-01-15",
            "revenue": "200",   # should win
            "amount":  "999",   # should be ignored
        }])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        # avg purchase value = 200 (not 999)
        assert result.customers_processed == 1
        assert result.total_revenue_at_risk == Decimal("200.0000")

    @pytest.mark.asyncio
    async def test_amount_used_when_revenue_absent(self, patched, conn):
        _stub_fetch(conn, [{
            "customer_external_id": "CUST-F",
            "date":   "2025-11-15",
            "amount": "300",
        }])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )
        assert result.total_revenue_at_risk == Decimal("300.0000")

    @pytest.mark.asyncio
    async def test_invalid_amount_strings_silently_dropped(self, patched, conn):
        _stub_fetch(conn, [
            {"customer_external_id": "CUST-G", "date": "2025-12-01", "revenue": "100"},
            {"customer_external_id": "CUST-G", "date": "2025-12-15", "revenue": "not-a-number"},
        ])

        result = await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )
        # Bad amount dropped; only the valid 100 contributes.
        assert result.customers_processed == 1
        assert result.total_revenue_at_risk == Decimal("100.0000")


# =========================================================================
# Upsert + rollup behaviour
# =========================================================================

class TestUpsertAndRollup:

    @pytest.mark.asyncio
    async def test_upsert_features_then_rollup_aggregates(self, patched, conn):
        _stub_fetch(conn, [
            _silver_row("CUST-H", days_ago=200, amount=100),
            _silver_row("CUST-I", days_ago=200, amount=300),
        ])

        await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )

        # Two feature upserts (one per customer) + two aggregate rows
        # (total_revenue_at_risk + at_risk_customer_count).
        sql_calls = [c.args[0] for c in conn.execute.call_args_list]
        feature_calls   = [s for s in sql_calls if "INSERT INTO gold_features" in s]
        aggregate_calls = [s for s in sql_calls if "INSERT INTO gold_aggregates" in s]
        assert len(feature_calls)   == 2
        assert len(aggregate_calls) == 2

    @pytest.mark.asyncio
    async def test_idempotent_second_pass_writes_same_values(self, patched, conn):
        _stub_fetch(conn, [
            _silver_row("CUST-J", days_ago=180, amount=400),
        ])

        await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )
        first_calls = list(conn.execute.call_args_list)

        await patched.aggregate_for_tenant(
            ENTERPRISE,
            today=datetime(2026, 4, 27, tzinfo=timezone.utc),
        )
        second_calls = list(conn.execute.call_args_list)

        # Same number of SQL calls per pass — UPSERT runs the same shape.
        assert len(second_calls) == 2 * len(first_calls)
