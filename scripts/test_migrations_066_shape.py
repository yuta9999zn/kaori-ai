"""Shape tests for migration 066 — DocSage cache tables.

066 = docsage_schemas + docsage_extractions for the 3-module structured-SQL
      RAG engine (P15-S11 D1 per docs/sprint/P15-S11_DOCSAGE_PLAN.md).

Pure-Python (no DB). Mirrors test_migrations_055_056_057_shape.py pattern.
Run from repo root:
    python -m pytest scripts/test_migrations_066_shape.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO    = Path(__file__).resolve().parent.parent
MIG_DIR = REPO / "infrastructure" / "postgres" / "migrations"
MIG_066_RAW = (MIG_DIR / "066_docsage_cache.sql").read_text(encoding="utf-8")


def _strip_sql_comments(sql: str) -> str:
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


MIG_066 = _strip_sql_comments(MIG_066_RAW)


# ─── Table existence ────────────────────────────────────────────────


def test_creates_docsage_schemas_table():
    assert re.search(
        r"CREATE TABLE IF NOT EXISTS docsage_schemas\s*\(",
        MIG_066,
    ), "docsage_schemas table missing"


def test_creates_docsage_extractions_table():
    assert re.search(
        r"CREATE TABLE IF NOT EXISTS docsage_extractions\s*\(",
        MIG_066,
    ), "docsage_extractions table missing"


# ─── Required columns ───────────────────────────────────────────────


SCHEMAS_REQUIRED_COLS = {
    "schema_id", "enterprise_id", "corpus_hash", "question_class",
    "schema_json", "llm_model", "llm_version", "token_count", "created_at",
}
EXTRACTIONS_REQUIRED_COLS = {
    "extraction_id", "enterprise_id", "schema_id", "doc_id",
    "rows_json", "extraction_status", "error_message", "token_count", "created_at",
}


def _table_body(sql: str, table_name: str) -> str:
    m = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table_name}\s*\((.*?)\)\s*;",
        sql, re.DOTALL,
    )
    assert m, f"{table_name} body not found"
    return m.group(1)


def test_docsage_schemas_required_columns():
    body = _table_body(MIG_066, "docsage_schemas")
    for col in SCHEMAS_REQUIRED_COLS:
        assert re.search(rf"\b{col}\b", body), f"docsage_schemas missing column {col!r}"


def test_docsage_extractions_required_columns():
    body = _table_body(MIG_066, "docsage_extractions")
    for col in EXTRACTIONS_REQUIRED_COLS:
        assert re.search(rf"\b{col}\b", body), f"docsage_extractions missing column {col!r}"


# ─── Constraints + indexes ──────────────────────────────────────────


def test_question_class_check_constraint():
    """Bounded vocab: comparison / aggregation / relationship / ranking."""
    assert re.search(
        r"chk_docsage_question_class\s+CHECK\s*\(question_class\s+IN",
        MIG_066,
    )
    for v in ("comparison", "aggregation", "relationship", "ranking"):
        assert f"'{v}'" in MIG_066, f"question_class enum missing {v!r}"


def test_extraction_status_check_constraint():
    assert re.search(
        r"chk_docsage_extract_status\s+CHECK\s*\(extraction_status\s+IN",
        MIG_066,
    )
    for v in ("ok", "partial", "failed"):
        assert f"'{v}'" in MIG_066, f"extraction_status enum missing {v!r}"


def test_schemas_unique_cache_key():
    """Same (enterprise, corpus, question_class) must round-trip to one row."""
    assert re.search(
        r"uq_docsage_schemas_cache.*?UNIQUE\s*\(enterprise_id,\s*corpus_hash,\s*question_class\)",
        MIG_066, re.DOTALL,
    )


def test_extractions_unique_cache_key():
    assert re.search(
        r"uq_docsage_extractions_cache.*?UNIQUE\s*\(enterprise_id,\s*schema_id,\s*doc_id\)",
        MIG_066, re.DOTALL,
    )


def test_lookup_indexes_present():
    assert "idx_docsage_schemas_lookup" in MIG_066
    assert "idx_docsage_extractions_lookup" in MIG_066


# ─── RLS (K-1) ──────────────────────────────────────────────────────


def test_rls_enabled_and_forced_on_both_tables():
    for tbl in ("docsage_schemas", "docsage_extractions"):
        assert re.search(rf"ALTER TABLE {tbl}\s+ENABLE ROW LEVEL SECURITY",
                         MIG_066), f"{tbl} missing ENABLE RLS"
        assert re.search(rf"ALTER TABLE {tbl}\s+FORCE ROW LEVEL SECURITY",
                         MIG_066), f"{tbl} missing FORCE RLS"


def test_tenant_isolation_policies_present():
    assert "tenant_docsage_schemas" in MIG_066
    assert "tenant_docsage_extractions" in MIG_066
    # Both should key off app.enterprise_id GUC (per Phase B-1 RLS pattern).
    assert MIG_066.count("current_setting('app.enterprise_id'") >= 2


def test_admin_bypass_policies_present():
    """SUPER_ADMIN bypass — sets app.is_admin = 'true' on the session."""
    assert "admin_bypass_docsage_schemas" in MIG_066
    assert "admin_bypass_docsage_extractions" in MIG_066


# ─── Grants ─────────────────────────────────────────────────────────


def test_kaori_app_grants():
    """SELECT + INSERT + DELETE for both tables; UPDATE explicitly NOT
    granted (cache is write-once + delete-on-evict)."""
    grants = [m for m in re.finditer(r"GRANT\s+([^O]+?)\s+ON\s+(\S+)\s+TO\s+kaori_app",
                                     MIG_066)]
    assert grants, "No kaori_app grants found"

    grant_tables = {g.group(2) for g in grants}
    assert "docsage_schemas" in grant_tables
    assert "docsage_extractions" in grant_tables

    for g in grants:
        privs = g.group(1).upper()
        assert "SELECT" in privs
        assert "INSERT" in privs
        assert "DELETE" in privs
        assert "UPDATE" not in privs, \
            f"UPDATE accidentally granted on {g.group(2)} — cache is write-once."


# ─── FK cascade ─────────────────────────────────────────────────────


def test_extractions_cascade_on_schema_delete():
    """When a schema row is evicted, its extractions go with it. Otherwise
    we leak orphan extraction rows under a deleted schema."""
    body = _table_body(MIG_066, "docsage_extractions")
    assert re.search(
        r"schema_id\s+UUID\s+NOT NULL\s+REFERENCES\s+docsage_schemas\(schema_id\)\s+ON DELETE CASCADE",
        body,
    )


def test_enterprise_cascade_on_both_tables():
    """When an enterprise is deleted, both caches purge."""
    for tbl in ("docsage_schemas", "docsage_extractions"):
        body = _table_body(MIG_066, tbl)
        assert re.search(
            r"enterprise_id\s+UUID\s+NOT NULL\s+REFERENCES\s+enterprises\(enterprise_id\)\s+ON DELETE CASCADE",
            body,
        ), f"{tbl} missing enterprise CASCADE"


# ─── K-20 invariants ────────────────────────────────────────────────


def test_k20_model_version_pinned_per_row():
    """K-20 — every cached LLM-derived row carries (llm_model, llm_version)
    so a cache hit on a stale model becomes a deliberate miss after upgrade."""
    body = _table_body(MIG_066, "docsage_schemas")
    assert re.search(r"llm_model\s+VARCHAR\(64\)\s+NOT NULL", body)
    assert re.search(r"llm_version\s+VARCHAR\(32\)\s+NOT NULL", body)
