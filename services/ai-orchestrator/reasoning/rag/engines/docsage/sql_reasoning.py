"""DocSage SQL Reasoning — D5 step 3.

Compose SQL from (SchemaDefinition, rows_by_doc, question) → execute
against ephemeral Postgres TEMP TABLES → format result into a
Vietnamese answer with citations.

Why TEMP TABLES (per plan §3 D5):
  * Session-private; auto-dropped at txn commit — no schema drift.
  * EXPLAIN ANALYZE-friendly for ops.
  * Cannot leak to other tenants — temp namespace is per-session.

Defence-in-depth on the LLM-emitted SQL:
  * Whitelist parser: only SELECT, only references to declared TEMP
    table names, no DDL / DML keywords beyond SELECT.
  * Connection runs WITHOUT the app.enterprise_id GUC so even if the
    LLM tried to reach a non-temp tenant table, RLS would deny.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import structlog

from .prompts import (
    SQL_COMPOSER_SYSTEM,
    SQL_FORMATTER_SYSTEM,
)
from .types import Citation, Row, SchemaDefinition

log = structlog.get_logger()


# ─── Result shape ───────────────────────────────────────────────────


@dataclass(frozen=True)
class SQLAnswer:
    text:        str
    sql_query:   str
    rowset:      list[dict]
    citations:   list[Citation]
    table_names: list[str] = field(default_factory=list)
    error:       Optional[str] = None


# ─── SQL whitelist parser ───────────────────────────────────────────


_DML_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|MERGE|CALL|COPY)\b",
    re.IGNORECASE,
)
_COMMENT_RE  = re.compile(r"(--.*?$)|(/\*.*?\*/)", re.MULTILINE | re.DOTALL)
_TABLE_REF   = re.compile(r"\b(FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


def is_sql_safe(sql: str, *, allowed_tables: set[str]) -> tuple[bool, Optional[str]]:
    """Reject any SQL that's not a plain SELECT against the whitelist.

    Returns (ok, reason). On reject the caller surfaces 'sql rejected'
    to the FE — DocSageEngine falls back gracefully.

    Rules:
      1. SQL must start with SELECT (after stripping leading whitespace).
      2. No DML keywords anywhere (INSERT, UPDATE, DELETE, DROP, etc).
      3. No SQL comments (-- or /* */).
      4. Every FROM / JOIN reference must hit `allowed_tables`.
      5. No semicolons except the optional trailing one (no multi-statement).
    """
    if not sql or not sql.strip():
        return False, "empty sql"

    stripped = sql.strip().rstrip(";").strip()
    if not stripped.upper().startswith("SELECT"):
        return False, "not a SELECT"

    if _COMMENT_RE.search(stripped):
        return False, "comments not allowed"

    if _DML_KEYWORDS.search(stripped):
        return False, "DML/DDL keyword found"

    # No multi-statement (one trailing semicolon is fine, multiple isn't).
    if stripped.count(";") > 0:
        return False, "multi-statement not allowed"

    refs = {m.group(2).lower() for m in _TABLE_REF.finditer(stripped)}
    bad = refs - {t.lower() for t in allowed_tables}
    if bad:
        return False, f"references table(s) outside schema: {sorted(bad)}"

    return True, None


# ─── JSON Schema for the SQL composer LLM output ────────────────────


def _sql_composer_output_schema() -> dict:
    return {
        "type":     "object",
        "required": ["sql", "explanation_vi"],
        "additionalProperties": False,
        "properties": {
            "sql":            {"type": "string", "minLength": 8, "maxLength": 4000},
            "explanation_vi": {"type": "string", "maxLength": 500},
        },
    }


# ─── DDL helpers ────────────────────────────────────────────────────


def build_temp_table_ddl(schema: SchemaDefinition) -> list[str]:
    """Produce CREATE TEMPORARY TABLE statements for every table in
    `schema`. SQL identifiers are validated by the Pydantic model so
    this is safe to interpolate."""
    out = []
    for tbl in schema.tables:
        cols_sql = []
        for c in tbl.columns:
            nullable = "" if c.nullable else " NOT NULL"
            cols_sql.append(f"{c.name} {c.sql_type}{nullable}")
        ddl = f"CREATE TEMPORARY TABLE {tbl.name} ({', '.join(cols_sql)})"
        out.append(ddl)
    return out


def build_insert_statements(
    schema: SchemaDefinition, rows: list[Row],
) -> list[tuple[str, list]]:
    """Returns (sql, values_list) tuples for asyncpg.execute_many style
    inserts. Values flow through asyncpg's parameter binding — no
    interpolation, no injection."""
    cols_by_table = {t.name: [c.name for c in t.columns] for t in schema.tables}
    grouped: dict[str, list[Row]] = {}
    for r in rows:
        grouped.setdefault(r.table, []).append(r)

    out = []
    for tbl, tbl_rows in grouped.items():
        if tbl not in cols_by_table:
            continue
        cols = cols_by_table[tbl]
        placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
        sql = f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({placeholders})"
        for r in tbl_rows:
            values = [r.values.get(c) for c in cols]
            out.append((sql, values))
    return out


# ─── Module class ───────────────────────────────────────────────────


class SQLReasoning:
    """Step 3. Composes + executes SQL; formats result in Vietnamese.

    Caller provides:
      * llm_router — for SQL composer + result formatter LLM calls
      * sql_executor — an async callable (sql, params) → list[dict]
        that runs the CREATE TEMP TABLE + INSERT + SELECT against a
        new asyncpg connection. The default executor wires this; tests
        pass a mock.
    """

    def __init__(
        self, *,
        llm_router,
        sql_executor=None,    # async callable: (ddls, inserts, query) -> list[dict]
    ):
        self.llm_router   = llm_router
        self.sql_executor = sql_executor

    async def query(
        self,
        *,
        enterprise_id: UUID,
        schema:        SchemaDefinition,
        rows_by_doc:   dict[str, list[Row]],
        question:      str,
        consent_external: bool = False,
    ) -> SQLAnswer:
        # Flatten rows.
        flat_rows: list[Row] = []
        for doc_rows in rows_by_doc.values():
            flat_rows.extend(doc_rows)

        if not flat_rows:
            return SQLAnswer(
                text="Không có dữ liệu để trả lời câu hỏi.",
                sql_query="", rowset=[], citations=[],
                error="empty rowset (extraction produced 0 rows across the corpus)",
            )

        allowed_tables = {t.name for t in schema.tables}

        # Step 1 — LLM composes the SQL.
        composer_prompt = (
            f"{SQL_COMPOSER_SYSTEM}\n\n---\n\n"
            f"Schema:\n{schema.model_dump_json()}\n\n"
            f"Câu hỏi: {question}\n\n"
            "Trả JSON { sql, explanation_vi }."
        )
        composer_out = await self.llm_router.complete_structured(
            prompt=composer_prompt,
            task="docsage.sql_compose",
            output_schema=_sql_composer_output_schema(),
            consent_external=consent_external,
            enterprise_id=str(enterprise_id),
            max_tokens=800,
        )
        sql = (composer_out.get("sql") or "").strip().rstrip(";").strip()

        ok, reason = is_sql_safe(sql, allowed_tables=allowed_tables)
        if not ok:
            log.warning("docsage.sql_reasoning.rejected",
                        sql=sql[:200], reason=reason)
            return SQLAnswer(
                text=(
                    "Không thể tạo SQL an toàn cho câu hỏi này. "
                    "Vui lòng hỏi lại với phạm vi cụ thể hơn."
                ),
                sql_query=sql,
                rowset=[],
                citations=[],
                error=f"SQL rejected: {reason}",
                table_names=sorted(allowed_tables),
            )

        # Step 2 — execute against TEMP tables.
        ddls    = build_temp_table_ddl(schema)
        inserts = build_insert_statements(schema, flat_rows)

        if self.sql_executor is None:
            return SQLAnswer(
                text="(no executor wired — provide sql_executor at construction.)",
                sql_query=sql, rowset=[], citations=[],
                error="no executor",
                table_names=sorted(allowed_tables),
            )

        try:
            rowset = await self.sql_executor(ddls, inserts, sql)
        except Exception as e:
            log.warning("docsage.sql_reasoning.execute_failed",
                        sql=sql[:200], error=str(e))
            return SQLAnswer(
                text="Không chạy được truy vấn — vui lòng thử lại.",
                sql_query=sql, rowset=[], citations=[],
                error=f"execution error: {type(e).__name__}: {e}",
                table_names=sorted(allowed_tables),
            )

        # Step 3 — LLM formats the rowset as Vietnamese prose.
        formatter_prompt = (
            f"{SQL_FORMATTER_SYSTEM}\n\n---\n\n"
            f"Câu hỏi: {question}\n\n"
            f"Kết quả truy vấn (rowset):\n{rowset}\n\n"
            "Trả lời 1-3 câu tiếng Việt, có inline citation."
        )
        text = await self.llm_router.complete(
            prompt=formatter_prompt,
            task="docsage.sql_format",
            consent_external=consent_external,
            enterprise_id=str(enterprise_id),
            max_tokens=400,
        )

        # Build citations from rows' source_segments.
        citations: list[Citation] = []
        for doc_id, doc_rows in rows_by_doc.items():
            for r in doc_rows:
                if r.source_segment:
                    citations.append(Citation(
                        engine="docsage", doc_id=doc_id,
                        source_segment=r.source_segment,
                        sql_query=sql,
                        table_names=sorted(allowed_tables),
                    ))

        return SQLAnswer(
            text=text.strip(),
            sql_query=sql,
            rowset=rowset,
            citations=citations,
            table_names=sorted(allowed_tables),
        )
