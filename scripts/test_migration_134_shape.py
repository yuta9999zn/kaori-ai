"""Shape test for migration 134 (ai_use_risk_register) — no DB needed."""
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations/134_ai_use_risk_register.sql"


def test_migration_134_exists():
    assert MIG.exists(), f"missing {MIG}"


def test_k21_id_strategy():
    sql = MIG.read_text(encoding="utf-8")
    assert "gen_uuid_v7()" in sql, "K-21: PK must default gen_uuid_v7()"
    assert "gen_ulid()" in sql, "K-21: external public_ref must default gen_ulid()"


def test_rls_enabled():
    sql = MIG.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "isolation_airisk" in sql
    assert "app.current_enterprise_id" in sql


def test_tier_and_status_constraints():
    sql = MIG.read_text(encoding="utf-8")
    for tier in ("prohibited", "high", "limited", "minimal"):
        assert tier in sql, f"tier {tier} must be in CHECK constraint"
    assert "chk_airisk_status" in sql


def test_grant_app_role():
    sql = MIG.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ai_use_risk_register TO kaori_app" in sql
