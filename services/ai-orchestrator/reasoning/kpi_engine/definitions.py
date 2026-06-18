"""
KPI definition loader — reads kpi_definitions table.

Pure data layer. No computation here; just typed access to the
canonical KPI rows seeded in migration 049.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import asyncpg


@dataclass(frozen=True)
class KPIDefinition:
    """One row of kpi_definitions, typed."""

    kpi_id: str
    kpi_code: str
    dept_type: str
    display_name_vi: str
    display_name_en: str
    description_vi: Optional[str]

    formula_sql: str
    target_gold_view: str

    unit: str                   # 'VND' | 'pct' | 'ratio' | 'days' | 'count' | 'score' | 'hours'
    decimal_places: int
    direction: str              # 'higher_better' | 'lower_better' | 'target_midpoint'
    target_value: Optional[Decimal]

    threshold_good: Optional[Decimal]
    threshold_warning: Optional[Decimal]
    threshold_source: Optional[str]

    is_active: bool


_LOAD_BY_CODE_SQL = """
SELECT
    kpi_id::text          AS kpi_id,
    kpi_code,
    dept_type,
    display_name_vi,
    display_name_en,
    description_vi,
    formula_sql,
    target_gold_view,
    unit,
    decimal_places,
    direction,
    target_value,
    threshold_good,
    threshold_warning,
    threshold_source,
    is_active
FROM kpi_definitions
WHERE kpi_code = $1
  AND dept_type = $2
  AND is_active = TRUE
"""


_LIST_BY_DEPT_SQL = """
SELECT
    kpi_id::text          AS kpi_id,
    kpi_code,
    dept_type,
    display_name_vi,
    display_name_en,
    description_vi,
    formula_sql,
    target_gold_view,
    unit,
    decimal_places,
    direction,
    target_value,
    threshold_good,
    threshold_warning,
    threshold_source,
    is_active
FROM kpi_definitions
WHERE dept_type = $1
  AND is_active = TRUE
ORDER BY kpi_code
"""


async def load_kpi(
    conn: asyncpg.Connection,
    *,
    kpi_code: str,
    dept_type: str,
) -> Optional[KPIDefinition]:
    """Return the canonical definition for (kpi_code, dept_type) or None.

    kpi_definitions is a global ref table (no RLS), so the caller's
    tenant scope doesn't matter.
    """
    row = await conn.fetchrow(_LOAD_BY_CODE_SQL, kpi_code, dept_type)
    if row is None:
        return None
    return _row_to_definition(row)


async def list_kpis_for_dept(
    conn: asyncpg.Connection,
    *,
    dept_type: str,
) -> list[KPIDefinition]:
    """Return all active KPI definitions for a dept_type, alphabetised
    by kpi_code."""
    rows = await conn.fetch(_LIST_BY_DEPT_SQL, dept_type)
    return [_row_to_definition(r) for r in rows]


def _row_to_definition(row) -> KPIDefinition:
    return KPIDefinition(
        kpi_id=row["kpi_id"],
        kpi_code=row["kpi_code"],
        dept_type=row["dept_type"],
        display_name_vi=row["display_name_vi"],
        display_name_en=row["display_name_en"],
        description_vi=row["description_vi"],
        formula_sql=row["formula_sql"],
        target_gold_view=row["target_gold_view"],
        unit=row["unit"],
        decimal_places=row["decimal_places"],
        direction=row["direction"],
        target_value=row["target_value"],
        threshold_good=row["threshold_good"],
        threshold_warning=row["threshold_warning"],
        threshold_source=row["threshold_source"],
        is_active=row["is_active"],
    )
