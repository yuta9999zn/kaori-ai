"""Shape tests for migrations 055/056/057 — corporate hierarchy + Vingroup seed + cross-workflow links.

055 = corporate_groups + business_divisions tables, enterprises ALTER
      with corporate_group_id / business_division_id / parent_enterprise_id,
      v_corporate_tree recursive view, RLS K-1 via app.current_workspace_id.
056 = Vingroup demo seed (1 group + 8 divisions + 16 subsidiaries +
      branches/departments backfill per new enterprise).
057 = workflow_cross_links table + v_workflow_cross_links_enriched view.

Pure-Python (no DB). Pattern mirrors test_migrations_051_052_shape.py.
Run from repo root:
    python -m pytest scripts/test_migrations_055_056_057_shape.py
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO    = Path(__file__).resolve().parent.parent
MIG_DIR = REPO / "infrastructure" / "postgres" / "migrations"

MIG_055_RAW = (MIG_DIR / "055_corporate_hierarchy.sql").read_text(encoding="utf-8")
MIG_056_RAW = (MIG_DIR / "056_vingroup_demo_seed.sql").read_text(encoding="utf-8")
MIG_057_RAW = (MIG_DIR / "057_workflow_cross_links.sql").read_text(encoding="utf-8")


def _strip_sql_comments(sql: str) -> str:
    """Drop -- line comments and /* */ block comments."""
    out, in_block = [], False
    for line in sql.splitlines():
        if in_block:
            end = line.find("*/")
            if end == -1:
                continue
            line = line[end + 2:]
            in_block = False
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
        out.append(line.split("--", 1)[0])
    return "\n".join(out)


MIG_055 = _strip_sql_comments(MIG_055_RAW)
MIG_056 = _strip_sql_comments(MIG_056_RAW)
MIG_057 = _strip_sql_comments(MIG_057_RAW)


# ─── Mig 055 — corporate hierarchy schema ───────────────────────────


def test_mig_055_creates_corporate_groups_table():
    assert "CREATE TABLE IF NOT EXISTS corporate_groups" in MIG_055


def test_mig_055_creates_business_divisions_table():
    assert "CREATE TABLE IF NOT EXISTS business_divisions" in MIG_055


def test_mig_055_alters_enterprises_with_three_fks():
    """Three FKs added to enterprises: corporate_group_id +
    business_division_id + parent_enterprise_id (all NULLABLE)."""
    alter_block = MIG_055[MIG_055.index("ALTER TABLE enterprises"):
                          MIG_055.index("Cycle prevention", MIG_055.index("ALTER TABLE enterprises") + 10)
                          if "Cycle prevention" in MIG_055 else MIG_055.index("ALTER TABLE enterprises") + 2000]
    assert "corporate_group_id" in alter_block
    assert "business_division_id" in alter_block
    assert "parent_enterprise_id" in alter_block


def test_mig_055_creates_v_corporate_tree_view():
    """Non-recursive UNION ALL view that flattens the org tree.

    WITH RECURSIVE was originally planned but Postgres rejects multi-
    branch UNION ALL in a recursive CTE (recursive reference appears in
    non-recursive term after left-associative parse). Phase 1 view is
    plain UNION ALL of 4-5 anchor SELECTs covering levels 1-4."""
    assert "CREATE OR REPLACE VIEW v_corporate_tree" in MIG_055


def test_mig_055_view_emits_4_node_levels():
    """Group / division / enterprise(at div) / enterprise(direct) /
    sub-enterprise. The view's UNION ALL must cover ≥ 4 SELECT branches."""
    tree_view_block = MIG_055[MIG_055.index("CREATE OR REPLACE VIEW v_corporate_tree"):
                              MIG_055.index("COMMENT ON VIEW v_corporate_tree")]
    # 5 SELECT branches = 4 UNION ALL operators.
    assert tree_view_block.count("UNION ALL") >= 3


def test_mig_055_rls_uses_workspace_id_guc():
    """Per anh's directive: workspace-scoped RLS (NOT enterprise-scoped)
    because corporate_group spans many enterprises."""
    assert "app.current_workspace_id" in MIG_055
    assert "CREATE POLICY isolation_corporate_groups" in MIG_055
    assert "CREATE POLICY isolation_business_divisions" in MIG_055


def test_mig_055_corporate_group_unique_per_workspace():
    """Two corp_groups with same name in same workspace not allowed."""
    assert "uq_corp_group_name_per_workspace" in MIG_055
    assert "UNIQUE (workspace_id, name)" in MIG_055


def test_mig_055_division_unique_per_group():
    assert "uq_div_name_per_group" in MIG_055
    assert "UNIQUE (corporate_group_id, name)" in MIG_055


# ─── Mig 056 — Vingroup demo seed ────────────────────────────────────


def test_mig_056_creates_vingroup_workspace():
    """Workspace 'Vingroup Holdings' seeded (idempotent on name)."""
    assert "'Vingroup Holdings'" in MIG_056
    assert "NOT EXISTS" in MIG_056   # idempotent guard


def test_mig_056_creates_vingroup_corporate_group():
    assert "'Vingroup'" in MIG_056
    assert "'Tập đoàn Vingroup'" in MIG_056


def test_mig_056_seeds_8_business_divisions():
    """Per Corporate Profile 2018: 8 mảng (BĐS / Du lịch / Bán lẻ /
    Công nghiệp / Y tế / Giáo dục / Nông nghiệp / Công nghệ)."""
    for vi in (
        "Bất động sản", "Du lịch & Giải trí", "Bán lẻ",
        "Công nghiệp", "Y tế", "Giáo dục", "Nông nghiệp", "Công nghệ",
    ):
        assert f"'{vi}'" in MIG_056, f"Vingroup division missing: {vi}"


def test_mig_056_seeds_known_vingroup_brands():
    """Per 2018 profile §1.3 — these brands should all be present."""
    for brand in (
        "Vinhomes", "Vincom Retail",
        "Vinpearl",
        "VinMart",
        "VinFast", "VinSmart",
        "Vinmec",
        "VinSchool", "VinUni",
        "VinEco",
        "VinAI",
    ):
        assert f"'{brand}'" in MIG_056, f"Vingroup brand missing in seed: {brand}"


def test_mig_056_idempotent_via_not_exists():
    """Workspaces + enterprises lack UNIQUE on name; rely on NOT EXISTS."""
    # Should NOT use ON CONFLICT (name) for workspaces — that would fail.
    assert "ON CONFLICT (name) DO NOTHING" not in MIG_056_RAW


def test_mig_056_backfills_branches_and_departments():
    """Each new Vingroup enterprise must get default branch + 6 depts +
    Manual upload source, mirroring mig 046."""
    assert "INSERT INTO branches" in MIG_056
    assert "'Trụ sở chính'" in MIG_056
    assert "INSERT INTO departments" in MIG_056
    # 6 default dept_types
    for dt in ("marketing", "sales", "customer_service", "warehouse", "hr", "finance"):
        assert f"'{dt}'" in MIG_056


def test_mig_056_scopes_backfill_to_vingroup_only():
    """Don't accidentally re-seed Olist or other tenants."""
    assert "cg.name = 'Vingroup'" in MIG_056


# ─── Mig 057 — cross-workflow links ──────────────────────────────────


def test_mig_057_creates_workflow_cross_links_table():
    assert "CREATE TABLE IF NOT EXISTS workflow_cross_links" in MIG_057


def test_mig_057_self_loop_blocked():
    assert "source_workflow_id <> target_workflow_id" in MIG_057


def test_mig_057_link_type_enum():
    """4 link types per docx PART V Phần 2 + anh's directive."""
    for lt in ("triggers", "depends_on", "notifies", "data_handoff"):
        assert f"'{lt}'" in MIG_057


def test_mig_057_workspace_scoped_rls():
    """Cross-workflow links span enterprises — must be workspace-scoped,
    NOT enterprise-scoped, otherwise legitimate cross-subsidiary links
    would be invisible to one of the two sides."""
    assert "app.current_workspace_id" in MIG_057
    assert "CREATE POLICY isolation_workflow_cross_links" in MIG_057


def test_mig_057_creates_enriched_view():
    """v_workflow_cross_links_enriched joins workflows + enterprises +
    departments to render readable cross-org labels."""
    assert "CREATE OR REPLACE VIEW v_workflow_cross_links_enriched" in MIG_057


def test_mig_057_view_includes_cross_dimension_flags():
    """The view must surface crosses_enterprise / department / branch /
    division / corporate_group flags so the FE can render the right
    badges per anh's directive (phòng ban A của công ty Y có thể liên
    quan workflow phòng ban B của công ty khác)."""
    enriched_block = MIG_057[MIG_057.index("CREATE OR REPLACE VIEW v_workflow_cross_links_enriched"):
                             MIG_057.index("COMMENT ON VIEW v_workflow_cross_links_enriched")]
    for flag in (
        "crosses_enterprise",
        "crosses_department",
        "crosses_branch",
        "crosses_division",
        "crosses_corporate_group",
    ):
        assert flag in enriched_block, f"View missing flag: {flag}"


def test_mig_057_unique_active_link_per_pair():
    """No duplicate active link of the same type between two workflows."""
    assert "uq_cross_link_pair" in MIG_057
    assert "WHERE is_active = TRUE" in MIG_057


# ─── Anh's directive citations ──────────────────────────────────────


def test_mig_055_cites_anh_directive():
    assert "Vingroup-class" in MIG_055_RAW or "2026-05-15" in MIG_055_RAW


def test_mig_057_cites_anh_directive():
    """Per anh 'workflow phòng ban A có thể liên quan workflow phòng ban B'."""
    assert "phòng ban" in MIG_057_RAW.lower() or "anh" in MIG_057_RAW.lower()
