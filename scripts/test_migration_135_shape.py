"""Shape test for migration 135 (workflow_approvals.gate_kind) — no DB."""
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql"


def test_migration_135_exists():
    assert MIG.exists(), f"missing {MIG}"


def test_adds_gate_kind_column_additively():
    sql = MIG.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS gate_kind" in sql
    assert "DEFAULT 'approval_gate'" in sql


def test_check_constraint_both_kinds():
    sql = MIG.read_text(encoding="utf-8")
    assert "chk_wfappr_gate_kind" in sql
    assert "eu_ai_act_oversight" in sql
    assert "approval_gate" in sql
