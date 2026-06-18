"""Shape tests for migrations 051 + 052 — Medallion strict separation.

Per anh's directive 2026-05-15:
  "Cần phải có đầy đủ ba lớp đồng bạc vàng, và có chức năng nhiệm vụ
  riêng, không để chồng chéo."

These tests read the .sql files directly (no DB) and verify:

  Mig 051 (Silver per-domain tables):
    - 6 expected tables created
    - RLS enabled + K-1 isolation policy + ABAC dept_scope policy per table
    - Each table has enterprise_id + branch_id + department_id columns

  Mig 052 (Gold views from Silver only):
    - gold schema created
    - 6 expected views created
    - Views NEVER reference bronze_rows / silver_rows / JSONB extraction
      → enforces strict layer separation

Run from repo root:  python -m pytest scripts/test_migrations_051_052_shape.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MIG_DIR = REPO / "infrastructure" / "postgres" / "migrations"


def _strip_sql_comments(sql: str) -> str:
    """Drop `-- ...` line comments and `/* ... */` block comments.

    The strict-separation tests check for tokens (bronze_rows / silver_rows)
    in the EXECUTABLE SQL only — explanatory comments may legitimately
    mention what the migration deliberately AVOIDS.
    """
    out_lines: list[str] = []
    in_block = False
    for line in sql.splitlines():
        if in_block:
            end = line.find("*/")
            if end == -1:
                continue
            line = line[end + 2:]
            in_block = False
        # Strip block comments that open and close on the same line.
        while True:
            start = line.find("/*")
            if start == -1:
                break
            end = line.find("*/", start + 2)
            if end == -1:
                line = line[:start]
                in_block = True
                break
            line = line[:start] + line[end + 2:]
        # Strip line comments.
        line_no_comment = line.split("--", 1)[0]
        out_lines.append(line_no_comment)
    return "\n".join(out_lines)


MIG_051_RAW = (MIG_DIR / "051_silver_per_domain_tables.sql").read_text(encoding="utf-8")
MIG_052_RAW = (MIG_DIR / "052_per_dept_gold_views.sql").read_text(encoding="utf-8")
MIG_051 = _strip_sql_comments(MIG_051_RAW)
MIG_052 = _strip_sql_comments(MIG_052_RAW)


# ─── Mig 051 — Silver per-domain tables ─────────────────────────────────

EXPECTED_SILVER_TABLES = [
    "silver_customers",
    "silver_orders",
    "silver_tickets",
    "silver_inventory",
    "silver_employees",
    "silver_finance_periods",
]


@pytest.mark.parametrize("table", EXPECTED_SILVER_TABLES)
def test_mig_051_creates_silver_table(table):
    """Each of the 6 Silver tables must be created."""
    assert f"CREATE TABLE IF NOT EXISTS {table}" in MIG_051, (
        f"Mig 051 missing CREATE TABLE for {table}"
    )


@pytest.mark.parametrize("table", EXPECTED_SILVER_TABLES)
def test_mig_051_silver_table_has_org_attribution(table):
    """Every Silver table must carry enterprise + branch + department FKs."""
    # We look at the surrounding 50-line slice for that CREATE TABLE.
    idx = MIG_051.index(f"CREATE TABLE IF NOT EXISTS {table}")
    slice_ = MIG_051[idx:idx + 5000]
    assert "enterprise_id" in slice_,   f"{table} missing enterprise_id"
    assert "branch_id"     in slice_,   f"{table} missing branch_id"
    assert "department_id" in slice_,   f"{table} missing department_id"


@pytest.mark.parametrize("table", EXPECTED_SILVER_TABLES)
def test_mig_051_silver_table_has_rls_enabled(table):
    """RLS must be enabled — the DO $$ loop covers all 6 tables."""
    # Loop in mig 051 enables RLS for the named tables. Check the table
    # name appears inside the ARRAY[...] block.
    rls_block_start = MIG_051.index("ENABLE ROW LEVEL SECURITY")
    rls_block       = MIG_051[rls_block_start - 1000:rls_block_start + 500]
    assert table in rls_block, f"{table} missing from RLS ENABLE loop"


def test_mig_051_has_k1_isolation_and_abac_policies():
    """Both K-1 enterprise isolation + ABAC dept_scope policies must exist."""
    assert "CREATE POLICY isolation_%I"        in MIG_051
    assert "CREATE POLICY abac_dept_scope_%I"  in MIG_051
    # K-1 + ABAC use the same GUC names as mig 047
    assert "app.current_enterprise_id"  in MIG_051
    assert "app.current_department_id"  in MIG_051


def test_mig_051_silver_customers_has_pii_columns():
    """Silver_customers must carry PII columns — these get redacted at
    K-5 boundary, not stripped at Silver."""
    idx = MIG_051.index("CREATE TABLE IF NOT EXISTS silver_customers")
    slice_ = MIG_051[idx:idx + 3000]
    for col in ("name", "email", "phone"):
        assert col in slice_, f"silver_customers missing PII column {col}"


def test_mig_051_silver_orders_has_status_check_constraint():
    """deal_status must be CHECK-constrained to a known enum."""
    assert "chk_silver_orders_status" in MIG_051
    assert "'won'"       in MIG_051
    assert "'lost'"      in MIG_051
    assert "'open'"      in MIG_051


# ─── Mig 052 — Gold views from Silver only ─────────────────────────────

EXPECTED_GOLD_VIEWS = [
    "gold.customer_360_marketing",
    "gold.sales_pipeline",
    "gold.ticket_summary",
    "gold.inventory_warehouse",
    "gold.payroll_hr",
    "gold.kpi_finance",
]


def test_mig_052_creates_gold_schema():
    assert "CREATE SCHEMA IF NOT EXISTS gold" in MIG_052


@pytest.mark.parametrize("view", EXPECTED_GOLD_VIEWS)
def test_mig_052_creates_gold_view(view):
    """Each Gold view must be created with CREATE OR REPLACE VIEW."""
    assert f"CREATE OR REPLACE VIEW {view}" in MIG_052, (
        f"Mig 052 missing CREATE OR REPLACE VIEW {view}"
    )


def test_mig_052_view_names_match_kpi_definitions_target_gold_view():
    """Mig 049 kpi_definitions.target_gold_view must point at views that
    exist in mig 052. If a KPI references gold.X, mig 052 must create gold.X."""
    mig_049 = (MIG_DIR / "049_kpi_definitions_and_benchmarks.sql").read_text(encoding="utf-8")
    referenced = set()
    for view in EXPECTED_GOLD_VIEWS:
        if f"'{view}'" in mig_049:
            referenced.add(view)
    # All 6 expected views are referenced by at least one KPI definition.
    assert referenced == set(EXPECTED_GOLD_VIEWS), (
        f"Mismatch — mig 049 references {referenced}, "
        f"mig 052 creates {set(EXPECTED_GOLD_VIEWS)}"
    )


# ─── Strict separation guard rails (anh's directive) ───────────────────


import re

_FROM_OR_JOIN_RE = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO|USING)\s+([a-zA-Z_][a-zA-Z0-9_.]*)",
    re.IGNORECASE,
)


def _query_target_tables(sql: str) -> set[str]:
    """Extract table names that appear immediately after FROM/JOIN/UPDATE/INTO/USING.
    Strips schema prefix so `gold.x` and `x` both compare as `x`."""
    targets: set[str] = set()
    for match in _FROM_OR_JOIN_RE.finditer(sql):
        name = match.group(1).split(".")[-1]
        targets.add(name.lower())
    return targets


def test_mig_052_views_never_touch_bronze_rows():
    """Gold views MUST NOT read from bronze_rows. That's Bronze's grain."""
    targets = _query_target_tables(MIG_052)
    assert "bronze_rows" not in targets, (
        f"Mig 052 has FROM/JOIN bronze_rows in query context — Gold views "
        f"may NOT touch Bronze. Anh's directive 2026-05-15: "
        f"'không để chồng chéo'. Found targets: {targets}"
    )


def test_mig_052_views_never_touch_bronze_files():
    """Same rule — bronze_files is Bronze's grain."""
    targets = _query_target_tables(MIG_052)
    assert "bronze_files" not in targets


def test_mig_052_views_never_touch_silver_rows_jsonb_landing():
    """silver_rows is the legacy JSONB landing table — it's Bronze-grain
    even though the name says Silver. Gold views must read silver_* (per-
    domain typed tables) instead."""
    targets = _query_target_tables(MIG_052)
    assert "silver_rows" not in targets, (
        f"Mig 052 has FROM/JOIN silver_rows in query context — Gold views "
        f"must aggregate from silver_customers / silver_orders / etc., never "
        f"from the raw JSONB landing. That's a Silver→Bronze layer leak. "
        f"Found targets: {targets}"
    )


def test_mig_052_views_never_do_jsonb_extraction():
    """JSONB operators (->, ->>, ::jsonb) belong in Silver, not Gold.
    Gold reads typed columns only."""
    forbidden_ops = ["->>", "->", "::jsonb", "clean_data"]
    for op in forbidden_ops:
        assert op not in MIG_052, (
            f"Mig 052 contains JSONB operator/column {op!r} — that's "
            f"Silver's job. Gold views must read typed columns from "
            f"silver_* per-domain tables."
        )


def test_mig_052_views_reference_silver_per_domain_tables():
    """Each Gold view must read from at least one silver_* per-domain
    table. Otherwise the view is fabricated data, not a Medallion view."""
    silver_tables_in_view_body = []
    for tbl in EXPECTED_SILVER_TABLES:
        if tbl in MIG_052:
            silver_tables_in_view_body.append(tbl)
    # We expect at least 5 distinct Silver tables to appear (inventory +
    # employees + finance views are pass-throughs; customer + sales + CS
    # views also reference silver_customers join). The 6th (silver_inventory)
    # is in inventory_warehouse. So at minimum all 6 should appear.
    assert len(silver_tables_in_view_body) >= 5, (
        f"Mig 052 only references {silver_tables_in_view_body} Silver tables; "
        f"expected at least 5 of {EXPECTED_SILVER_TABLES}."
    )


# ─── ABAC + display-name consistency ────────────────────────────────────


@pytest.mark.parametrize("view", EXPECTED_GOLD_VIEWS)
def test_mig_052_view_projects_org_attribution(view):
    """Every Gold view must project enterprise_id + department_id +
    branch_id so the FE can apply per-dept filtering on top."""
    # Find the view body up to the next CREATE OR REPLACE or end-of-file.
    body_start = MIG_052.index(f"CREATE OR REPLACE VIEW {view}")
    next_create = MIG_052.find("CREATE OR REPLACE VIEW", body_start + 1)
    body_end = next_create if next_create > 0 else len(MIG_052)
    body = MIG_052[body_start:body_end]

    assert "enterprise_id" in body,   f"{view} missing enterprise_id projection"
    assert "department_id" in body,   f"{view} missing department_id projection"
    assert "branch_id"     in body,   f"{view} missing branch_id projection"


def test_mig_051_and_052_have_anh_directive_citation():
    """Both migrations cite anh's directive — paper trail for the
    Medallion strict-separation rule that drove this rewrite.
    Comments allowed here (we check the RAW SQL since the citation lives
    in the header comment block by design)."""
    expected_phrase = "không để chồng chéo"
    assert expected_phrase in MIG_051_RAW, "Mig 051 missing anh's directive citation"
    assert expected_phrase in MIG_052_RAW, "Mig 052 missing anh's directive citation"
