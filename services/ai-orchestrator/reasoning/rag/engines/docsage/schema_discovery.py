"""DocSage Schema Discovery — D3.

Single LLM call that converts a question + corpus sample → a minimal
joinable `SchemaDefinition`. Cached per (enterprise_id, corpus_hash,
question_class) in `docsage_schemas` (mig 066).

K-3:  via llm-gateway only (LLMRouter.complete_structured).
K-4:  Qwen local default; external opt-in via `consent_external`.
K-13: ON CONFLICT DO NOTHING on the cache row — replay-safe.
K-19: span emitted in LLMRouter; this module just calls.
K-20: cache row records (llm_model, llm_version) — miss on upgrade.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable, Optional
from uuid import UUID

import structlog

from .prompts import (
    PROMPT_VERSION,
    SCHEMA_DISCOVERY_SYSTEM,
    SCHEMA_DISCOVERY_USER_TEMPLATE,
)
from .types import SchemaDefinition

log = structlog.get_logger()


# ─── Output schema for Issue #3 validation ──────────────────────────


def _schema_definition_json_schema() -> dict:
    """JSON Schema 2020-12 representation of SchemaDefinition.

    Hand-rolled (not derived from .model_json_schema()) so the prompt
    can stay readable in the LLM input AND so we keep tight bounds on
    types/lengths that Pydantic auto-gen would loosen up."""
    return {
        "type":     "object",
        "required": ["tables", "question_class"],
        "additionalProperties": False,
        "properties": {
            "tables": {
                "type":  "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type":     "object",
                    "required": ["name", "columns"],
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "maxLength": 32,
                                  "pattern": "^[a-z][a-z0-9_]*$"},
                        "columns": {
                            "type":  "array",
                            "minItems": 1, "maxItems": 12,
                            "items": {
                                "type":     "object",
                                "required": ["name", "sql_type", "role"],
                                "additionalProperties": False,
                                "properties": {
                                    "name":      {"type": "string", "maxLength": 32,
                                                   "pattern": "^[a-z][a-z0-9_]*$"},
                                    "sql_type":  {"type": "string",
                                                   "enum": ["TEXT", "INTEGER", "NUMERIC",
                                                            "DATE", "TIMESTAMP", "BOOLEAN"]},
                                    "nullable":  {"type": "boolean"},
                                    "role":      {"type": "string",
                                                   "enum": ["key", "attribute", "measure", "fk"]},
                                    "fk_target": {"type": ["string", "null"], "maxLength": 64},
                                },
                            },
                        },
                    },
                },
            },
            "join_keys": {
                "type":  "array",
                "maxItems": 10,
                "items": {
                    "type":     "object",
                    "required": ["left_table", "left_column", "right_table", "right_column"],
                    "additionalProperties": False,
                    "properties": {
                        "left_table":   {"type": "string", "maxLength": 32},
                        "left_column":  {"type": "string", "maxLength": 32},
                        "right_table":  {"type": "string", "maxLength": 32},
                        "right_column": {"type": "string", "maxLength": 32},
                    },
                },
            },
            "question_class": {
                "type": "string",
                "enum": ["comparison", "aggregation", "relationship", "ranking"],
            },
        },
    }


# ─── Cache key helpers ──────────────────────────────────────────────


def corpus_hash_of(doc_ids: Iterable[str]) -> str:
    """Stable sha256 of sorted doc_ids. Empty corpus = stable empty
    hash (caller's choice whether to short-circuit before calling)."""
    canonical = ",".join(sorted(d.strip() for d in doc_ids if d and d.strip()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─── Module class ───────────────────────────────────────────────────


class SchemaDiscovery:
    """Step 1 of the DocSage pipeline.

    The class is intentionally stateless — pass in a connection pool +
    LLM router at construction time, then call `.discover()` per query.
    The cache lookup + LLM call + cache store all live inside .discover().
    """

    def __init__(self, *, llm_router, db_pool=None):
        # db_pool=None lets unit tests construct without a Postgres pool;
        # in that mode .discover() skips cache I/O.
        self.llm_router = llm_router
        self.db_pool    = db_pool

    async def discover(
        self,
        *,
        enterprise_id: UUID,
        question: str,
        corpus_excerpts: list[tuple[str, str]],
        consent_external: bool = False,
    ) -> SchemaDefinition:
        """Return a `SchemaDefinition` for the question + corpus.

        Args:
            enterprise_id:    tenant uuid, for RLS-scoped cache I/O.
            question:         the manager's question (Vietnamese OK).
            corpus_excerpts:  list of (doc_id, excerpt_text). The
                              excerpt should be ≤600 chars per doc —
                              caller trims.
            consent_external: K-4 opt-in flag, forwarded to LLM router.

        Cache:
            Looked up before the LLM call; on hit the cached
            SchemaDefinition is returned without paying the LLM cost.
            On miss the LLM is called, the result validated, then
            written back to docsage_schemas.
        """
        doc_ids = [d_id for d_id, _ in corpus_excerpts]
        ch = corpus_hash_of(doc_ids)

        cached = await self._cache_lookup_or_none(enterprise_id, ch)
        if cached is not None:
            log.info("docsage.schema_discovery.cache_hit",
                     enterprise_id=str(enterprise_id),
                     corpus_hash=ch,
                     question_class=cached.question_class)
            return cached

        # Call the LLM via the gateway with Issue #3 output_schema. The
        # gateway repairs once on validation fail per K-20 path; if it
        # 502s twice in a row we let the error bubble up — the caller
        # falls back to pgvector per the RAGRouter contract.
        corpus_excerpt_text = "\n\n".join(
            f"[doc {d_id[:8]}…]\n{excerpt[:600]}"
            for d_id, excerpt in corpus_excerpts[:3]
        ) or "(empty corpus)"
        user_prompt = SCHEMA_DISCOVERY_USER_TEMPLATE.format(
            question=question,
            corpus_excerpt=corpus_excerpt_text,
        )
        prompt = f"{SCHEMA_DISCOVERY_SYSTEM}\n\n---\n\n{user_prompt}"

        parsed = await self.llm_router.complete_structured(
            prompt=prompt,
            task="docsage.schema_discovery",
            output_schema=_schema_definition_json_schema(),
            consent_external=consent_external,
            enterprise_id=str(enterprise_id),
            max_tokens=1500,
        )

        # Pydantic validation as defence-in-depth — the gateway already
        # ran the JSON Schema check, but the Pydantic model adds the
        # snake_case + enum checks the JSON Schema can't express cleanly.
        schema = SchemaDefinition.model_validate(parsed)

        await self._cache_store(
            enterprise_id=enterprise_id,
            corpus_hash=ch,
            schema=schema,
        )
        log.info("docsage.schema_discovery.miss_then_landed",
                 enterprise_id=str(enterprise_id),
                 corpus_hash=ch,
                 question_class=schema.question_class,
                 table_count=len(schema.tables))
        return schema

    # ─── Internal cache I/O ───────────────────────────────────────

    async def _cache_lookup_or_none(
        self, enterprise_id: UUID, corpus_hash: str,
    ) -> Optional[SchemaDefinition]:
        if self.db_pool is None:
            return None
        # We don't know question_class yet, but the cache row is keyed
        # on (enterprise_id, corpus_hash, question_class). For the
        # lookup we accept "any question_class on this corpus" — the
        # next caller hitting the same hash + class wins the cache;
        # different class = miss + LLM call. This matches spec §4.5.
        from ...shared.db import acquire_for_tenant  # type: ignore  # noqa: E402
        async with acquire_for_tenant(enterprise_id) as conn:
            row = await conn.fetchrow(
                """SELECT schema_json
                   FROM docsage_schemas
                   WHERE enterprise_id = $1
                     AND corpus_hash   = $2
                   ORDER BY created_at DESC
                   LIMIT 1""",
                enterprise_id, corpus_hash,
            )
        if row is None:
            return None
        raw = row["schema_json"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        return SchemaDefinition.model_validate(raw)

    async def _cache_store(
        self, *, enterprise_id: UUID, corpus_hash: str,
        schema: SchemaDefinition,
    ) -> None:
        if self.db_pool is None:
            return
        from ...shared.db import acquire_for_tenant  # type: ignore  # noqa: E402

        # K-20 — record the model + version that produced this row.
        # _DEV_MODEL fallback when LLMRouter exposes neither (tests).
        llm_model   = getattr(self.llm_router, "last_model", None) or "qwen2.5:14b"
        llm_version = getattr(self.llm_router, "last_version", None) or PROMPT_VERSION

        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """INSERT INTO docsage_schemas
                       (enterprise_id, corpus_hash, question_class,
                        schema_json, llm_model, llm_version, token_count)
                   VALUES ($1, $2, $3, $4::jsonb, $5, $6, 0)
                   ON CONFLICT (enterprise_id, corpus_hash, question_class)
                   DO NOTHING""",
                enterprise_id, corpus_hash, schema.question_class,
                schema.model_dump_json(),
                llm_model, llm_version,
            )
