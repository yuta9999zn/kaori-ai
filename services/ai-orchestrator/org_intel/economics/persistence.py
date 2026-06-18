"""
NOV digest persistence — UPSERT + trend read for the monthly digest.

Phase 1.5 P15-S9 D7. The pure computation lives in nov.py / cost.py /
revenue.py; this module is the thin DB layer the workflow + endpoint
both consume so the SQL doesn't get duplicated across consumers.

Single source of truth for:
  * upsert_monthly_digest()  — insert-or-update, bumps `revision` on
    re-write so the dashboard can surface "revised N times" hints.
  * fetch_current_digest()   — latest digest for a tenant (any month).
  * fetch_trend()            — last N months for the trend tile.

Tenant scoping (K-1) is the caller's responsibility — pass an asyncpg
Connection that already has `app.current_enterprise_id` set (the
shared.db.acquire_for_tenant context manager populates the GUC; RLS
on `nov_monthly_digests` enforces it).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from .nov import NOVResult


@dataclass(frozen=True)
class MonthlyDigestRow:
    """Read shape — what fetch_current_digest / fetch_trend return.

    Mirrors the migration 043 columns; using a frozen dataclass keeps
    callers (router, workflow) typed without needing pydantic in modules
    that don't already import it.
    """
    enterprise_id: UUID
    month_start: date
    revenue_vnd: Decimal
    cost_vnd: Decimal
    nov_vnd: Decimal
    revenue_method: str
    revenue_confidence: Decimal
    people_cost_vnd: Decimal
    ai_cost_vnd: Decimal
    infra_cost_vnd: Decimal
    integration_cost_vnd: Decimal
    revision: int

    def is_negative(self) -> bool:
        return self.nov_vnd < 0


async def upsert_monthly_digest(
    conn: Any,
    *,
    enterprise_id: UUID,
    month_start: date,
    nov_result: NOVResult,
    cost_breakdown: dict[str, Decimal] | None = None,
    written_by_workflow_run: str | None = None,
    notes: str | None = None,
) -> MonthlyDigestRow:
    """INSERT-or-UPDATE the digest for (enterprise, month).

    On conflict the row's NOV fields are overwritten + `revision` is
    bumped — that single counter is what the dashboard renders as
    "revised 2x this month" if a late cost correction triggers
    recompute.

    `cost_breakdown` is an optional dict {people, ai, infra, integration}.
    Missing keys default to 0; passing the dict is recommended so the
    drill-down tile on the dashboard isn't all zeroes.
    """
    cb = cost_breakdown or {}
    row = await conn.fetchrow(
        """
        INSERT INTO nov_monthly_digests (
            enterprise_id, month_start,
            revenue_vnd, cost_vnd, nov_vnd,
            revenue_method, revenue_confidence,
            people_cost_vnd, ai_cost_vnd, infra_cost_vnd, integration_cost_vnd,
            written_by_workflow_run, notes,
            revision
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 1)
        ON CONFLICT (enterprise_id, month_start) DO UPDATE SET
            revenue_vnd          = EXCLUDED.revenue_vnd,
            cost_vnd             = EXCLUDED.cost_vnd,
            nov_vnd              = EXCLUDED.nov_vnd,
            revenue_method       = EXCLUDED.revenue_method,
            revenue_confidence   = EXCLUDED.revenue_confidence,
            people_cost_vnd      = EXCLUDED.people_cost_vnd,
            ai_cost_vnd          = EXCLUDED.ai_cost_vnd,
            infra_cost_vnd       = EXCLUDED.infra_cost_vnd,
            integration_cost_vnd = EXCLUDED.integration_cost_vnd,
            written_by_workflow_run = EXCLUDED.written_by_workflow_run,
            notes                = EXCLUDED.notes,
            computed_at          = now(),
            revision             = nov_monthly_digests.revision + 1
        RETURNING enterprise_id, month_start, revenue_vnd, cost_vnd, nov_vnd,
                  revenue_method, revenue_confidence,
                  people_cost_vnd, ai_cost_vnd, infra_cost_vnd, integration_cost_vnd,
                  revision
        """,
        enterprise_id, month_start,
        nov_result.revenue_vnd, nov_result.cost_vnd, nov_result.nov_vnd,
        nov_result.revenue_method, nov_result.revenue_confidence,
        cb.get("people", Decimal("0")),
        cb.get("ai", Decimal("0")),
        cb.get("infra", Decimal("0")),
        cb.get("integration", Decimal("0")),
        written_by_workflow_run,
        notes,
    )
    return _row_to_digest(row)


async def fetch_current_digest(
    conn: Any, *, enterprise_id: UUID,
) -> MonthlyDigestRow | None:
    """Most recent month's digest for the tenant. Returns None when no
    digest has been written yet (new tenant or workflow disabled)."""
    row = await conn.fetchrow(
        """
        SELECT enterprise_id, month_start, revenue_vnd, cost_vnd, nov_vnd,
               revenue_method, revenue_confidence,
               people_cost_vnd, ai_cost_vnd, infra_cost_vnd, integration_cost_vnd,
               revision
        FROM nov_monthly_digests
        WHERE enterprise_id = $1
        ORDER BY month_start DESC
        LIMIT 1
        """,
        enterprise_id,
    )
    return _row_to_digest(row) if row else None


async def fetch_trend(
    conn: Any, *, enterprise_id: UUID, months: int = 6,
) -> list[MonthlyDigestRow]:
    """Last N months of digests, oldest → newest (chart-friendly).

    The DB query orders DESC (uses the trend index); we reverse in
    Python so the caller can plot left-to-right without thinking about
    it. N defaults to 6 because the dashboard tile shows half a year.
    """
    rows = await conn.fetch(
        """
        SELECT enterprise_id, month_start, revenue_vnd, cost_vnd, nov_vnd,
               revenue_method, revenue_confidence,
               people_cost_vnd, ai_cost_vnd, infra_cost_vnd, integration_cost_vnd,
               revision
        FROM nov_monthly_digests
        WHERE enterprise_id = $1
        ORDER BY month_start DESC
        LIMIT $2
        """,
        enterprise_id, months,
    )
    return [_row_to_digest(r) for r in reversed(rows)]


async def fetch_quarter_window(
    conn: Any, *, enterprise_id: UUID, quarter_start: date, quarter_end: date,
) -> list[MonthlyDigestRow]:
    """All digests whose month_start falls inside [quarter_start, quarter_end].

    Used by NOV-RPT-020 CFO digest endpoint — typically 3 rows per
    quarter. The window can be partial (e.g. quarter just started); the
    digest builder handles 1-3 rows gracefully.
    """
    rows = await conn.fetch(
        """
        SELECT enterprise_id, month_start, revenue_vnd, cost_vnd, nov_vnd,
               revenue_method, revenue_confidence,
               people_cost_vnd, ai_cost_vnd, infra_cost_vnd, integration_cost_vnd,
               revision
        FROM nov_monthly_digests
        WHERE enterprise_id = $1
          AND month_start BETWEEN $2 AND $3
        ORDER BY month_start ASC
        """,
        enterprise_id, quarter_start, quarter_end,
    )
    return [_row_to_digest(r) for r in rows]


def _row_to_digest(row: Any) -> MonthlyDigestRow:
    return MonthlyDigestRow(
        enterprise_id=row["enterprise_id"],
        month_start=row["month_start"],
        revenue_vnd=row["revenue_vnd"],
        cost_vnd=row["cost_vnd"],
        nov_vnd=row["nov_vnd"],
        revenue_method=row["revenue_method"],
        revenue_confidence=row["revenue_confidence"],
        people_cost_vnd=row["people_cost_vnd"],
        ai_cost_vnd=row["ai_cost_vnd"],
        infra_cost_vnd=row["infra_cost_vnd"],
        integration_cost_vnd=row["integration_cost_vnd"],
        revision=row["revision"],
    )
