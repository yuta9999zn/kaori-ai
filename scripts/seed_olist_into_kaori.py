#!/usr/bin/env python3
"""
Olist → Kaori seed — P15-S11 Tuần 7 ngày 7 Build Week prep.

Reads the Olist Brazilian E-commerce CSVs from data/kaggle/olist/ and
inserts them into the Kaori multi-tenant schema as if a real enterprise
had uploaded each file through the wizard:

    workspace "Olist Brazil"
      └── enterprise "Olist Brazilian E-commerce 2018"
            └── branch (default "Trụ sở chính" auto-seeded by mig 046)
                  └── 6 departments (auto-seeded by mig 046)
                        ├── sales            ← orders, customers, sellers
                        ├── customer_service ← order_reviews
                        ├── warehouse        ← products, geolocation
                        └── finance          ← order_payments

Each CSV becomes one `bronze_files` row + N `bronze_rows` rows
(JSONB raw_data per CSV line). The Schema Detection + Silver cleaning
runs are NOT exercised here — this script only seeds Bronze so the
Data Explorer landing page has something to show.

Usage:

    # Dry run — print summary, no DB writes
    python scripts/seed_olist_into_kaori.py --dry-run

    # Real run — needs DATABASE_URL env (default localhost:5432/kaori)
    python scripts/seed_olist_into_kaori.py --real --sample-rows 1000

    # Full ingest (warning: 5 minutes + ~500MB bronze_rows storage)
    python scripts/seed_olist_into_kaori.py --real --sample-rows 0

Re-running is idempotent: workspace/enterprise lookup by name, files
upserted by sha256 (per K-8 bronze idempotency).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None  # graceful for --dry-run on a clean venv

try:
    import pandas as pd
except ImportError:
    print("pandas required: pip install pandas", file=sys.stderr)
    sys.exit(2)


# ─── Olist CSV → Kaori department mapping ────────────────────────────


@dataclass(frozen=True)
class CSVPlan:
    """One CSV → one bronze_file in a target department."""
    filename: str
    dept_type: str         # 'sales' | 'customer_service' | 'warehouse' | 'finance'
    domain: str            # business meaning ('customers', 'orders', 'reviews', ...)


OLIST_PLAN = [
    CSVPlan("olist_customers_dataset.csv",       "sales",            "customers"),
    CSVPlan("olist_orders_dataset.csv",          "sales",            "orders"),
    CSVPlan("olist_order_items_dataset.csv",     "sales",            "order_items"),
    CSVPlan("olist_sellers_dataset.csv",         "sales",            "sellers"),
    CSVPlan("olist_order_reviews_dataset.csv",   "customer_service", "reviews"),
    CSVPlan("olist_products_dataset.csv",        "warehouse",        "products"),
    CSVPlan("olist_geolocation_dataset.csv",     "warehouse",        "geolocation"),
    CSVPlan("olist_order_payments_dataset.csv",  "finance",          "payments"),
]

WORKSPACE_NAME = "Olist Brazil"
ENTERPRISE_NAME = "Olist Brazilian E-commerce 2018"
DEFAULT_SOURCE_NAME = "Manual upload"


# ─── Dry-run accumulator ─────────────────────────────────────────────


@dataclass
class SeedSummary:
    workspace_id: Optional[str] = None
    enterprise_id: Optional[str] = None
    branch_id: Optional[str] = None
    files_by_dept: dict[str, int] = None  # dept_name → file count
    rows_by_dept: dict[str, int] = None
    total_bytes: int = 0
    dry_run: bool = True

    def __post_init__(self):
        if self.files_by_dept is None:
            self.files_by_dept = {}
        if self.rows_by_dept is None:
            self.rows_by_dept = {}

    def add_file(self, dept_type: str, row_count: int, size_bytes: int) -> None:
        self.files_by_dept[dept_type] = self.files_by_dept.get(dept_type, 0) + 1
        self.rows_by_dept[dept_type] = self.rows_by_dept.get(dept_type, 0) + row_count
        self.total_bytes += size_bytes

    def print(self) -> None:
        mode = "DRY-RUN (no DB writes)" if self.dry_run else "REAL"
        print(f"\n=== Olist seed summary [{mode}] ===")
        print(f"workspace_id   = {self.workspace_id}")
        print(f"enterprise_id  = {self.enterprise_id}")
        print(f"branch_id      = {self.branch_id}")
        print()
        for dept in ("sales", "customer_service", "warehouse", "finance"):
            files = self.files_by_dept.get(dept, 0)
            rows = self.rows_by_dept.get(dept, 0)
            if files == 0:
                continue
            print(f"  {dept:>16}: {files} files, {rows:>10,} rows")
        print(f"\n  Total raw size: {self.total_bytes / (1024 * 1024):.1f} MB")
        print()


# ─── Silver projection — pure dict→dict converters per Olist CSV ─────
#
# Anh's directive 2026-05-15:
#   "Cần phải có đầy đủ ba lớp đồng bạc vàng, và có chức năng nhiệm vụ
#   riêng, không để chồng chéo."
#
# Each function takes a Bronze raw row (dict[str, str] from CSV) and
# returns a typed dict matching one Silver table's column shape, OR
# None if the row should be skipped (e.g. malformed timestamp).
#
# Build Week reality: this is the Bronze→Silver projection step that
# Phase 2 ETL will own. Co-located in the seed script today so the demo
# fills both layers in one pass; Phase 2 splits into a real worker.
#
# Strict separation rule: these functions write to Silver per-domain
# tables ONLY (silver_customers / silver_orders / silver_tickets /
# silver_finance_periods). They do NOT modify Bronze, and Gold views
# never call them.


def _parse_ts(value: str | None) -> Optional[datetime]:
    """Olist timestamps are 'YYYY-MM-DD HH:MM:SS' or empty."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Try the two formats Olist uses (timestamp vs date-only).
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_decimal(value: str | None) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def project_customer_row(raw: dict) -> Optional[dict]:
    """olist_customers_dataset.csv → silver_customers row.

    Returns dict keyed by silver_customers column names, or None if the
    row has no usable customer_id."""
    cid = (raw.get("customer_unique_id") or raw.get("customer_id") or "").strip()
    if not cid:
        return None
    return {
        "customer_external_id": cid,
        "name":                 None,                                # PII not in Olist
        "email":                None,
        "phone":                None,
        "acquired_at":          None,
        "acquisition_channel":  "olist_marketplace",
        "marketing_spend":      None,
        "segment":              raw.get("customer_state") or None,
    }


def project_order_row(raw: dict) -> Optional[dict]:
    """olist_orders_dataset.csv → silver_orders row.

    Olist 'order_status' values: delivered / shipped / canceled / processing / etc.
    Mapped to our deal_status enum (won / lost / open / cancelled / pending)."""
    order_id = (raw.get("order_id") or "").strip()
    if not order_id:
        return None
    status_map = {
        "delivered":  "won",
        "shipped":    "open",
        "processing": "open",
        "invoiced":   "open",
        "created":    "pending",
        "approved":   "pending",
        "canceled":   "cancelled",
        "unavailable": "lost",
    }
    olist_status = (raw.get("order_status") or "").strip().lower()
    return {
        "order_external_id":      order_id,
        "customer_external_id":   (raw.get("customer_id") or "").strip() or None,
        "rep_user_id":            None,
        "lead_external_id":       None,
        "deal_status":            status_map.get(olist_status, "pending"),
        "deal_value":             None,                              # comes from order_items + payments join
        "quota_target":           None,
        "created_at_source":      _parse_ts(raw.get("order_purchase_timestamp")),
        "closed_at":              _parse_ts(raw.get("order_delivered_customer_date")),
        "campaign_external_id":   None,
        "campaign_revenue":       None,
        "campaign_spend":         None,
        "campaign_date":          None,
    }


def project_review_row(raw: dict) -> Optional[dict]:
    """olist_order_reviews_dataset.csv → silver_tickets row.

    Each review = one CS ticket (Build Week proxy)."""
    review_id = (raw.get("review_id") or "").strip()
    if not review_id:
        return None
    score = raw.get("review_score")
    csat = float(score) if (score and score.strip().isdigit()) else None
    return {
        "ticket_external_id":    review_id,
        "customer_external_id":  (raw.get("customer_id") or "").strip() or None,
        "agent_user_id":         None,
        "csat_rating":           csat,
        "nps_score":             None,                               # CSAT, not NPS
        "rated_at":              _parse_ts(raw.get("review_creation_date")),
        "created_at_source":     _parse_ts(raw.get("review_creation_date")),
        "first_response_at":     _parse_ts(raw.get("review_answer_timestamp")),
        "resolved_at":           _parse_ts(raw.get("review_answer_timestamp")),
        "escalated":             (csat is not None and csat <= 2.0),
        "category":              "review",
        "priority":              "normal",
    }


def project_payment_row(raw: dict) -> Optional[dict]:
    """olist_order_payments_dataset.csv → one (order_id, payment_value) tuple.

    NOTE: Payments aggregate to silver_finance_periods by year-month at
    the BATCH step (aggregate_finance_periods), not row-by-row. This
    projector returns the raw row for the batch aggregator instead of a
    final Silver shape. None means skip."""
    val = _parse_decimal(raw.get("payment_value"))
    if val is None:
        return None
    return {
        "order_id":      (raw.get("order_id") or "").strip() or None,
        "payment_value": val,
        # Olist payments have no timestamp column directly; we leave
        # period assignment to the aggregator which joins with orders.
    }


def aggregate_finance_periods(
    payment_rows: list[dict],
    order_index: dict[str, datetime],
) -> list[dict]:
    """Roll payment rows into per-month silver_finance_periods rows.

    payment_rows = output of project_payment_row over the payments CSV.
    order_index  = order_id → order_purchase_timestamp from the orders CSV.

    Returns one dict per (year, month) with revenue + period set; other
    columns left None (Phase 2 will compute proper P&L)."""
    bucket: dict[str, float] = {}
    for pay in payment_rows:
        oid = pay.get("order_id")
        if not oid:
            continue
        ts = order_index.get(oid)
        if ts is None:
            continue
        key = ts.strftime("%Y-%m-01")
        bucket[key] = bucket.get(key, 0.0) + float(pay["payment_value"])
    rows: list[dict] = []
    for period_str, revenue in sorted(bucket.items()):
        rows.append({
            "period":           period_str,
            "revenue":          revenue,
            "cogs":             None,
            "operating_expense": None,
            "annual_revenue":   None,
            "ar_balance":       None,
            "cash_balance":     None,
            "monthly_burn":     None,
            "current_assets":   None,
            "current_liabilities": None,
        })
    return rows


# ─── CSV reading + hashing ───────────────────────────────────────────


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_rows(path: Path, sample_rows: int) -> Iterable[dict]:
    """Read CSV → yield dict per row. Stops at sample_rows (0 = all)."""
    nrows = None if sample_rows == 0 else sample_rows
    df = pd.read_csv(path, nrows=nrows, dtype=str, keep_default_na=False)
    for _, row in df.iterrows():
        yield row.to_dict()


# ─── Real-mode DB inserts ────────────────────────────────────────────


async def get_or_create_workspace(conn) -> str:
    row = await conn.fetchrow(
        "SELECT workspace_id::text FROM workspaces WHERE name = $1",
        WORKSPACE_NAME,
    )
    if row:
        return row["workspace_id"]
    row = await conn.fetchrow(
        """INSERT INTO workspaces (name, plan_code, status)
           VALUES ($1, 'PILOT', 'active')
           RETURNING workspace_id::text""",
        WORKSPACE_NAME,
    )
    return row["workspace_id"]


async def get_or_create_enterprise(conn, workspace_id: str) -> str:
    row = await conn.fetchrow(
        """SELECT enterprise_id::text FROM enterprises
           WHERE workspace_id = $1 AND name = $2""",
        workspace_id, ENTERPRISE_NAME,
    )
    if row:
        return row["enterprise_id"]
    row = await conn.fetchrow(
        """INSERT INTO enterprises (workspace_id, name, industry, timezone, locale, status)
           VALUES ($1, $2, 'ecommerce', 'America/Sao_Paulo', 'pt', 'active')
           RETURNING enterprise_id::text""",
        workspace_id, ENTERPRISE_NAME,
    )
    return row["enterprise_id"]


async def get_default_branch(conn, enterprise_id: str) -> str:
    row = await conn.fetchrow(
        """SELECT branch_id::text FROM branches
           WHERE enterprise_id = $1 AND is_default = TRUE""",
        enterprise_id,
    )
    if row is None:
        raise RuntimeError(
            f"No default branch for enterprise {enterprise_id} — migration 046 "
            "backfill should have created one. Check migrations applied."
        )
    return row["branch_id"]


async def get_dept_id(conn, enterprise_id: str, dept_type: str) -> str:
    row = await conn.fetchrow(
        """SELECT department_id::text FROM departments
           WHERE enterprise_id = $1 AND dept_type = $2 AND status = 'active'
           ORDER BY created_at ASC LIMIT 1""",
        enterprise_id, dept_type,
    )
    if row is None:
        raise RuntimeError(f"No active department of type {dept_type}")
    return row["department_id"]


async def get_default_source(conn, enterprise_id: str, dept_id: str) -> str:
    row = await conn.fetchrow(
        """SELECT source_id::text FROM data_sources
           WHERE enterprise_id = $1 AND department_id = $2 AND name = $3""",
        enterprise_id, dept_id, DEFAULT_SOURCE_NAME,
    )
    if row is None:
        raise RuntimeError(f"No '{DEFAULT_SOURCE_NAME}' source for dept {dept_id}")
    return row["source_id"]


async def upsert_pipeline_run(conn, enterprise_id: str, filename: str, sha: str) -> str:
    row = await conn.fetchrow(
        """SELECT run_id::text FROM pipeline_runs
           WHERE enterprise_id = $1 AND sha256 = $2""",
        enterprise_id, sha,
    )
    if row:
        return row["run_id"]
    row = await conn.fetchrow(
        """INSERT INTO pipeline_runs
              (enterprise_id, filename, sha256, detected_language, status, sheet_count)
           VALUES ($1, $2, $3, 'auto', 'bronze_complete', 1)
           RETURNING run_id::text""",
        enterprise_id, filename, sha,
    )
    return row["run_id"]


async def insert_bronze_file(
    conn,
    *,
    enterprise_id: str, branch_id: str, dept_id: str, source_id: str,
    run_id: str, filename: str, sha: str, row_count: int,
) -> str:
    """Upsert one bronze_files row keyed by (enterprise_id, sha256)."""
    row = await conn.fetchrow(
        """SELECT file_id::text FROM bronze_files
           WHERE enterprise_id = $1 AND sha256 = $2""",
        enterprise_id, sha,
    )
    if row:
        return row["file_id"]
    row = await conn.fetchrow(
        """INSERT INTO bronze_files
              (run_id, enterprise_id, branch_id, department_id, source_id,
               filename, sheet_name, sheet_index, sha256, row_count, uploaded_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, 0, $8, $9, NOW())
           RETURNING file_id::text""",
        run_id, enterprise_id, branch_id, dept_id, source_id,
        filename, filename.replace(".csv", ""), sha, row_count,
    )
    return row["file_id"]


async def insert_silver_customers(
    conn,
    *,
    enterprise_id: str, branch_id: str, dept_id: str, source_id: str,
    run_id: str, raw_rows: list[dict],
) -> int:
    """Project Bronze customer rows → silver_customers."""
    records = []
    for raw in raw_rows:
        proj = project_customer_row(raw)
        if proj is None:
            continue
        records.append((
            enterprise_id, proj["customer_external_id"],
            branch_id, dept_id,
            proj["name"], proj["email"], proj["phone"],
            proj["acquired_at"], proj["acquisition_channel"],
            proj["marketing_spend"], proj["segment"],
            source_id, run_id,
        ))
    if not records:
        return 0
    await conn.executemany(
        """INSERT INTO silver_customers
              (enterprise_id, customer_external_id,
               branch_id, department_id,
               name, email, phone,
               acquired_at, acquisition_channel,
               marketing_spend, segment,
               source_id, bronze_run_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
           ON CONFLICT (enterprise_id, customer_external_id) DO NOTHING""",
        records,
    )
    return len(records)


async def insert_silver_orders(
    conn,
    *,
    enterprise_id: str, branch_id: str, dept_id: str, source_id: str,
    run_id: str, raw_rows: list[dict],
) -> int:
    """Project Bronze order rows → silver_orders."""
    records = []
    for raw in raw_rows:
        proj = project_order_row(raw)
        if proj is None:
            continue
        records.append((
            enterprise_id, proj["order_external_id"],
            branch_id, dept_id,
            proj["customer_external_id"], proj["rep_user_id"], proj["lead_external_id"],
            proj["deal_status"], proj["deal_value"], proj["quota_target"],
            proj["created_at_source"], proj["closed_at"],
            proj["campaign_external_id"], proj["campaign_revenue"],
            proj["campaign_spend"], proj["campaign_date"],
            source_id, run_id,
        ))
    if not records:
        return 0
    await conn.executemany(
        """INSERT INTO silver_orders
              (enterprise_id, order_external_id,
               branch_id, department_id,
               customer_external_id, rep_user_id, lead_external_id,
               deal_status, deal_value, quota_target,
               created_at_source, closed_at,
               campaign_external_id, campaign_revenue,
               campaign_spend, campaign_date,
               source_id, bronze_run_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                   $11, $12, $13, $14, $15, $16, $17, $18)
           ON CONFLICT (enterprise_id, order_external_id) DO NOTHING""",
        records,
    )
    return len(records)


async def insert_silver_tickets(
    conn,
    *,
    enterprise_id: str, branch_id: str, dept_id: str, source_id: str,
    run_id: str, raw_rows: list[dict],
) -> int:
    """Project Bronze review rows → silver_tickets."""
    records = []
    for raw in raw_rows:
        proj = project_review_row(raw)
        if proj is None:
            continue
        records.append((
            enterprise_id, proj["ticket_external_id"],
            branch_id, dept_id,
            proj["customer_external_id"], proj["agent_user_id"],
            proj["csat_rating"], proj["nps_score"], proj["rated_at"],
            proj["created_at_source"], proj["first_response_at"],
            proj["resolved_at"], proj["escalated"],
            proj["category"], proj["priority"],
            source_id, run_id,
        ))
    if not records:
        return 0
    await conn.executemany(
        """INSERT INTO silver_tickets
              (enterprise_id, ticket_external_id,
               branch_id, department_id,
               customer_external_id, agent_user_id,
               csat_rating, nps_score, rated_at,
               created_at_source, first_response_at,
               resolved_at, escalated,
               category, priority,
               source_id, bronze_run_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                   $11, $12, $13, $14, $15, $16, $17)
           ON CONFLICT (enterprise_id, ticket_external_id) DO NOTHING""",
        records,
    )
    return len(records)


async def insert_silver_finance_periods(
    conn,
    *,
    enterprise_id: str, branch_id: str, dept_id: str, source_id: str,
    run_id: str, agg_rows: list[dict],
) -> int:
    """Insert pre-aggregated silver_finance_periods rows."""
    if not agg_rows:
        return 0
    records = [
        (enterprise_id, r["period"], branch_id, dept_id,
         r["revenue"], r["cogs"], r["operating_expense"], r["annual_revenue"],
         r["ar_balance"], r["cash_balance"], r["monthly_burn"],
         r["current_assets"], r["current_liabilities"],
         source_id, run_id)
        for r in agg_rows
    ]
    await conn.executemany(
        """INSERT INTO silver_finance_periods
              (enterprise_id, period, branch_id, department_id,
               revenue, cogs, operating_expense, annual_revenue,
               ar_balance, cash_balance, monthly_burn,
               current_assets, current_liabilities,
               source_id, bronze_run_id)
           VALUES ($1, $2::date, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
           ON CONFLICT (enterprise_id, department_id, period) DO NOTHING""",
        records,
    )
    return len(records)


# ─── Demo workflow cloning + step-document attachment ───────────────
#
# P15-S11 Tuần 8 — make the demo non-empty. After Bronze + Silver land,
# clone the "Lead Qualification Workflow" template into the Olist
# enterprise (Sales dept) and attach each Olist file to a reasonable
# step. The FE tree viewer then shows real files on first open.


async def clone_demo_workflow(
    conn,
    *,
    enterprise_id: str, sales_dept_id: str, branch_id: str,
) -> Optional[str]:
    """Clone the Lead Qualification template into Sales. Idempotent on name."""
    # Skip if a workflow named "Lead Qualification Workflow" already exists.
    existing = await conn.fetchval(
        """SELECT workflow_id::text FROM workflows
           WHERE enterprise_id = $1 AND department_id = $2 AND name = $3""",
        enterprise_id, sales_dept_id, "Lead Qualification Workflow",
    )
    if existing:
        return existing

    tpl = await conn.fetchrow(
        """SELECT template_id, display_name, display_name_vi, description,
                  category, workflow_definition
           FROM workflow_templates
           WHERE display_name = $1 AND is_active = TRUE
           LIMIT 1""",
        "Lead Qualification Workflow",
    )
    if tpl is None:
        return None

    wf_def = tpl["workflow_definition"]
    if isinstance(wf_def, str):
        wf_def = json.loads(wf_def)

    import uuid as _uuid
    wf_id = str(_uuid.uuid4())
    await conn.execute(
        """INSERT INTO workflows
              (workflow_id, enterprise_id, branch_id, department_id,
               name, name_vi, description, category, business_function,
               state, source, cloned_from_template_id)
           VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                   $5, $6, $7, $8, NULL,
                   'ACTIVE_BASELINE', 'template_based', $9::uuid)""",
        wf_id, enterprise_id, branch_id, sales_dept_id,
        tpl["display_name"], tpl["display_name_vi"], tpl["description"],
        tpl["category"], tpl["template_id"],
    )

    client_to_real: dict[str, str] = {}
    for raw_node in wf_def.get("nodes", []):
        node_id = str(_uuid.uuid4())
        client_to_real[raw_node["client_id"]] = node_id
        await conn.execute(
            """INSERT INTO workflow_nodes
                  (node_id, workflow_id, enterprise_id, department_id,
                   node_type, category, side_effect_class,
                   position_x, position_y,
                   title, title_vi, note, hashtags,
                   required_document_types, sequence_order)
               VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                       $5, $6, $7, $8, $9, $10, $11, $12, $13,
                       $14::jsonb, $15)""",
            node_id, wf_id, enterprise_id, sales_dept_id,
            raw_node.get("node_type", "step"),
            raw_node.get("category", "data_input"),
            raw_node.get("side_effect_class", "read_only"),
            raw_node.get("position_x", 0),
            raw_node.get("position_y", 0),
            raw_node["title"],
            raw_node.get("title_vi"),
            raw_node.get("note"),
            raw_node.get("hashtags", []),
            json.dumps(raw_node.get("required_document_types", []), ensure_ascii=False),
            raw_node.get("sequence_order", 0),
        )

    for raw_edge in wf_def.get("edges", []):
        src = client_to_real.get(raw_edge["source_client_id"])
        tgt = client_to_real.get(raw_edge["target_client_id"])
        if not src or not tgt:
            continue
        await conn.execute(
            """INSERT INTO workflow_edges
                  (workflow_id, enterprise_id, source_node_id, target_node_id, label)
               VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5)""",
            wf_id, enterprise_id, src, tgt, raw_edge.get("label"),
        )

    return wf_id


async def attach_file_to_workflow_step(
    conn,
    *,
    workflow_id: str, enterprise_id: str, dept_id: str,
    file_id: str, sequence_order: int, document_kind: str,
) -> None:
    """Attach a bronze_file to the workflow node at the given sequence_order."""
    node = await conn.fetchrow(
        """SELECT node_id::text FROM workflow_nodes
           WHERE workflow_id = $1 AND sequence_order = $2
           ORDER BY created_at ASC LIMIT 1""",
        workflow_id, sequence_order,
    )
    if node is None:
        return
    await conn.execute(
        """INSERT INTO workflow_step_documents
              (workflow_id, node_id, file_id, enterprise_id, department_id,
               document_kind, uploaded_at)
           VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6, NOW())
           ON CONFLICT (workflow_id, node_id, file_id) DO NOTHING""",
        workflow_id, node["node_id"], file_id, enterprise_id, dept_id, document_kind,
    )


async def insert_bronze_rows(
    conn,
    *,
    enterprise_id: str, branch_id: str, dept_id: str, source_id: str,
    file_id: str, rows: list[dict],
) -> int:
    """Bulk insert via executemany. Skips if rows already exist for the file."""
    existing = await conn.fetchval(
        "SELECT COUNT(*) FROM bronze_rows WHERE file_id = $1",
        file_id,
    )
    if existing and existing >= len(rows):
        return existing
    records = [
        (file_id, enterprise_id, branch_id, dept_id, source_id, idx,
         json.dumps(row, ensure_ascii=False))
        for idx, row in enumerate(rows)
    ]
    await conn.executemany(
        """INSERT INTO bronze_rows
              (file_id, enterprise_id, branch_id, department_id, source_id,
               row_index, raw_data)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
           ON CONFLICT DO NOTHING""",
        records,
    )
    return len(records)


# ─── Driver ──────────────────────────────────────────────────────────


async def seed(
    olist_dir: Path,
    *,
    dry_run: bool,
    sample_rows: int,
    database_url: Optional[str] = None,
) -> SeedSummary:
    summary = SeedSummary(dry_run=dry_run)

    if not dry_run:
        if asyncpg is None:
            raise RuntimeError("asyncpg not installed — required for --real mode")
        url = database_url or os.environ.get(
            "DATABASE_URL", "postgresql://kaori_user:kaori_pass@localhost:5432/kaori"
        )
        conn = await asyncpg.connect(url)
    else:
        conn = None

    try:
        if not dry_run:
            async with conn.transaction():
                # GUC set for both legacy and new RLS policies.
                summary.workspace_id = await get_or_create_workspace(conn)
                summary.enterprise_id = await get_or_create_enterprise(
                    conn, summary.workspace_id
                )
                await conn.execute(
                    "SELECT set_config('app.enterprise_id', $1, true)",
                    summary.enterprise_id,
                )
                await conn.execute(
                    "SELECT set_config('app.current_enterprise_id', $1, true)",
                    summary.enterprise_id,
                )
                summary.branch_id = await get_default_branch(conn, summary.enterprise_id)
        else:
            summary.workspace_id = "[dry-run-uuid-workspace]"
            summary.enterprise_id = "[dry-run-uuid-enterprise]"
            summary.branch_id = "[dry-run-uuid-branch]"

        # order_index built when we process the orders CSV; consumed when
        # we process the payments CSV (cross-CSV dependency for finance
        # period aggregation).
        order_index: dict[str, datetime] = {}
        # Map Olist domain → bronze file_id. Used at the end of the seed
        # to attach files to demo workflow steps.
        files_by_domain: dict[str, str] = {}

        for plan in OLIST_PLAN:
            csv_path = olist_dir / plan.filename
            if not csv_path.exists():
                print(f"  ⚠ {plan.filename}: file not found in {olist_dir}, skipping")
                continue
            print(f"→ {plan.filename} → dept={plan.dept_type} (domain={plan.domain})")

            sha = sha256_of_file(csv_path)
            size = csv_path.stat().st_size
            rows = list(iter_rows(csv_path, sample_rows))
            row_count = len(rows)

            # Build order_index as we see the orders CSV — used later by
            # the payments → silver_finance_periods aggregator.
            if plan.domain == "orders":
                for r in rows:
                    oid = (r.get("order_id") or "").strip()
                    ts = _parse_ts(r.get("order_purchase_timestamp"))
                    if oid and ts is not None:
                        order_index[oid] = ts

            if not dry_run:
                dept_id = await get_dept_id(conn, summary.enterprise_id, plan.dept_type)
                source_id = await get_default_source(conn, summary.enterprise_id, dept_id)
                async with conn.transaction():
                    await conn.execute(
                        "SELECT set_config('app.enterprise_id', $1, true)",
                        summary.enterprise_id,
                    )
                    await conn.execute(
                        "SELECT set_config('app.current_enterprise_id', $1, true)",
                        summary.enterprise_id,
                    )
                    run_id = await upsert_pipeline_run(
                        conn, summary.enterprise_id, plan.filename, sha
                    )
                    file_id = await insert_bronze_file(
                        conn,
                        enterprise_id=summary.enterprise_id,
                        branch_id=summary.branch_id,
                        dept_id=dept_id,
                        source_id=source_id,
                        run_id=run_id,
                        filename=plan.filename,
                        sha=sha,
                        row_count=row_count,
                    )
                    inserted = await insert_bronze_rows(
                        conn,
                        enterprise_id=summary.enterprise_id,
                        branch_id=summary.branch_id,
                        dept_id=dept_id,
                        source_id=source_id,
                        file_id=file_id,
                        rows=rows,
                    )
                    print(f"    file_id={file_id} bronze_rows≈{inserted}")
                    files_by_domain[plan.domain] = file_id

                    # ─── Bronze → Silver projection (Build Week only;
                    #     Phase 2 owns this in a separate ETL worker).
                    silver_inserted: Optional[int] = None
                    if plan.domain == "customers":
                        silver_inserted = await insert_silver_customers(
                            conn,
                            enterprise_id=summary.enterprise_id,
                            branch_id=summary.branch_id,
                            dept_id=dept_id,
                            source_id=source_id,
                            run_id=run_id,
                            raw_rows=rows,
                        )
                    elif plan.domain == "orders":
                        silver_inserted = await insert_silver_orders(
                            conn,
                            enterprise_id=summary.enterprise_id,
                            branch_id=summary.branch_id,
                            dept_id=dept_id,
                            source_id=source_id,
                            run_id=run_id,
                            raw_rows=rows,
                        )
                    elif plan.domain == "reviews":
                        silver_inserted = await insert_silver_tickets(
                            conn,
                            enterprise_id=summary.enterprise_id,
                            branch_id=summary.branch_id,
                            dept_id=dept_id,
                            source_id=source_id,
                            run_id=run_id,
                            raw_rows=rows,
                        )
                    elif plan.domain == "payments":
                        payment_rows = [
                            p for p in (project_payment_row(r) for r in rows)
                            if p is not None
                        ]
                        agg = aggregate_finance_periods(payment_rows, order_index)
                        silver_inserted = await insert_silver_finance_periods(
                            conn,
                            enterprise_id=summary.enterprise_id,
                            branch_id=summary.branch_id,
                            dept_id=dept_id,
                            source_id=source_id,
                            run_id=run_id,
                            agg_rows=agg,
                        )
                    if silver_inserted is not None:
                        print(f"    silver_rows={silver_inserted} ({plan.domain})")

            summary.add_file(plan.dept_type, row_count, size)

        # P15-S11 Tuần 8 — clone demo workflow + attach Olist files.
        # Phase 2 connector wiring will replace this co-located demo helper.
        if not dry_run:
            sales_dept_id = await get_dept_id(conn, summary.enterprise_id, "sales")
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.enterprise_id', $1, true)",
                    summary.enterprise_id,
                )
                await conn.execute(
                    "SELECT set_config('app.current_enterprise_id', $1, true)",
                    summary.enterprise_id,
                )
                wf_id = await clone_demo_workflow(
                    conn,
                    enterprise_id=summary.enterprise_id,
                    sales_dept_id=sales_dept_id,
                    branch_id=summary.branch_id,
                )
                if wf_id:
                    print(f"→ Demo workflow ready: {wf_id}")
                    # Attach Olist files to plausible workflow steps so the
                    # tree viewer demos non-empty on first load. Mapping:
                    #   customers → Card 1 (Lead intake)
                    #   orders    → Card 3 (SQL/MQL split — uses deal_status)
                    #   sellers   → Card 4 (Sales rep handoff)
                    attach_plan = [
                        ("customers", 1, "csv"),
                        ("orders",    3, "csv"),
                        ("sellers",   4, "csv"),
                    ]
                    for domain, seq, kind in attach_plan:
                        fid = files_by_domain.get(domain)
                        if fid is None:
                            continue
                        await attach_file_to_workflow_step(
                            conn,
                            workflow_id=wf_id,
                            enterprise_id=summary.enterprise_id,
                            dept_id=sales_dept_id,
                            file_id=fid,
                            sequence_order=seq,
                            document_kind=kind,
                        )
                        print(f"    attached {domain} → card seq={seq}")
    finally:
        if conn is not None:
            await conn.close()

    return summary


# ─── CLI ─────────────────────────────────────────────────────────────


def main() -> int:
    # PowerShell on Windows defaults to cp1252; reconfigure stdout so
    # arrow + box-drawing characters in our progress output don't crash.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except AttributeError:
        pass  # older Python or non-text stream

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--olist-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "kaggle" / "olist",
        help="Folder containing olist_*_dataset.csv files",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=1000,
        help="Cap rows per CSV. 0 = all rows. Default 1000 (~5MB bronze_rows total).",
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true", help="Print summary, no DB writes")
    grp.add_argument("--real", action="store_true", help="Insert into Postgres")
    parser.add_argument(
        "--database-url",
        help="Postgres URL. Default = DATABASE_URL env / localhost:5432/kaori",
    )
    args = parser.parse_args()

    if not args.olist_dir.exists():
        print(f"ERROR: --olist-dir not found: {args.olist_dir}", file=sys.stderr)
        return 2

    summary = asyncio.run(
        seed(
            args.olist_dir,
            dry_run=args.dry_run,
            sample_rows=args.sample_rows,
            database_url=args.database_url,
        )
    )
    summary.print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
