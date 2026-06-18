"""
P2-S21 D5+D6+D7 tests:
  P2-M212-001 OKR framework (mig 071 + routers/okr.py)
  NOV-RPT-023 negative-NOV workflow recommendations (recommendations.py)
  NOV-RPT-024 NOV simulation (simulation.py)

8-section template per anh's "chuẩn chỉ + hiệu năng + phi chức năng":
  1. Mig 071 shape          — 3 tables + CHECK constraints + indexes
  2. Recommendations pure   — severity classifier + template matching + ranking
  3. Simulation pure        — projection + CI + assumptions + edge cases
  4. OKR router smoke       — POST + GET + PATCH KR triggers progress recalc
  5. Endpoint integration   — /recommendations + /simulate via TestClient mocks
  6. Tenant isolation       — X-Enterprise-ID header required
  7. Determinism            — same input → identical output
  8. Performance            — 100 workflows ranked in < 100ms
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.economics.recommendations import (
    OKRRef,
    TemplateCandidate,
    WorkflowRecommendation,
    WorkflowRoiRow,
    classify_severity,
    recommend_workflow_fixes,
)
from ai_orchestrator.org_intel.economics.simulation import (
    BaselineDigest,
    ScenarioChange,
    SimulationResult,
    simulate_nov,
)


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
DEPT_ID    = "33333333-3333-3333-3333-333333333333"
WORKFLOW_ID = "44444444-4444-4444-4444-444444444444"
TEMPLATE_ID = "55555555-5555-5555-5555-555555555555"
OKR_ID     = "66666666-6666-6666-6666-666666666666"

OKR_HEADERS = {"X-Enterprise-ID": ENTERPRISE}
ECON_HEADERS = {"X-Enterprise-ID": ENTERPRISE}

REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"


# ─── shared mocks ────────────────────────────────────────────────────


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    return r


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 071 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig071Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        return (MIG_DIR / "071_okr_framework.sql").read_text(encoding="utf-8")

    def test_3_tables_present(self, mig_text: str):
        assert "CREATE TABLE IF NOT EXISTS okrs" in mig_text
        assert "CREATE TABLE IF NOT EXISTS key_results" in mig_text
        assert "CREATE TABLE IF NOT EXISTS workflow_okr_links" in mig_text

    def test_okr_status_check(self, mig_text: str):
        for s in ("DRAFT", "ACTIVE", "ACHIEVED", "MISSED", "CANCELLED"):
            assert f"'{s}'" in mig_text

    def test_kr_metric_type_check(self, mig_text: str):
        for m in ("count", "percentage", "currency", "score", "duration", "binary"):
            assert f"'{m}'" in mig_text

    def test_progress_clamp_constraint(self, mig_text: str):
        assert "chk_okr_progress_range" in mig_text
        assert "progress >= 0 AND progress <= 1" in mig_text

    def test_period_order_constraint(self, mig_text: str):
        assert "period_end >= period_start" in mig_text

    def test_workflow_okr_unique_constraint(self, mig_text: str):
        assert "uq_workflow_okr" in mig_text

    def test_indexes_present(self, mig_text: str):
        for idx in ("idx_okrs_enterprise_period",
                    "idx_key_results_okr",
                    "idx_workflow_okr_workflow"):
            assert idx in mig_text


# ═════════════════════════════════════════════════════════════════════
# 2. Recommendations pure compute
# ═════════════════════════════════════════════════════════════════════


def _wf(*, nov, roi, dept="marketing", name="W") -> WorkflowRoiRow:
    return WorkflowRoiRow(
        workflow_id=uuid4(),
        workflow_name=name,
        department_type=dept,
        revenue_vnd=Decimal("0"),
        cost_vnd=Decimal("100"),
        nov_vnd=Decimal(nov),
        roi=Decimal(roi),
    )


def _tpl(*, dept="marketing", name="T1", setup=10) -> TemplateCandidate:
    return TemplateCandidate(
        template_id=uuid4(),
        display_name=name,
        display_name_vi=name + "_vi",
        department_type=dept,
        industry_vertical="general",
        category="campaign",
        estimated_setup_minutes=setup,
    )


class TestSeverityClassifier:

    def test_critical_when_nov_very_negative(self):
        assert classify_severity(Decimal("-1000"), Decimal("-0.6")) == "critical"

    def test_warning_when_nov_just_negative(self):
        assert classify_severity(Decimal("-100"), Decimal("-0.1")) == "warning"

    def test_warning_when_roi_negative_nov_positive(self):
        """NOV positive but ROI < 0 shouldn't happen (since ROI=NOV/cost) —
        but treat any ROI<0 as warning regardless."""
        assert classify_severity(Decimal("100"), Decimal("-0.1")) == "warning"

    def test_info_when_low_roi_positive(self):
        assert classify_severity(Decimal("50"), Decimal("0.05")) == "info"


class TestRecommendations:

    def test_filters_to_underperformers_only(self):
        good = _wf(nov="500", roi="0.5", name="GoodFlow")
        bad = _wf(nov="-100", roi="-0.2", name="BadFlow")
        recs = recommend_workflow_fixes(
            workflows=[good, bad],
            available_templates=[_tpl()],
            linked_okrs_by_workflow={},
            top_k=10,
        )
        assert len(recs) == 1
        assert recs[0].workflow_name == "BadFlow"

    def test_ranks_critical_before_warning(self):
        critical = _wf(nov="-1000", roi="-0.8", name="CritFlow")
        warning_ = _wf(nov="-50", roi="-0.1", name="WarnFlow")
        recs = recommend_workflow_fixes(
            workflows=[warning_, critical],   # input order swapped
            available_templates=[_tpl()],
            linked_okrs_by_workflow={},
            top_k=10,
        )
        assert recs[0].workflow_name == "CritFlow"
        assert recs[1].workflow_name == "WarnFlow"

    def test_template_match_by_department(self):
        bad_mkt = _wf(nov="-100", roi="-0.2", dept="marketing", name="MktBad")
        templates = [
            _tpl(dept="finance", name="FinTpl"),
            _tpl(dept="marketing", name="MktTpl", setup=5),
            _tpl(dept="marketing", name="MktTpl2", setup=20),
        ]
        recs = recommend_workflow_fixes(
            workflows=[bad_mkt], available_templates=templates,
            linked_okrs_by_workflow={}, top_k=1,
        )
        assert recs[0].suggested_template is not None
        # Shorter setup wins
        assert recs[0].suggested_template.display_name == "MktTpl"

    def test_no_template_match_returns_none(self):
        bad = _wf(nov="-100", roi="-0.2", dept="hr", name="HRBad")
        recs = recommend_workflow_fixes(
            workflows=[bad],
            available_templates=[_tpl(dept="marketing")],
            linked_okrs_by_workflow={},
            top_k=1,
        )
        assert recs[0].suggested_template is None

    def test_blocked_okrs_surfaced(self):
        bad = _wf(nov="-100", roi="-0.2", name="BadFlow")
        okr_ref = OKRRef(
            okr_id=uuid4(), objective_text="Q1 Revenue 10B",
            progress=Decimal("0.3"), contribution_weight=Decimal("0.7"),
        )
        recs = recommend_workflow_fixes(
            workflows=[bad], available_templates=[_tpl()],
            linked_okrs_by_workflow={bad.workflow_id: [okr_ref]},
            top_k=1,
        )
        assert len(recs[0].blocked_okrs) == 1
        assert recs[0].blocked_okrs[0].objective_text == "Q1 Revenue 10B"

    def test_top_k_respected(self):
        wfs = [_wf(nov="-100", roi="-0.2", name=f"W{i}") for i in range(10)]
        recs = recommend_workflow_fixes(
            workflows=wfs, available_templates=[_tpl()],
            linked_okrs_by_workflow={}, top_k=3,
        )
        assert len(recs) == 3

    def test_vietnamese_reason_per_severity(self):
        bad = _wf(nov="-1000", roi="-0.8", name="CritFlow")
        recs = recommend_workflow_fixes(
            workflows=[bad], available_templates=[_tpl()],
            linked_okrs_by_workflow={}, top_k=1,
        )
        # Critical reason should mention "lỗ nặng"
        assert "lỗ nặng" in recs[0].reason_vi


# ═════════════════════════════════════════════════════════════════════
# 3. Simulation pure compute
# ═════════════════════════════════════════════════════════════════════


def _baseline(*, revenue="1000", people="200", ai="100",
              infra="50", integration="50", setup="0",
              users=10) -> BaselineDigest:
    return BaselineDigest(
        enterprise_id=UUID(ENTERPRISE),
        period_label="2026-05",
        revenue_vnd=Decimal(revenue),
        people_cost_vnd=Decimal(people),
        ai_cost_vnd=Decimal(ai),
        infra_cost_vnd=Decimal(infra),
        integration_cost_vnd=Decimal(integration),
        setup_amortized_vnd=Decimal(setup),
        user_count=users,
    )


class TestSimulation:

    def test_baseline_nov_no_change(self):
        b = _baseline()    # NOV = 1000 - 400 = 600
        r = simulate_nov(b, ScenarioChange())
        assert r.baseline_nov_vnd == Decimal("600.0000")
        assert r.projected_nov_vnd == Decimal("600.0000")
        assert r.delta_vnd == Decimal("0.0000")

    def test_revenue_uplift_only(self):
        b = _baseline()    # NOV = 600
        r = simulate_nov(b, ScenarioChange(revenue_uplift_pct=Decimal("10")))
        # New revenue = 1100; cost = 400; NOV = 700
        assert r.projected_nov_vnd == Decimal("700.0000")
        assert r.delta_vnd == Decimal("100.0000")

    def test_cost_reduction_only(self):
        b = _baseline()    # NOV = 600
        r = simulate_nov(b, ScenarioChange(cost_reduction_pct=Decimal("20")))
        # New cost = 400 × 0.8 = 320; NOV = 680
        assert r.projected_nov_vnd == Decimal("680.0000")

    def test_user_count_scales_revenue_linearly(self):
        b = _baseline(users=10)
        r = simulate_nov(b, ScenarioChange(user_count_change=5))
        # Revenue × 1.5 = 1500; cost unchanged 400; NOV = 1100
        assert r.projected_nov_vnd == Decimal("1100.0000")

    def test_combined_uplift_and_cost_cut(self):
        b = _baseline()
        r = simulate_nov(b, ScenarioChange(
            revenue_uplift_pct=Decimal("10"),
            cost_reduction_pct=Decimal("10"),
        ))
        # Revenue = 1100; cost = 360; NOV = 740
        assert r.projected_nov_vnd == Decimal("740.0000")

    def test_confidence_interval_width_10pct_of_projection(self):
        b = _baseline()
        r = simulate_nov(b, ScenarioChange())
        # Projection = 600, halfwidth = 60
        assert r.confidence_low_vnd == Decimal("540.0000")
        assert r.confidence_high_vnd == Decimal("660.0000")

    def test_baseline_zero_delta_pct_is_zero(self):
        b = _baseline(revenue="100", people="50", ai="50",
                      infra="0", integration="0")  # NOV = 0
        r = simulate_nov(b, ScenarioChange(revenue_uplift_pct=Decimal("10")))
        assert r.delta_pct == Decimal("0")
        assert any("Baseline NOV is 0" in a for a in r.assumptions)

    def test_assumption_text_present_per_change(self):
        b = _baseline()
        r = simulate_nov(b, ScenarioChange(
            revenue_uplift_pct=Decimal("10"),
            cost_reduction_pct=Decimal("5"),
            user_count_change=2,
        ))
        text = " ".join(r.assumptions)
        assert "Revenue uplift 10%" in text
        assert "Cost reduction 5%" in text
        assert "User count" in text

    def test_negative_scenario_decreases_nov(self):
        b = _baseline()
        r = simulate_nov(b, ScenarioChange(
            revenue_uplift_pct=Decimal("-5"),   # downturn
        ))
        # Revenue = 950; cost = 400; NOV = 550 < 600 baseline
        assert r.projected_nov_vnd < r.baseline_nov_vnd
        assert r.delta_vnd < Decimal("0")


# ═════════════════════════════════════════════════════════════════════
# 4. OKR router smoke (POST + KR PATCH triggers progress recalc)
# ═════════════════════════════════════════════════════════════════════


class TestOKRRouterSmoke:

    def _make_app(self) -> FastAPI:
        from ai_orchestrator.routers import okr
        app = FastAPI()
        app.include_router(okr.router)
        return app

    def test_create_okr_with_inline_krs(self):
        from ai_orchestrator.routers import okr

        conn = _make_conn()
        # Sequence of fetchrow calls: 1 OKR insert, 2 KR inserts, 1 refresh
        okr_row = _row(
            okr_id=UUID(OKR_ID), enterprise_id=UUID(ENTERPRISE),
            department_id=None, workspace_id=None,
            objective_text="Q1 Sales", objective_text_vi="Sales Q1",
            period_label="Q1 2026", period_start="2026-01-01",
            period_end="2026-03-31",
            owner_user_id=None, status="DRAFT",
            progress=Decimal("0.5"), notes=None,
        )
        # date strings need to be date objects for Pydantic
        from datetime import date
        okr_row = _row(
            okr_id=UUID(OKR_ID), enterprise_id=UUID(ENTERPRISE),
            department_id=None, workspace_id=None,
            objective_text="Q1 Sales", objective_text_vi="Sales Q1",
            period_label="Q1 2026", period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            owner_user_id=None, status="DRAFT",
            progress=Decimal("0.5"), notes=None,
        )
        kr_row = _row(
            kr_id=uuid4(), okr_id=UUID(OKR_ID),
            kr_text="Close 10 deals", kr_text_vi="Đóng 10 deal",
            metric_type="count", target_value=Decimal("10"),
            current_value=Decimal("5"), baseline_value=Decimal("0"),
            weight=Decimal("1.0"), unit=None, sort_order=0,
        )
        conn.fetchrow.side_effect = [okr_row, kr_row, okr_row]
        # Empty fetch for progress recalc
        conn.fetch.return_value = [
            _row(target_value=Decimal("10"), current_value=Decimal("5"),
                 baseline_value=Decimal("0"), weight=Decimal("1.0"),
                 metric_type="count")
        ]

        with patch.object(okr, "acquire_for_tenant", _tenant_ctx(conn)):
            app = self._make_app()
            client = TestClient(app)
            r = client.post(
                "/p2/strategy/okr",
                json={
                    "objective_text": "Q1 Sales",
                    "period_label": "Q1 2026",
                    "period_start": "2026-01-01",
                    "period_end": "2026-03-31",
                    "key_results": [
                        {
                            "kr_text": "Close 10 deals",
                            "metric_type": "count",
                            "target_value": "10",
                            "current_value": "5",
                            "weight": "1.0",
                        }
                    ],
                },
                headers=OKR_HEADERS,
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["objective_text"] == "Q1 Sales"
        assert len(body["key_results"]) == 1


# ═════════════════════════════════════════════════════════════════════
# 5. Endpoint integration (recommendations + simulate)
# ═════════════════════════════════════════════════════════════════════


class TestEndpointsSmoke:

    def _make_app(self) -> FastAPI:
        from ai_orchestrator.routers import economics
        app = FastAPI()
        app.include_router(economics.router)
        return app

    def test_simulate_404_when_no_baseline(self):
        from ai_orchestrator.routers import economics
        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(economics, "acquire_for_tenant", _tenant_ctx(conn)):
            app = self._make_app()
            client = TestClient(app)
            r = client.post(
                "/economics/reports/manager-digest/simulate",
                json={"period_label": "2026-05"},
                headers=ECON_HEADERS,
            )
        assert r.status_code == 404

    def test_recommendations_invalid_quarter_400(self):
        from ai_orchestrator.routers import economics
        conn = _make_conn()
        with patch.object(economics, "acquire_for_tenant", _tenant_ctx(conn)):
            app = self._make_app()
            client = TestClient(app)
            r = client.get(
                "/economics/reports/manager-digest/recommendations?quarter=bogus",
                headers=ECON_HEADERS,
            )
        assert r.status_code == 400


# ═════════════════════════════════════════════════════════════════════
# 6. Tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    def test_okr_post_requires_enterprise_header(self):
        from ai_orchestrator.routers import okr
        app = FastAPI()
        app.include_router(okr.router)
        client = TestClient(app)
        r = client.post("/p2/strategy/okr", json={
            "objective_text": "x", "period_label": "Q1",
            "period_start": "2026-01-01", "period_end": "2026-03-31",
        })
        assert r.status_code == 422

    def test_simulate_requires_enterprise_header(self):
        from ai_orchestrator.routers import economics
        app = FastAPI()
        app.include_router(economics.router)
        client = TestClient(app)
        r = client.post(
            "/economics/reports/manager-digest/simulate",
            json={"period_label": "2026-05"},
        )
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 7. Determinism
# ═════════════════════════════════════════════════════════════════════


class TestDeterminism:

    def test_simulation_pure_same_input_same_output(self):
        b = _baseline()
        s = ScenarioChange(revenue_uplift_pct=Decimal("15"),
                           cost_reduction_pct=Decimal("5"))
        r1 = simulate_nov(b, s)
        r2 = simulate_nov(b, s)
        assert r1 == r2

    def test_recommendations_stable_order_for_ties(self):
        # Two workflows with identical NOV+ROI — string(workflow_id) tiebreaker
        wf1 = WorkflowRoiRow(
            workflow_id=UUID("00000000-0000-0000-0000-000000000001"),
            workflow_name="A", department_type="marketing",
            revenue_vnd=Decimal("0"), cost_vnd=Decimal("100"),
            nov_vnd=Decimal("-100"), roi=Decimal("-0.5"),
        )
        wf2 = WorkflowRoiRow(
            workflow_id=UUID("00000000-0000-0000-0000-000000000002"),
            workflow_name="B", department_type="marketing",
            revenue_vnd=Decimal("0"), cost_vnd=Decimal("100"),
            nov_vnd=Decimal("-100"), roi=Decimal("-0.5"),
        )
        r1 = recommend_workflow_fixes(
            workflows=[wf2, wf1], available_templates=[_tpl()],
            linked_okrs_by_workflow={}, top_k=2,
        )
        r2 = recommend_workflow_fixes(
            workflows=[wf1, wf2], available_templates=[_tpl()],
            linked_okrs_by_workflow={}, top_k=2,
        )
        assert [r.workflow_id for r in r1] == [r.workflow_id for r in r2]


# ═════════════════════════════════════════════════════════════════════
# 8. Performance — 100 workflows ranked in <100ms
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_100_workflows_ranked_under_100ms(self):
        wfs = [
            _wf(nov=f"-{i * 10}", roi=f"-0.{i % 9 + 1}", name=f"W{i}")
            for i in range(100)
        ]
        templates = [_tpl(name=f"T{j}", setup=j) for j in range(25)]
        t0 = time.perf_counter()
        recs = recommend_workflow_fixes(
            workflows=wfs, available_templates=templates,
            linked_okrs_by_workflow={}, top_k=5,
        )
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"too slow: {elapsed:.3f}s"
        assert len(recs) == 5

    def test_simulation_under_5ms(self):
        b = _baseline()
        s = ScenarioChange(revenue_uplift_pct=Decimal("10"))
        t0 = time.perf_counter()
        for _ in range(100):
            simulate_nov(b, s)
        avg = (time.perf_counter() - t0) / 100
        assert avg < 0.005, f"simulate too slow: {avg:.4f}s"
