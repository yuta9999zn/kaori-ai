"""
Gap 4 — _handle_bronze_complete unit tests.

Covers the new behaviour: when bronze_complete carries workflow_step_id +
workflow_id + department_id (workflow-attached upload), the handler fans
out compute_kpi over every active KPI for the department's dept_type and
upserts each measurement into kpi_measurements.

Non-workflow uploads (legacy /upload, payload missing workflow_step_id)
are skipped silently — no DB activity, no KPI compute.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from ai_orchestrator.consumers import pipeline_consumer
from ai_orchestrator.reasoning.kpi_engine import KPIDefinition, KPIMeasurement


ENTERPRISE   = "11111111-1111-1111-1111-111111111111"
DEPT_ID      = "22222222-2222-2222-2222-222222222222"
WORKFLOW_ID  = "33333333-3333-3333-3333-333333333333"
STEP_ID      = "44444444-4444-4444-4444-444444444444"
BRANCH_ID    = "55555555-5555-5555-5555-555555555555"


def _kpi_def(kpi_code: str = "cac", dept_type: str = "marketing") -> KPIDefinition:
    return KPIDefinition(
        kpi_id="kpi-1",
        kpi_code=kpi_code,
        dept_type=dept_type,
        display_name_vi="Chi phí thu khách",
        display_name_en="Customer Acquisition Cost",
        description_vi="Tổng chi phí marketing / số khách mới.",
        formula_sql="SELECT 100",
        target_gold_view="gold.customer_360_marketing",
        unit="VND",
        decimal_places=0,
        direction="lower_better",
        target_value=Decimal("500000"),
        threshold_good=Decimal("400000"),
        threshold_warning=Decimal("800000"),
        threshold_source="seed",
        is_active=True,
    )


def _measurement(raw_value=Decimal("450000.0000")) -> KPIMeasurement:
    return KPIMeasurement(
        kpi_code="cac",
        dept_type="marketing",
        enterprise_id=ENTERPRISE,
        department_id=DEPT_ID,
        branch_id=BRANCH_ID,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 16),
        raw_value=raw_value,
        classification="good",
        benchmark=None,
        sql_executed="SELECT 100",
        sql_row_count=1,
        display_name_vi="Chi phí thu khách",
        unit="VND",
        decimal_places=0,
        direction="lower_better",
        threshold_good=Decimal("400000"),
        threshold_warning=Decimal("800000"),
    )


@pytest.fixture
def conn():
    c = AsyncMock()
    c.fetch.return_value = []
    c.fetchrow.return_value = None
    c.execute.return_value = "INSERT 0 1"
    return c


@pytest.fixture
def tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


# ─── Skip path ───────────────────────────────────────────────────────


class TestSkipsNonWorkflowUploads:

    @pytest.mark.asyncio
    async def test_skips_when_no_workflow_step_id(self, conn, tenant_ctx):
        """Legacy upload (no X-Workflow-Step-ID) → handler returns without
        opening a tenant connection or compute_kpi call."""
        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx):
            await pipeline_consumer._handle_bronze_complete({
                "run_id": "abc",
                "enterprise_id": ENTERPRISE,
                "row_count": 100,
            })
        conn.fetchrow.assert_not_awaited()
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_department_id_missing(self, conn, tenant_ctx):
        """Defensive — workflow_step_id present but department_id absent
        (shouldn't happen given the producer contract, but skip cleanly)."""
        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx):
            await pipeline_consumer._handle_bronze_complete({
                "enterprise_id":    ENTERPRISE,
                "workflow_id":      WORKFLOW_ID,
                "workflow_step_id": STEP_ID,
                # department_id intentionally omitted
            })
        conn.fetchrow.assert_not_awaited()


# ─── Happy path ──────────────────────────────────────────────────────


class TestKPIComputeOnWorkflowUpload:

    @pytest.mark.asyncio
    async def test_fans_out_compute_kpi_for_every_dept_kpi(
        self, conn, tenant_ctx,
    ):
        """Two active KPIs for the dept_type → compute_kpi called twice,
        each result upserted into kpi_measurements."""
        conn.fetchrow.return_value = {"dept_type": "marketing"}

        kpi_a = _kpi_def(kpi_code="cac")
        kpi_b = _kpi_def(kpi_code="ltv")

        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx), \
             patch("ai_orchestrator.reasoning.kpi_engine.list_kpis_for_dept",
                   new=AsyncMock(return_value=[kpi_a, kpi_b])), \
             patch("ai_orchestrator.reasoning.kpi_engine.compute_kpi",
                   new=AsyncMock(return_value=_measurement())) as mock_compute:
            await pipeline_consumer._handle_bronze_complete({
                "enterprise_id":    ENTERPRISE,
                "workflow_id":      WORKFLOW_ID,
                "workflow_step_id": STEP_ID,
                "department_id":    DEPT_ID,
                "branch_id":        BRANCH_ID,
            })

        # 1 dept_type lookup + 0 extra fetchrows
        assert conn.fetchrow.await_count == 1
        # compute_kpi fanned out once per KPI
        assert mock_compute.await_count == 2
        # Two upserts into kpi_measurements
        assert conn.execute.await_count == 2
        # SQL touches kpi_measurements
        assert "kpi_measurements" in conn.execute.await_args.args[0]

    @pytest.mark.asyncio
    async def test_skips_upsert_when_compute_returns_null_value(
        self, conn, tenant_ctx,
    ):
        """Gold view empty on first upload → raw_value=None → don't INSERT
        (kpi_measurements.raw_value is NOT NULL). Subsequent uploads
        once Gold catches up will populate the row."""
        conn.fetchrow.return_value = {"dept_type": "marketing"}

        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx), \
             patch("ai_orchestrator.reasoning.kpi_engine.list_kpis_for_dept",
                   new=AsyncMock(return_value=[_kpi_def()])), \
             patch("ai_orchestrator.reasoning.kpi_engine.compute_kpi",
                   new=AsyncMock(return_value=_measurement(raw_value=None))):
            await pipeline_consumer._handle_bronze_complete({
                "enterprise_id":    ENTERPRISE,
                "workflow_id":      WORKFLOW_ID,
                "workflow_step_id": STEP_ID,
                "department_id":    DEPT_ID,
            })

        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_one_kpi_failure_does_not_block_others(
        self, conn, tenant_ctx,
    ):
        """compute_kpi raising for one KPI is swallowed; remaining KPIs
        still get computed and persisted."""
        conn.fetchrow.return_value = {"dept_type": "marketing"}

        async def _compute_side_effect(*args, **kwargs):
            if kwargs.get("kpi_code") == "broken_kpi":
                raise ValueError("formula references missing column")
            return _measurement()

        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx), \
             patch("ai_orchestrator.reasoning.kpi_engine.list_kpis_for_dept",
                   new=AsyncMock(return_value=[
                       _kpi_def(kpi_code="broken_kpi"),
                       _kpi_def(kpi_code="cac"),
                   ])), \
             patch("ai_orchestrator.reasoning.kpi_engine.compute_kpi",
                   new=AsyncMock(side_effect=_compute_side_effect)):
            await pipeline_consumer._handle_bronze_complete({
                "enterprise_id":    ENTERPRISE,
                "workflow_id":      WORKFLOW_ID,
                "workflow_step_id": STEP_ID,
                "department_id":    DEPT_ID,
            })

        # broken_kpi compute raised → no INSERT. cac succeeded → 1 INSERT.
        assert conn.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_returns_early_when_dept_type_missing(
        self, conn, tenant_ctx,
    ):
        """Department row exists but dept_type column NULL → handler logs
        warning and returns; no KPI compute attempted."""
        conn.fetchrow.return_value = {"dept_type": None}

        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx), \
             patch("ai_orchestrator.reasoning.kpi_engine.compute_kpi",
                   new=AsyncMock()) as mock_compute:
            await pipeline_consumer._handle_bronze_complete({
                "enterprise_id":    ENTERPRISE,
                "workflow_id":      WORKFLOW_ID,
                "workflow_step_id": STEP_ID,
                "department_id":    DEPT_ID,
            })

        mock_compute.assert_not_awaited()
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_early_when_dept_has_no_active_kpis(
        self, conn, tenant_ctx,
    ):
        """dept_type resolves but kpi_definitions has no active row for
        it (e.g. dept_type='kho_van' before its KPIs are seeded)."""
        conn.fetchrow.return_value = {"dept_type": "warehouse"}

        with patch.object(pipeline_consumer, "acquire_for_tenant", tenant_ctx), \
             patch("ai_orchestrator.reasoning.kpi_engine.list_kpis_for_dept",
                   new=AsyncMock(return_value=[])), \
             patch("ai_orchestrator.reasoning.kpi_engine.compute_kpi",
                   new=AsyncMock()) as mock_compute:
            await pipeline_consumer._handle_bronze_complete({
                "enterprise_id":    ENTERPRISE,
                "workflow_id":      WORKFLOW_ID,
                "workflow_step_id": STEP_ID,
                "department_id":    DEPT_ID,
            })

        mock_compute.assert_not_awaited()
        conn.execute.assert_not_awaited()
