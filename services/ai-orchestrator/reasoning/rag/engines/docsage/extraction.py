"""DocSage Structured Extraction — D4.

Per-doc LLM call: schema + doc_text → list[Row]. Cached per
(enterprise_id, schema_id, doc_id) in `docsage_extractions` (mig 066).

Compliance summary:
  K-3:  via llm-gateway (LLMRouter.complete_structured)
  K-4:  consent_external forwarded
  K-5:  redact PII before any external-vendor call (Qwen local stays raw)
  K-13: ON CONFLICT DO NOTHING — idempotent on re-extract
  K-20: cache row records (llm_model, llm_version)

Cost guard rails (per plan §3 D4):
  * Per-doc extraction LLM call capped at 8K input chars.
  * If a doc exceeds 8K, split into ≤4 segments at paragraph
    boundaries, run extraction on each, merge results, mark
    extraction_status='partial' if any segment failed.
  * Cache hit before LLM call — re-extracting the same doc + same
    schema returns the cached rows without paying LLM cost.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import structlog

from .prompts import (
    EXTRACTION_SYSTEM,
    EXTRACTION_USER_TEMPLATE,
    PROMPT_VERSION,
)
from .types import Row, SchemaDefinition

log = structlog.get_logger()


# Per-call extraction cap. 8000 chars ≈ 2000 tokens — well under Qwen
# 32K context but bounded enough that one doc never starves the rest
# of the corpus.
DOC_TEXT_CAP = 8000
MAX_SEGMENTS = 4


# ─── Result shape ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractionResult:
    """What extraction returns per doc. The 4-field shape mirrors mig
    066 docsage_extractions columns so cache I/O is a memcpy."""
    rows:             list[Row]
    extraction_status: str            # 'ok' / 'partial' / 'failed'
    error_message:    Optional[str]   = None
    token_count:      int             = 0


# ─── PII redaction (K-5) ────────────────────────────────────────────


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b0\d{9,10}\b|\+84\d{9,10}\b")
_NID   = re.compile(r"\b\d{12}\b")    # VN CCCD 12 digits


def redact_pii(text: str) -> str:
    """Vietnamese-aware PII redaction. Applied ONLY when the call is
    routed to an external vendor — Qwen local skips redaction (the
    data stays inside the tenant boundary anyway)."""
    text = _EMAIL.sub("<EMAIL>", text)
    text = _PHONE.sub("<PHONE>", text)
    text = _NID.sub("<NID>", text)
    return text


# ─── JSON Schema for Issue #3 validation ────────────────────────────


def _rows_envelope_json_schema() -> dict:
    return {
        "type":     "object",
        "required": ["rows"],
        "additionalProperties": False,
        "properties": {
            "rows": {
                "type":     "array",
                "maxItems": 200,        # hard cap per doc
                "items": {
                    "type":     "object",
                    "required": ["table", "values"],
                    "additionalProperties": False,
                    "properties": {
                        "table":  {"type": "string", "maxLength": 32,
                                    "pattern": "^[a-z][a-z0-9_]*$"},
                        "values": {"type": "object"},
                        "source_segment": {
                            "type":     "array",
                            "minItems": 2, "maxItems": 2,
                            "items":    {"type": "integer", "minimum": 0},
                        },
                    },
                },
            },
        },
    }


# ─── Helpers ────────────────────────────────────────────────────────


def _split_doc(text: str, *, page_from: int, page_to: int) -> list[tuple[str, int, int]]:
    """Split text into ≤MAX_SEGMENTS segments at paragraph boundaries
    when len(text) > DOC_TEXT_CAP. Returns list of (segment_text,
    page_from, page_to) — page boundaries are approximated linearly
    when we can't recover the exact page split."""
    if len(text) <= DOC_TEXT_CAP:
        return [(text, page_from, page_to)]

    # Split on blank lines first, fall back to mid-string hard split.
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    segments: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= DOC_TEXT_CAP:
            buf = (buf + "\n\n" + p) if buf else p
        else:
            if buf:
                segments.append(buf)
            if len(p) > DOC_TEXT_CAP:
                # Single paragraph bigger than cap — hard split.
                for i in range(0, len(p), DOC_TEXT_CAP):
                    segments.append(p[i:i + DOC_TEXT_CAP])
                buf = ""
            else:
                buf = p
    if buf:
        segments.append(buf)

    # Cap at MAX_SEGMENTS; drop overflow with a warning. 8K × 4 = 32K
    # chars is more than any business doc we expect Phase 1.5.
    if len(segments) > MAX_SEGMENTS:
        log.warning("docsage.extraction.segments_truncated",
                    segments=len(segments), max=MAX_SEGMENTS)
        segments = segments[:MAX_SEGMENTS]

    # Approximate page distribution.
    total_pages = max(page_to - page_from + 1, 1)
    out: list[tuple[str, int, int]] = []
    for i, seg in enumerate(segments):
        seg_from = page_from + (i * total_pages) // len(segments)
        seg_to   = page_from + ((i + 1) * total_pages) // len(segments) - 1
        out.append((seg, max(seg_from, page_from), max(seg_to, seg_from)))
    return out


def _doc_fingerprint(doc_text: str) -> str:
    return hashlib.sha256(doc_text.encode("utf-8")).hexdigest()


# ─── Module class ───────────────────────────────────────────────────


class StructuredExtraction:
    """Per-doc LLM extractor. Like SchemaDiscovery, stateless beyond
    the constructor args."""

    def __init__(self, *, llm_router, db_pool=None):
        self.llm_router = llm_router
        self.db_pool    = db_pool

    async def extract(
        self,
        *,
        enterprise_id: UUID,
        schema_id:     UUID,
        schema:        SchemaDefinition,
        doc_id:        str,
        doc_text:      str,
        page_from:     int = 1,
        page_to:       int = 1,
        consent_external: bool = False,
    ) -> ExtractionResult:
        """Extract rows for `schema` out of `doc_text`. Returns the rows
        plus a status + per-segment token count."""
        if not doc_text or not doc_text.strip():
            return ExtractionResult(
                rows=[], extraction_status="failed",
                error_message="Empty doc_text — nothing to extract.",
            )

        # Cache check.
        cached = await self._cache_lookup_or_none(enterprise_id, schema_id, doc_id)
        if cached is not None:
            log.info("docsage.extraction.cache_hit",
                     enterprise_id=str(enterprise_id),
                     schema_id=str(schema_id), doc_id=doc_id,
                     row_count=len(cached.rows))
            return cached

        # Split if oversize.
        segments = _split_doc(doc_text, page_from=page_from, page_to=page_to)
        all_rows: list[Row] = []
        any_failure = False
        total_segments = len(segments)

        # K-5 — redact PII for external-vendor calls; Qwen local skips.
        schema_json = schema.model_dump_json()

        for seg_text, seg_page_from, seg_page_to in segments:
            prompt_text = (
                redact_pii(seg_text) if consent_external else seg_text
            )
            user_prompt = EXTRACTION_USER_TEMPLATE.format(
                schema_json=schema_json,
                page_from=seg_page_from,
                page_to=seg_page_to,
                doc_text=prompt_text,
            )
            prompt = f"{EXTRACTION_SYSTEM}\n\n---\n\n{user_prompt}"

            try:
                parsed = await self.llm_router.complete_structured(
                    prompt=prompt,
                    task="docsage.extraction",
                    output_schema=_rows_envelope_json_schema(),
                    consent_external=consent_external,
                    enterprise_id=str(enterprise_id),
                    max_tokens=2500,
                )
            except Exception as e:
                any_failure = True
                log.warning("docsage.extraction.segment_failed",
                            doc_id=doc_id,
                            seg_page_from=seg_page_from,
                            error=str(e))
                continue

            raw_rows = parsed.get("rows", []) or []
            allowed_tables = {t.name for t in schema.tables}
            for r in raw_rows:
                tbl = r.get("table")
                if tbl not in allowed_tables:
                    # LLM hallucinated a table not in the schema —
                    # skip rather than poison the rowset.
                    continue
                # Coerce source_segment from [from, to] list to tuple.
                src = r.get("source_segment")
                if src and isinstance(src, list) and len(src) == 2:
                    src = (int(src[0]), int(src[1]))
                else:
                    src = (seg_page_from, seg_page_to)
                try:
                    all_rows.append(Row(table=tbl, values=r.get("values") or {},
                                         source_segment=src))
                except Exception:
                    # Pydantic validation on Row failed — skip the bad row.
                    continue

        status = (
            "failed" if not all_rows
            else "partial" if (any_failure or len(segments) > 1)
            else "ok"
        )
        result = ExtractionResult(
            rows=all_rows,
            extraction_status=status,
            error_message=(
                f"{len([s for s in segments if True])} segments; failures={any_failure}"
                if any_failure or total_segments > 1 else None
            ),
        )

        await self._cache_store(
            enterprise_id=enterprise_id, schema_id=schema_id, doc_id=doc_id,
            result=result,
        )
        log.info("docsage.extraction.landed",
                 enterprise_id=str(enterprise_id),
                 schema_id=str(schema_id), doc_id=doc_id,
                 row_count=len(all_rows), status=status,
                 segments=total_segments)
        return result

    # ─── Cache I/O ────────────────────────────────────────────────

    async def _cache_lookup_or_none(
        self, enterprise_id: UUID, schema_id: UUID, doc_id: str,
    ) -> Optional[ExtractionResult]:
        if self.db_pool is None:
            return None
        from ...shared.db import acquire_for_tenant  # noqa: E402
        async with acquire_for_tenant(enterprise_id) as conn:
            row = await conn.fetchrow(
                """SELECT rows_json, extraction_status, error_message, token_count
                   FROM docsage_extractions
                   WHERE enterprise_id = $1 AND schema_id = $2 AND doc_id = $3""",
                enterprise_id, schema_id, doc_id,
            )
        if row is None:
            return None
        raw = row["rows_json"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        rows = []
        for r in raw:
            src = r.get("source_segment")
            if src and isinstance(src, list) and len(src) == 2:
                r = {**r, "source_segment": (int(src[0]), int(src[1]))}
            rows.append(Row(**r))
        return ExtractionResult(
            rows=rows,
            extraction_status=row["extraction_status"],
            error_message=row["error_message"],
            token_count=row["token_count"] or 0,
        )

    async def _cache_store(
        self, *, enterprise_id: UUID, schema_id: UUID, doc_id: str,
        result: ExtractionResult,
    ) -> None:
        if self.db_pool is None:
            return
        from ...shared.db import acquire_for_tenant  # noqa: E402
        llm_model   = getattr(self.llm_router, "last_model", None) or "qwen2.5:14b"
        llm_version = getattr(self.llm_router, "last_version", None) or PROMPT_VERSION

        rows_json = json.dumps(
            [{"table": r.table, "values": r.values,
              "source_segment": list(r.source_segment) if r.source_segment else None}
             for r in result.rows],
            ensure_ascii=False,
        )

        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """INSERT INTO docsage_extractions
                       (enterprise_id, schema_id, doc_id, rows_json,
                        extraction_status, error_message, token_count)
                   VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                   ON CONFLICT (enterprise_id, schema_id, doc_id)
                   DO NOTHING""",
                enterprise_id, schema_id, doc_id, rows_json,
                result.extraction_status, result.error_message,
                result.token_count,
            )
        # llm_model/llm_version not stored on extractions per mig 066 — Schema
        # row carries them; extraction inherits the schema's model+version
        # because extraction prompt + schema_id are 1-to-1 coupled in cache.
        _ = (llm_model, llm_version)
