"""Shape test for migration 136 (ai_incident) — no DB."""
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations/136_ai_incident.sql"


def test_migration_136_exists():
    assert MIG.exists(), f"missing {MIG}"


def test_k21_id_strategy():
    sql = MIG.read_text(encoding="utf-8")
    assert "gen_uuid_v7()" in sql
    assert "gen_ulid()" in sql


def test_severity_and_status_constraints():
    sql = MIG.read_text(encoding="utf-8")
    for s in ("low", "medium", "high", "serious"):
        assert s in sql, f"severity {s} missing"
    assert "chk_incident_severity" in sql
    assert "chk_incident_status" in sql


def test_rls_enabled():
    sql = MIG.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "isolation_incident" in sql
    assert "app.current_enterprise_id" in sql


def test_grant_app_role():
    sql = MIG.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ai_incident TO kaori_app" in sql
