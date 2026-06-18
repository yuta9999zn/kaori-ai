"""
SH-M59 ROI-Hybrid billing tests.

8-section template (Phase 2 methodology):
  1. Mig 077 shape          — 2 tables + check constraints + indexes
  2. Pure compute            — rate × revenue + cap + eligibility
  3. Eligibility helpers     — opted_in × months_of_data combinations
  4. DB helpers              — fetch_actioned_revenue / months / opt-in
  5. Cron entry              — compute_monthly_run + idempotency
  6. Endpoint smoke          — opt-in/out + subscription + cron + preview
  7. Integration             — full lifecycle + cap-applied scenario
  8. Tenant isolation + edge — cross-tenant + zero revenue + boundary months
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.economics.roi_billing import (
    DEFAULT_CAP_VND,
    DEFAULT_RATE,
    MIN_MONTHS_OF_DATA,
    RoiComputation,
    compute_monthly_run,
    compute_roi_addon,
    fetch_actioned_revenue_at_risk,
    fetch_months_of_data,
    has_existing_line,
    is_eligible,
    is_opted_in,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"

ENT     = UUID("11111111-1111-1111-1111-111111111111")
ENT_B   = UUID("22222222-2222-2222-2222-222222222222")
HEADERS = {"X-Enterprise-ID": str(ENT)}
MONTH   = date(2026, 5, 1)
PREV_M  = date(2026, 4, 1)


# ─── Helpers ─────────────────────────────────────────────────────────


def _row(**kw):
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kw[k]
    r.get = lambda k, default=None: kw.get(k, default)
    r.keys = MagicMock(return_value=list(kw.keys()))
    return r


class _FakeConn:
    """Stand-in for asyncpg Connection. Models:
        gold_features              (enterprise_id, customer_external_id,
                                    revenue_at_risk, is_actioned, actioned_at)
        enterprise_monthly_billing (enterprise_id, billing_month)
        enterprise_roi_subscriptions (enterprise_id, opted_in_at,
                                      opted_out_at, eligibility_confirmed_at,
                                      notes)
        enterprise_roi_billing_lines (line_id, enterprise_id, billing_month,
                                       inputs..., outputs..., metadata...)
    """

    def __init__(self):
        self.gold:  list[dict] = []
        self.bills: list[dict] = []
        self.subs:  list[dict] = []
        self.lines: list[dict] = []

    @asynccontextmanager
    async def transaction(self):
        yield self

    def _sub(self, enterprise_id):
        for r in self.subs:
            if r["enterprise_id"] == enterprise_id:
                return r
        return None

    async def fetch(self, sql, *args):
        s = " ".join(sql.split())
        if s.startswith("SELECT enterprise_id FROM enterprise_roi_subscriptions"):
            return [_row(enterprise_id=r["enterprise_id"])
                    for r in self.subs
                    if r.get("opted_out_at") is None]
        if "FROM enterprise_roi_billing_lines" in s:
            rows = [r for r in self.lines
                    if r["enterprise_id"] == args[0]]
            if "billing_month >=" in s:
                rows = [r for r in rows if r["billing_month"] >= args[1]]
            if "billing_month <=" in s:
                # to_month is last param
                rows = [r for r in rows if r["billing_month"] <= args[-1]]
            rows.sort(key=lambda r: r["billing_month"], reverse=True)
            return [_row(**r) for r in rows]
        raise AssertionError(f"unhandled fetch: {s[:120]}")

    async def fetchrow(self, sql, *args):
        s = " ".join(sql.split())
        if s.startswith("SELECT COALESCE(SUM(revenue_at_risk)"):
            ent, billing_month = args
            from datetime import timedelta as _td
            # actioned within [billing_month, next_month)
            year, month = billing_month.year, billing_month.month
            if month == 12:
                nxt = date(year + 1, 1, 1)
            else:
                nxt = date(year, month + 1, 1)
            total = Decimal("0")
            for r in self.gold:
                if r["enterprise_id"] != ent or not r["is_actioned"]:
                    continue
                if r.get("actioned_at") is None:
                    continue
                aa = r["actioned_at"]
                if isinstance(aa, datetime):
                    aa = aa.date()
                if billing_month <= aa < nxt:
                    total += Decimal(str(r["revenue_at_risk"]))
            return _row(total=total)
        if s.startswith("SELECT COUNT(*) AS n FROM enterprise_monthly_billing"):
            ent, upto = args
            n = sum(1 for r in self.bills
                    if r["enterprise_id"] == ent and r["billing_month"] < upto)
            return _row(n=n)
        if s.startswith("SELECT 1 FROM enterprise_roi_subscriptions"):
            r = self._sub(args[0])
            if r is None or r.get("opted_out_at") is not None:
                return None
            return _row(_one=1)
        if s.startswith("SELECT 1 FROM enterprise_roi_billing_lines"):
            ent, bm = args
            for r in self.lines:
                if r["enterprise_id"] == ent and r["billing_month"] == bm:
                    return _row(_one=1)
            return None
        if s.startswith("SELECT opted_in_at, eligibility_confirmed_at"):
            r = self._sub(args[0])
            if r is None:
                return None
            return _row(
                opted_in_at=r["opted_in_at"],
                eligibility_confirmed_at=r.get("eligibility_confirmed_at"),
            )
        if s.startswith("SELECT opted_in_at, opted_out_at"):
            r = self._sub(args[0])
            if r is None:
                return None
            return _row(
                opted_in_at=r["opted_in_at"],
                opted_out_at=r.get("opted_out_at"),
                eligibility_confirmed_at=r.get("eligibility_confirmed_at"),
                notes=r.get("notes"),
            )
        if s.startswith("UPDATE enterprise_roi_subscriptions SET opted_out_at"):
            r = self._sub(args[0])
            if r is None or r.get("opted_out_at") is not None:
                return None
            r["opted_out_at"] = datetime.now(timezone.utc)
            return _row(opted_out_at=r["opted_out_at"])
        if s.startswith("SELECT line_id, enterprise_id"):
            ent, bm = args
            for r in self.lines:
                if r["enterprise_id"] == ent and r["billing_month"] == bm:
                    return _row(**r)
            return None
        raise AssertionError(f"unhandled fetchrow: {s[:120]}")

    async def execute(self, sql, *args):
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO enterprise_roi_subscriptions"):
            r = self._sub(args[0])
            if r is None:
                self.subs.append({
                    "enterprise_id": args[0],
                    "opted_in_at":  datetime.now(timezone.utc),
                    "opted_out_at": None,
                    "eligibility_confirmed_at": None,
                    "notes": None,
                })
            else:
                r["opted_in_at"]  = datetime.now(timezone.utc)
                r["opted_out_at"] = None
            return "INSERT 0 1"
        if s.startswith("INSERT INTO enterprise_roi_billing_lines"):
            (ent, bm, rev, rate, cap, raw, capped, cap_applied,
             months, elig, run_id) = args
            for r in self.lines:
                if r["enterprise_id"] == ent and r["billing_month"] == bm:
                    return "INSERT 0 0"
            self.lines.append({
                "line_id": uuid4(),
                "enterprise_id": ent,
                "billing_month": bm,
                "actioned_revenue_at_risk_vnd": rev,
                "rate": rate,
                "cap_threshold_vnd": cap,
                "raw_roi_addon_vnd": raw,
                "capped_roi_addon_vnd": capped,
                "cap_applied": cap_applied,
                "months_of_data": months,
                "eligibility_met": elig,
                "computed_at": datetime.now(timezone.utc),
                "computed_by_run_id": run_id,
                "notes": None,
            })
            return "INSERT 0 1"
        if s.startswith("UPDATE enterprise_roi_subscriptions SET eligibility_confirmed_at"):
            r = self._sub(args[0])
            if r is not None and r.get("eligibility_confirmed_at") is None:
                r["eligibility_confirmed_at"] = datetime.now(timezone.utc)
            return "UPDATE 1"
        raise AssertionError(f"unhandled execute: {s[:120]}")


def _make_app(conn: _FakeConn):
    from ai_orchestrator.routers import roi_billing as rb

    @asynccontextmanager
    async def fake_acquire(_eid):
        yield conn

    rb.acquire_for_tenant = fake_acquire
    app = FastAPI()
    app.include_router(rb.router)
    return app


def _seed_months(conn, ent, n):
    """Seed n closed billing months strictly before MONTH."""
    for i in range(n):
        bm = date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1)
        conn.bills.append({"enterprise_id": ent, "billing_month": bm})


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 077 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig081Shape:

    @pytest.fixture(scope="class")
    def mig(self) -> str:
        return (MIG_DIR / "081_roi_billing.sql").read_text(encoding="utf-8")

    def test_subscriptions_table_present(self, mig):
        assert "CREATE TABLE IF NOT EXISTS enterprise_roi_subscriptions" in mig

    def test_billing_lines_table_present(self, mig):
        assert "CREATE TABLE IF NOT EXISTS enterprise_roi_billing_lines" in mig

    def test_unique_per_enterprise_month(self, mig):
        assert "uq_roi_enterprise_month" in mig
        assert "UNIQUE (enterprise_id, billing_month)" in mig

    def test_rate_check_constraint(self, mig):
        assert "chk_roi_rate_positive" in mig
        assert "rate > 0 AND rate < 1" in mig

    def test_cap_consistency_check(self, mig):
        assert "chk_roi_cap_consistency" in mig
        assert "cap_applied = TRUE" in mig
        assert "cap_applied = FALSE" in mig

    def test_capped_le_raw_check(self, mig):
        assert "chk_roi_capped_le_raw" in mig
        assert "capped_roi_addon_vnd <= raw_roi_addon_vnd" in mig

    def test_partial_index_active_subscriptions(self, mig):
        assert "idx_roi_sub_active" in mig
        assert "WHERE opted_out_at IS NULL" in mig

    def test_optout_after_optin_check(self, mig):
        assert "chk_roi_sub_optout_after_optin" in mig

    def test_money_precision_decimal(self, mig):
        # K-9: NUMERIC(18,4) for money, NUMERIC(5,4) for rate
        assert "NUMERIC(18,4)" in mig
        assert "NUMERIC(5,4)" in mig

    def test_default_rate_and_cap(self, mig):
        assert "DEFAULT 0.0150" in mig
        assert "DEFAULT 20000000" in mig


# ═════════════════════════════════════════════════════════════════════
# 2. Pure compute
# ═════════════════════════════════════════════════════════════════════


class TestComputeRoiAddon:

    def test_simple_under_cap(self):
        rev = Decimal("100000000")    # 100M revenue saved
        comp = compute_roi_addon(rev, months_of_data=12)
        # 1.5% × 100M = 1.5M
        assert comp.raw_roi_addon_vnd == Decimal("1500000.0000")
        assert comp.capped_roi_addon_vnd == Decimal("1500000.0000")
        assert comp.cap_applied is False
        assert comp.eligibility_met is True

    def test_cap_applies(self):
        rev = Decimal("2000000000")   # 2B revenue saved
        comp = compute_roi_addon(rev, months_of_data=12)
        # 1.5% × 2B = 30M but cap = 20M
        assert comp.raw_roi_addon_vnd == Decimal("30000000.0000")
        assert comp.capped_roi_addon_vnd == DEFAULT_CAP_VND
        assert comp.cap_applied is True

    def test_eligibility_blocks_below_threshold(self):
        rev = Decimal("100000000")
        # 2 months — below MIN_MONTHS_OF_DATA=3
        comp = compute_roi_addon(rev, months_of_data=2)
        assert comp.eligibility_met is False
        assert comp.capped_roi_addon_vnd == Decimal("0.0000")
        # Raw computed for audit, just not charged
        assert comp.raw_roi_addon_vnd == Decimal("1500000.0000")

    def test_exact_threshold_eligible(self):
        comp = compute_roi_addon(Decimal("1000"), months_of_data=MIN_MONTHS_OF_DATA)
        assert comp.eligibility_met is True

    def test_zero_revenue_no_charge(self):
        comp = compute_roi_addon(Decimal("0"), months_of_data=12)
        assert comp.raw_roi_addon_vnd == Decimal("0.0000")
        assert comp.capped_roi_addon_vnd == Decimal("0.0000")
        assert comp.cap_applied is False

    def test_negative_revenue_raises(self):
        with pytest.raises(ValueError):
            compute_roi_addon(Decimal("-1"), months_of_data=12)

    def test_invalid_rate_raises(self):
        with pytest.raises(ValueError):
            compute_roi_addon(Decimal("1000"), rate=Decimal("2.0"), months_of_data=12)
        with pytest.raises(ValueError):
            compute_roi_addon(Decimal("1000"), rate=Decimal("0"), months_of_data=12)

    def test_custom_rate_and_cap(self):
        comp = compute_roi_addon(
            Decimal("10000000"),
            rate=Decimal("0.0200"),
            cap_threshold_vnd=Decimal("100000"),
            months_of_data=12,
        )
        # 2% × 10M = 200K, cap 100K → cap applied
        assert comp.raw_roi_addon_vnd == Decimal("200000.0000")
        assert comp.capped_roi_addon_vnd == Decimal("100000.0000")
        assert comp.cap_applied is True

    def test_quantize_to_4_decimals(self):
        # Odd value to force quantize
        comp = compute_roi_addon(Decimal("123456789"), months_of_data=12)
        # exponent should be -4
        assert comp.raw_roi_addon_vnd.as_tuple().exponent == -4


# ═════════════════════════════════════════════════════════════════════
# 3. Eligibility helpers
# ═════════════════════════════════════════════════════════════════════


class TestIsEligible:

    def test_opted_in_with_data(self):
        assert is_eligible(months_of_data=3, opted_in=True) is True

    def test_opted_in_insufficient_data(self):
        assert is_eligible(months_of_data=2, opted_in=True) is False

    def test_opted_out_blocks(self):
        assert is_eligible(months_of_data=12, opted_in=False) is False

    def test_exact_threshold(self):
        assert is_eligible(months_of_data=MIN_MONTHS_OF_DATA, opted_in=True) is True


# ═════════════════════════════════════════════════════════════════════
# 4. DB helpers
# ═════════════════════════════════════════════════════════════════════


class TestDbHelpers:

    @pytest.mark.asyncio
    async def test_fetch_revenue_filters_by_actioned_and_period(self):
        conn = _FakeConn()
        # Match: in-month + actioned
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c1",
            "revenue_at_risk": Decimal("100000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        })
        # Skip: not actioned
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c2",
            "revenue_at_risk": Decimal("500000"),
            "is_actioned": False,
            "actioned_at": None,
        })
        # Skip: wrong tenant
        conn.gold.append({
            "enterprise_id": ENT_B,
            "customer_external_id": "c3",
            "revenue_at_risk": Decimal("200000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        })
        # Skip: actioned in previous month
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c4",
            "revenue_at_risk": Decimal("9000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 4, 30, tzinfo=timezone.utc),
        })

        total = await fetch_actioned_revenue_at_risk(conn, ENT, billing_month=MONTH)
        assert total == Decimal("100000")

    @pytest.mark.asyncio
    async def test_months_of_data_counts_strictly_before(self):
        conn = _FakeConn()
        conn.bills = [
            {"enterprise_id": ENT, "billing_month": date(2026, 2, 1)},
            {"enterprise_id": ENT, "billing_month": date(2026, 3, 1)},
            {"enterprise_id": ENT, "billing_month": date(2026, 4, 1)},
            {"enterprise_id": ENT, "billing_month": date(2026, 5, 1)},   # NOT counted (== upto)
        ]
        n = await fetch_months_of_data(conn, ENT, upto_month=MONTH)
        assert n == 3

    @pytest.mark.asyncio
    async def test_is_opted_in_false_when_no_row(self):
        conn = _FakeConn()
        assert await is_opted_in(conn, ENT) is False

    @pytest.mark.asyncio
    async def test_is_opted_in_false_when_opted_out(self):
        conn = _FakeConn()
        conn.subs.append({
            "enterprise_id": ENT,
            "opted_in_at": datetime.now(timezone.utc),
            "opted_out_at": datetime.now(timezone.utc),
        })
        assert await is_opted_in(conn, ENT) is False


# ═════════════════════════════════════════════════════════════════════
# 5. Cron entry — compute_monthly_run
# ═════════════════════════════════════════════════════════════════════


class TestCronRun:

    @pytest.mark.asyncio
    async def test_idempotent_skips_existing(self):
        conn = _FakeConn()
        conn.subs.append({
            "enterprise_id": ENT,
            "opted_in_at": datetime.now(timezone.utc),
        })
        # Pre-existing line for the month
        conn.lines.append({
            "line_id": uuid4(),
            "enterprise_id": ENT,
            "billing_month": MONTH,
            "actioned_revenue_at_risk_vnd": Decimal("0"),
            "rate": Decimal("0.0150"),
            "cap_threshold_vnd": DEFAULT_CAP_VND,
            "raw_roi_addon_vnd": Decimal("0"),
            "capped_roi_addon_vnd": Decimal("0"),
            "cap_applied": False,
            "months_of_data": 3,
            "eligibility_met": True,
            "computed_at": datetime.now(timezone.utc),
            "computed_by_run_id": None,
            "notes": None,
        })
        report = await compute_monthly_run(conn, billing_month=MONTH)
        assert report.total_skipped == 1
        assert report.total_computed == 0
        assert len(conn.lines) == 1  # no new line inserted

    @pytest.mark.asyncio
    async def test_persists_when_no_existing_line(self):
        conn = _FakeConn()
        conn.subs.append({
            "enterprise_id": ENT,
            "opted_in_at": datetime.now(timezone.utc),
        })
        # 5 months of billing data → eligible
        for i in range(5):
            conn.bills.append({
                "enterprise_id": ENT,
                "billing_month": date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1),
            })
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c1",
            "revenue_at_risk": Decimal("100000000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        })

        report = await compute_monthly_run(conn, billing_month=MONTH)
        assert report.total_computed == 1
        assert len(conn.lines) == 1
        line = conn.lines[0]
        assert line["enterprise_id"] == ENT
        assert line["billing_month"] == MONTH
        assert line["capped_roi_addon_vnd"] == Decimal("1500000.0000")  # 1.5% × 100M

    @pytest.mark.asyncio
    async def test_preview_does_not_persist(self):
        conn = _FakeConn()
        conn.subs.append({
            "enterprise_id": ENT,
            "opted_in_at": datetime.now(timezone.utc),
        })
        conn.gold.append({
            "enterprise_id": ENT, "customer_external_id": "c1",
            "revenue_at_risk": Decimal("50000000"), "is_actioned": True,
            "actioned_at": datetime(2026, 5, 10, tzinfo=timezone.utc),
        })

        report = await compute_monthly_run(
            conn, billing_month=MONTH, persist=False,
        )
        assert report.run_kind == "preview"
        assert report.total_computed == 1
        assert len(conn.lines) == 0

    @pytest.mark.asyncio
    async def test_opted_out_tenant_not_walked(self):
        conn = _FakeConn()
        conn.subs.append({
            "enterprise_id": ENT,
            "opted_in_at": datetime.now(timezone.utc),
            "opted_out_at": datetime.now(timezone.utc),
        })
        report = await compute_monthly_run(conn, billing_month=MONTH)
        assert report.total_computed == 0
        assert report.total_skipped == 0


# ═════════════════════════════════════════════════════════════════════
# 6. Endpoint smoke
# ═════════════════════════════════════════════════════════════════════


class TestEndpoints:

    def test_opt_in_creates_row(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post("/economics/roi/opt-in", headers=HEADERS)
        assert r.status_code == 201
        assert len(conn.subs) == 1
        assert conn.subs[0]["enterprise_id"] == ENT

    def test_opt_in_reports_eligibility(self):
        conn = _FakeConn()
        for i in range(4):
            bm = date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1)
            conn.bills.append({"enterprise_id": ENT, "billing_month": bm})
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post("/economics/roi/opt-in", headers=HEADERS)
        body = r.json()
        # months_of_data computed against current month — 4 historical
        assert body["months_of_data"] >= 3
        assert body["eligibility_met"] is True

    def test_opt_out_404_when_not_opted_in(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post("/economics/roi/opt-out", headers=HEADERS)
        assert r.status_code == 404

    def test_opt_out_flips_flag(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        client.post("/economics/roi/opt-in", headers=HEADERS)
        r = client.post("/economics/roi/opt-out", headers=HEADERS)
        assert r.status_code == 200
        assert conn.subs[0]["opted_out_at"] is not None

    def test_subscription_default_not_opted_in(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get("/economics/roi/subscription", headers=HEADERS)
        body = r.json()
        assert body["opted_in"] is False

    def test_cron_compute_requires_opt_in(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post(
            "/economics/roi/cron/compute",
            headers=HEADERS,
            json={"billing_month": "2026-05-01"},
        )
        assert r.status_code == 400

    def test_preview_works_without_opt_in(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post(
            "/economics/roi/preview",
            headers=HEADERS,
            json={"billing_month": "2026-05-01"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["run_kind"] == "preview"
        assert body["total_computed"] == 1

    def test_billing_lines_404_for_missing_month(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get(
            "/economics/roi/billing-lines/2026-05-01", headers=HEADERS,
        )
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# 7. Integration — full lifecycle + cap-applied
# ═════════════════════════════════════════════════════════════════════


class TestIntegration:

    def test_full_lifecycle_under_cap(self):
        conn = _FakeConn()
        # Seed 4 prior months of data
        for i in range(4):
            bm = date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1)
            conn.bills.append({"enterprise_id": ENT, "billing_month": bm})
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c1",
            "revenue_at_risk": Decimal("100000000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        })

        app = _make_app(conn)
        client = TestClient(app)

        # Opt in
        r = client.post("/economics/roi/opt-in", headers=HEADERS)
        assert r.status_code == 201

        # Compute
        r = client.post(
            "/economics/roi/cron/compute",
            headers=HEADERS,
            json={"billing_month": "2026-05-01"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_computed"] == 1
        assert body["total_addon_vnd"] == "1500000.0000"

        # Read back
        r = client.get(
            "/economics/roi/billing-lines/2026-05-01", headers=HEADERS,
        )
        line = r.json()
        assert line["cap_applied"] is False
        assert line["eligibility_met"] is True
        assert line["capped_roi_addon_vnd"] == "1500000.0000"

    def test_cap_applied_path(self):
        conn = _FakeConn()
        for i in range(4):
            bm = date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1)
            conn.bills.append({"enterprise_id": ENT, "billing_month": bm})
        # 2B revenue → 30M raw → cap to 20M
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c1",
            "revenue_at_risk": Decimal("2000000000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        })

        app = _make_app(conn)
        client = TestClient(app)
        client.post("/economics/roi/opt-in", headers=HEADERS)
        r = client.post(
            "/economics/roi/cron/compute",
            headers=HEADERS,
            json={"billing_month": "2026-05-01"},
        )
        body = r.json()
        outcome = body["outcomes"][0]
        assert outcome["computation"]["cap_applied"] is True
        assert outcome["computation"]["capped_roi_addon_vnd"] == "20000000.0000"


# ═════════════════════════════════════════════════════════════════════
# 8. Tenant isolation + edge
# ═════════════════════════════════════════════════════════════════════


class TestIsolationAndEdge:

    @pytest.mark.asyncio
    async def test_cross_tenant_revenue_not_summed(self):
        """K-1: tenant A's actioned revenue from gold_features must NOT
        contribute to tenant B's monthly compute."""
        conn = _FakeConn()
        conn.subs.append({
            "enterprise_id": ENT_B,
            "opted_in_at": datetime.now(timezone.utc),
        })
        # Tenant A has actioned revenue
        conn.gold.append({
            "enterprise_id": ENT,
            "customer_external_id": "c1",
            "revenue_at_risk": Decimal("100000000"),
            "is_actioned": True,
            "actioned_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        })
        # Tenant B has zero
        for i in range(4):
            bm = date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1)
            conn.bills.append({"enterprise_id": ENT_B, "billing_month": bm})

        report = await compute_monthly_run(conn, billing_month=MONTH)
        assert report.total_computed == 1
        line = next(o for o in report.outcomes if o.computation is not None)
        assert line.computation.actioned_revenue_at_risk_vnd == Decimal("0")
        assert line.computation.capped_roi_addon_vnd == Decimal("0.0000")

    @pytest.mark.asyncio
    async def test_eligibility_stamp_set_once(self):
        """eligibility_confirmed_at must be set the first time eligibility
        is met and not overwritten by subsequent runs."""
        conn = _FakeConn()
        first_stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        conn.subs.append({
            "enterprise_id": ENT,
            "opted_in_at": first_stamp,
            "eligibility_confirmed_at": first_stamp,
        })
        for i in range(4):
            bm = date(2026, max(1, 5 - 1 - i), 1) if (5 - 1 - i) >= 1 else date(2025, 12 + (5 - 1 - i), 1)
            conn.bills.append({"enterprise_id": ENT, "billing_month": bm})

        await compute_monthly_run(conn, billing_month=MONTH)
        assert conn.subs[0]["eligibility_confirmed_at"] == first_stamp

    def test_zero_revenue_no_charge(self):
        comp = compute_roi_addon(Decimal("0"), months_of_data=12)
        assert comp.capped_roi_addon_vnd == Decimal("0.0000")
        assert comp.cap_applied is False

    def test_dataclass_immutable(self):
        c = RoiComputation(
            actioned_revenue_at_risk_vnd=Decimal("100"),
            rate=DEFAULT_RATE,
            cap_threshold_vnd=DEFAULT_CAP_VND,
            raw_roi_addon_vnd=Decimal("1.50"),
            capped_roi_addon_vnd=Decimal("1.50"),
            cap_applied=False,
            months_of_data=3,
            eligibility_met=True,
        )
        with pytest.raises(Exception):
            c.cap_applied = True  # type: ignore[misc]
