"""Shape tests for migration 067 — memory_l3 with pgvector.

Pure-Python. Mirrors test_migrations_066_shape.py.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO    = Path(__file__).resolve().parent.parent
MIG_DIR = REPO / "infrastructure" / "postgres" / "migrations"
MIG_067 = (MIG_DIR / "067_memory_l3_pgvector.sql").read_text(encoding="utf-8")


def _strip(sql: str) -> str:
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


M = _strip(MIG_067)


def test_creates_vector_extension():
    assert re.search(r"CREATE EXTENSION IF NOT EXISTS vector", M)


def test_creates_memory_l3_table():
    assert re.search(r"CREATE TABLE IF NOT EXISTS memory_l3\s*\(", M)


def test_embedding_column_vector_1024():
    assert re.search(r"embedding\s+VECTOR\(1024\)", M)


def test_required_columns():
    body_match = re.search(r"CREATE TABLE IF NOT EXISTS memory_l3\s*\((.*?)\);", M, re.DOTALL)
    assert body_match
    body = body_match.group(1)
    for col in ("record_id", "tenant_id", "memory_type", "content",
                 "embedding", "embedding_model", "session_id", "entity_id",
                 "occurred_at", "user_flagged_important",
                 "linked_outcome_value", "session_appearance_count",
                 "extra_metadata", "created_at", "updated_at"):
        assert re.search(rf"\b{col}\b", body), f"missing column {col}"


def test_memory_type_check_constraint():
    assert re.search(r"chk_memory_l3_type\s+CHECK\s*\(memory_type\s+IN", M)
    for v in ("EPISODIC", "SEMANTIC", "PROCEDURAL", "OPERATIONAL", "DECISION"):
        assert f"'{v}'" in M


def test_hnsw_cosine_index():
    assert re.search(
        r"CREATE INDEX IF NOT EXISTS idx_memory_l3_embedding_hnsw.*?USING hnsw\s*\(embedding\s+vector_cosine_ops\)",
        M, re.DOTALL,
    )


def test_rls_enabled_and_forced():
    assert re.search(r"ALTER TABLE memory_l3\s+ENABLE\s+ROW LEVEL SECURITY", M)
    assert re.search(r"ALTER TABLE memory_l3\s+FORCE\s+ROW LEVEL SECURITY", M)


def test_tenant_isolation_policy_present():
    assert "tenant_memory_l3" in M
    assert "current_setting('app.enterprise_id'" in M


def test_admin_bypass_policy_present():
    assert "admin_bypass_memory_l3" in M
    assert "app.is_admin" in M


def test_kaori_app_grants_include_update():
    """Unlike docsage_* tables, memory_l3 needs UPDATE so the bg
    embedding job can fill the vector column on existing rows."""
    grants = re.search(r"GRANT[^;]*ON memory_l3 TO kaori_app", M)
    assert grants
    privs = grants.group(0).upper()
    assert "SELECT" in privs
    assert "INSERT" in privs
    assert "UPDATE" in privs
    assert "DELETE" in privs


def test_session_and_entity_partial_indexes():
    assert re.search(
        r"idx_memory_l3_session.*?WHERE session_id IS NOT NULL",
        M, re.DOTALL,
    )
    assert re.search(
        r"idx_memory_l3_entity.*?WHERE entity_id IS NOT NULL",
        M, re.DOTALL,
    )


def test_enterprise_cascade():
    assert re.search(
        r"tenant_id\s+UUID\s+NOT NULL\s+REFERENCES\s+enterprises\(enterprise_id\)\s+ON DELETE CASCADE",
        M,
    )
