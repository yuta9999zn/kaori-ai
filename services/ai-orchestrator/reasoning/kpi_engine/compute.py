"""
KPI computer — renders formula_sql against the target Gold view.

The deterministic SQL backbone. Given (enterprise_id, dept_id, kpi_code,
period), this module:

  1. Loads the KPI definition (formula_sql + target_gold_view).
  2. Renders the Jinja-style placeholders (whitelisted set only).
  3. Executes the rendered SQL against the asyncpg connection.
  4. Records sql_executed + row_count in the returned dataclass for
     audit trail (where did this number come from?).
  5. Optionally classifies the value + looks up the benchmark
     percentile so a single call returns the full bundle.

LLM never touches this code path. It receives KPIMeasurement and
renders the explanation only.

Security:
- formula_sql is OPERATOR-AUTHORED data from kpi_definitions seed.
- We allow ONLY whitelisted Jinja placeholders to prevent SQL injection
  from a future bad seed. Unknown placeholders raise ValueError.
- target_gold_view is similarly validated against an allow-list of
  Kaori-managed view names (must start with `gold.` or `silver.`).
- asyncpg's parametrised query mode is used for the actual values
  ($1, $2, ...); placeholder substitution happens BEFORE the asyncpg
  call so it can be cached + audited.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Union

import asyncpg

from .benchmark import BenchmarkLookup, lookup_percentile
from .classify import classify_value
from .definitions import KPIDefinition, load_kpi


# Allow-list per spec: kpi_engine renders formula_sql only with these
# placeholders. Any unknown placeholder → ValueError (defends against
# accidental SQL injection if a bad row lands in kpi_definitions).
_ALLOWED_PLACEHOLDERS = {
    "enterprise_id",
    "department_id",
    "branch_id",
    "period_start",
    "period_end",
    "view",
}

# Gold/Silver view name pattern. Anything else gets rejected.
_VIEW_NAME_RE = re.compile(r"^(gold|silver)\.[a-z_][a-z0-9_]*$")

# Jinja-ish double-brace pattern. We only support {{name}} — no logic,
# no filters. Operator who wants if/loop should write a Python view.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass(frozen=True)
class KPIMeasurement:
    """One computed KPI bundle. Single object the LLM render layer
    receives. Carries enough context to display + audit."""

    kpi_code: str
    dept_type: str
    enterprise_id: str
    department_id: str
    branch_id: Optional[str]
    period_start: date
    period_end: date

    raw_value: Optional[Decimal]      # None when SQL returns no row
    classification: str               # 'good'|'warning'|'critical'|'no_threshold'

    # Benchmark snapshot (None when no industry benchmark exists or
    # caller skipped the lookup).
    benchmark: Optional[BenchmarkLookup]

    # Audit trail.
    sql_executed: str                 # the rendered SQL string
    sql_row_count: int                # number of rows returned (usually 1)

    # KPI metadata (denormalised for convenience in LLM rendering).
    display_name_vi: str
    unit: str
    decimal_places: int
    direction: str
    threshold_good: Optional[Decimal]
    threshold_warning: Optional[Decimal]


def render_formula(
    formula_sql: str,
    *,
    target_view: str,
) -> str:
    """Substitute {{view}} with the validated target_view name.

    Other placeholders ({{enterprise_id}}, etc.) are converted to
    asyncpg-style $N parameters in `_to_async_params` — they stay as
    placeholders here so caller knows the parameter positions.

    Validates:
      - target_view matches gold.* or silver.* pattern (no schema spoofing).
      - Every placeholder is in the allow-list.
    """
    if not _VIEW_NAME_RE.match(target_view):
        raise ValueError(
            f"target_view {target_view!r} not allowed — must match "
            f"^(gold|silver)\\.[a-z_][a-z0-9_]*$ to prevent schema spoofing."
        )

    # Check ALL placeholders against allow-list before substituting view.
    unknown = set(_PLACEHOLDER_RE.findall(formula_sql)) - _ALLOWED_PLACEHOLDERS
    if unknown:
        raise ValueError(
            f"formula_sql contains unknown placeholders {unknown!r}. "
            f"Allowed: {sorted(_ALLOWED_PLACEHOLDERS)!r}."
        )

    return formula_sql.replace("{{view}}", target_view).replace("{{ view }}", target_view)


def _to_async_params(rendered_sql: str, params: dict) -> tuple[str, list]:
    """Convert {{name}} → $N positional params for asyncpg.

    Returns (final_sql, ordered_param_list). Preserves first-appearance
    order so the audit trail SQL is readable.
    """
    seen_order: list[str] = []
    seen_set: set[str] = set()

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in seen_set:
            seen_set.add(name)
            seen_order.append(name)
        idx = seen_order.index(name) + 1
        return f"${idx}"

    final_sql = _PLACEHOLDER_RE.sub(replace, rendered_sql)
    ordered_values = [params[name] for name in seen_order]
    return final_sql, ordered_values


async def compute_kpi(
    conn: asyncpg.Connection,
    *,
    enterprise_id: str,
    department_id: str,
    kpi_code: str,
    dept_type: str,
    period_start: date,
    period_end: date,
    branch_id: Optional[str] = None,
    industry: Optional[str] = None,
    region: str = "VN",
    skip_benchmark: bool = False,
) -> KPIMeasurement:
    """Execute one KPI computation end-to-end.

    Raises:
        ValueError if the KPI definition is missing or has a bad shape.
    """
    kpi_def = await load_kpi(conn, kpi_code=kpi_code, dept_type=dept_type)
    if kpi_def is None:
        raise ValueError(
            f"No active KPI definition for kpi_code={kpi_code!r} "
            f"dept_type={dept_type!r}. Seed via migration 049."
        )

    rendered = render_formula(kpi_def.formula_sql, target_view=kpi_def.target_gold_view)
    bind = {
        "enterprise_id": enterprise_id,
        "department_id": department_id,
        "branch_id": branch_id,
        "period_start": period_start,
        "period_end": period_end,
    }
    final_sql, params = _to_async_params(rendered, bind)

    # Audit-friendly compact form: collapse whitespace for the
    # sql_executed field so JSON storage is tidy. Original spacing
    # preserved in the formula_sql source.
    sql_executed = " ".join(final_sql.split())

    row = await conn.fetchrow(final_sql, *params)
    raw_value: Optional[Decimal] = None
    if row is not None:
        # The formula MUST yield a single scalar — by convention the
        # first column. We accept Decimal / numeric / float / int.
        first = row[0]
        if first is not None:
            raw_value = Decimal(str(first)) if not isinstance(first, Decimal) else first

    classification = classify_value(kpi_def, raw_value)

    bench: Optional[BenchmarkLookup] = None
    if not skip_benchmark and raw_value is not None and industry is not None:
        higher_better = kpi_def.direction == "higher_better"
        bench = await lookup_percentile(
            conn,
            industry=industry,
            kpi_code=kpi_code,
            raw_value=raw_value,
            region=region,
            higher_is_better=higher_better,
        )

    return KPIMeasurement(
        kpi_code=kpi_code,
        dept_type=dept_type,
        enterprise_id=enterprise_id,
        department_id=department_id,
        branch_id=branch_id,
        period_start=period_start,
        period_end=period_end,
        raw_value=raw_value,
        classification=classification,
        benchmark=bench,
        sql_executed=sql_executed,
        sql_row_count=1 if row is not None else 0,
        display_name_vi=kpi_def.display_name_vi,
        unit=kpi_def.unit,
        decimal_places=kpi_def.decimal_places,
        direction=kpi_def.direction,
        threshold_good=kpi_def.threshold_good,
        threshold_warning=kpi_def.threshold_warning,
    )
