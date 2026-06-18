"""
KPI engine — P15-S11 Tuần 7 ngày 6.

SQL-first reasoning backbone per anh's directive (2026-05-15):

  "Hệ thống này không được rời xa SQL. Từ kết quả SQL, sau đó với
  RAG của từng chuyên ngành, từng đối tượng được update với thước
  đo chuẩn nhất, ta mới ra được kết quả và đánh giá được."

This module is the deterministic SQL backbone. LLM never enters here.
The pipeline is:

  1. definitions.load_kpi(kpi_code, dept_type)
       → KPIDefinition dataclass (formula_sql + threshold + direction)
  2. compute.compute_kpi(enterprise_id, dept_id, kpi_code, period)
       → runs formula_sql against target_gold_view via asyncpg
       → returns raw NUMERIC value (audit trail in sql_executed)
  3. classify.classify_value(kpi_def, raw_value)
       → 'good' | 'warning' | 'critical' (or 'no_threshold')
  4. benchmark.lookup_percentile(industry, kpi_code, value)
       → percentile of `value` vs industry_benchmarks distribution

The KPIMeasurement dataclass aggregates all 4 outputs and is the
single object the LLM render layer receives. LLM CANNOT recompute
the raw value — it can only describe what the value means.

GUC naming note (tech-debt, deferred cleanup):

  Codebase has 2 RLS GUC name conventions in flight:
    - app.enterprise_id      (migrations 001-041, set by shared/db.py
                              `acquire_for_tenant`)
    - app.current_enterprise_id (migrations 042+ including all the
                              org-hierarchy work in 046-049)
  This module bridges by setting BOTH on the scoped connection inside
  `_scoped_conn`. Cleanup migration consolidating to one name lands
  post-Build-Week.

Public API:

    from reasoning.kpi_engine import (
        KPIDefinition, KPIMeasurement,
        load_kpi, list_kpis_for_dept,
        compute_kpi, classify_value, lookup_percentile,
    )
"""
from __future__ import annotations

from .benchmark import lookup_percentile
from .classify import classify_value
from .compute import KPIMeasurement, compute_kpi
from .definitions import KPIDefinition, list_kpis_for_dept, load_kpi

__all__ = [
    "KPIDefinition",
    "KPIMeasurement",
    "classify_value",
    "compute_kpi",
    "list_kpis_for_dept",
    "load_kpi",
    "lookup_percentile",
]
