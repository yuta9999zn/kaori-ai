"""
Stage 2B — LLM fallback for column mapping.

Existing 3-step cascade in column_mapper.py:
  Step 1 exact match → confidence 1.0
  Step 2 fuzzy match (rapidfuzz) → confidence 0.65-0.95
  Step 3 no_match → passthrough (source.lower().replace(' ', '_'))

This module ships Step 3 properly: when fuzzy fails, ask Qwen via
llm-gateway which canonical name fits best. Returns a confidence-rated
mapping that the caller folds back into the result list before the
write to canonical_schemas.

K-3 / K-4 compliance:
  - llm-gateway only (`POST /v1/infer`); never direct Ollama HTTP
  - consent_external=False ALWAYS — Qwen local by design, per ADR-0015
    K-4 invariant. Column mapping is structural metadata; never sent to
    external vendor regardless of tenant consent.

K-6: Each LLM-fallback decision is logged to decision_audit_log by the
caller (routers/schema.py already does this for every mapping —
adding the llm_fallback method just changes the `method` column value).

Cost guard rails:
  - One LLM call per BATCH of unmapped columns (not per-column)
  - Cap batch at 20 columns; remainder degrades to passthrough
  - 5 sec timeout — if Qwen is slow, fall back to passthrough rather
    than block the /schema response
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")
TIMEOUT_S       = 5.0
MAX_BATCH       = 20
# Pilot guard: the column-naming fallback asks the local model to name every
# unrecognised column. On the 7B pilot box one call already exceeds the 5s
# timeout, so for a multi-sheet workbook (one call per sheet) /schema piles up
# past the gateway's 30s budget → 504, while delivering nothing (all calls
# time out). Default ON for the 14B production model; pilot sets it to 0.
FALLBACK_ENABLED = os.getenv("SCHEMA_LLM_FALLBACK", "1").lower() not in ("0", "false", "no", "")

# Issue #3 — JSON Schema for the LLM response. Mirrors mappings[] row
# shape so the caller can splice without translation.
_OUTPUT_SCHEMA = {
    "type":     "object",
    "required": ["mappings"],
    "additionalProperties": False,
    "properties": {
        "mappings": {
            "type":     "array",
            "minItems": 1,
            "maxItems": MAX_BATCH,
            "items": {
                "type":     "object",
                "required": ["source_column", "canonical_name", "data_type", "confidence"],
                "additionalProperties": False,
                "properties": {
                    "source_column":  {"type": "string", "maxLength": 200},
                    "canonical_name": {"type": "string", "maxLength": 100,
                                        "pattern": "^[a-z][a-z0-9_]*$"},
                    "data_type":      {"type": "string",
                                        "enum": ["text", "integer", "numeric",
                                                  "date", "timestamp", "boolean"]},
                    "confidence":     {"type": "number",
                                        "minimum": 0.0, "maximum": 1.0},
                },
            },
        },
    },
}


def _prompt(source_cols: list[str], canonical_options: list[str],
            detected_lang: str) -> str:
    """Build the LLM prompt. Vietnamese-aware; uses bullet list for
    options + columns so token efficiency stays high (avoid JSON-of-
    JSON in the prompt itself)."""
    options_block = "\n".join(f"  - {c}" for c in canonical_options)
    cols_block = "\n".join(f"  - {c}" for c in source_cols)
    return (
        "Bạn là agent map tên cột dữ liệu sang vocab canonical.\n\n"
        "Quy tắc:\n"
        "  1. Chỉ chọn `canonical_name` từ danh sách dưới — KHÔNG tự tạo tên mới.\n"
        "  2. Confidence 0.4-0.7 — đây là semantic guess, KHÔNG phải exact/fuzzy match.\n"
        "  3. Nếu thực sự không khớp gì → giữ canonical_name = `unknown`, confidence = 0.0.\n"
        "  4. data_type phải đúng (text/integer/numeric/date/timestamp/boolean).\n\n"
        f"Ngôn ngữ phát hiện: {detected_lang!r}\n\n"
        "Canonical options:\n"
        f"{options_block}\n\n"
        "Source columns cần map (mỗi cột 1 row trong response):\n"
        f"{cols_block}\n\n"
        "Trả JSON đúng schema, KHÔNG markdown, KHÔNG ``` fences."
    )


async def enrich_with_llm_fallback(
    mappings: list[dict],
    language_dict: dict,
    detected_lang: str = "unknown",
    enterprise_id: Optional[str] = None,
    run_id: Optional[str] = None,
    deadline: Optional[float] = None,
) -> list[dict]:
    """Replace `no_match` rows in `mappings` with LLM-derived guesses.

    In-place semantics: caller's `mappings` list is mutated AND
    returned (for chaining ergonomics).

    Safe degradation: if LLM gateway is unreachable or returns invalid
    output, the no_match rows stay as-is (passthrough). Never raises —
    Stage 2B is best-effort enrichment, not a hard dependency.

    Bounded: skips entirely when disabled (pilot) or past ``deadline``
    (a ``time.monotonic()`` value the caller shares across sheets so the
    whole /schema request can't blow the gateway timeout). Blank/Unnamed
    columns are never sent — there's nothing to name, and they dominate
    the batch on real workbooks.
    """
    if not FALLBACK_ENABLED:
        return mappings
    if deadline is not None and time.monotonic() > deadline:
        log.info("llm_column_fallback.budget_exhausted")
        return mappings

    unmapped = [
        m for m in mappings
        if m.get("method") == "no_match"
        and not m.get("is_empty") and not m.get("looks_unnamed")
    ]
    if not unmapped:
        return mappings

    # Cap batch — beyond MAX_BATCH the LLM prompt cost explodes + Qwen
    # 2K context likely truncates. Remainder stays passthrough.
    batch = unmapped[:MAX_BATCH]
    overflow = unmapped[MAX_BATCH:]
    if overflow:
        log.warning("llm_column_fallback.overflow",
                    overflow_count=len(overflow),
                    cap=MAX_BATCH)

    canonical_options = sorted(language_dict.keys()) + ["unknown"]
    source_cols = [m["source_column"] for m in batch]
    prompt = _prompt(source_cols, canonical_options, detected_lang)

    body = {
        "task":             "schema.column_mapping_fallback",
        "prompt":           prompt,
        "enterprise_id":    enterprise_id or "00000000-0000-0000-0000-000000000000",
        "consent_external": False,        # K-4: Qwen local always for schema work
        "max_tokens":       1500,
        "output_schema":    _OUTPUT_SCHEMA,
    }
    if run_id:
        body["run_id"] = run_id

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(f"{LLM_GATEWAY_URL}/v1/infer", json=body)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("llm_column_fallback.gateway_error",
                    error=str(e), batch_size=len(batch))
        return mappings   # passthrough on failure

    validation = payload.get("output_validation") or {}
    parsed = validation.get("parsed_json")
    if not parsed or not isinstance(parsed, dict):
        log.warning("llm_column_fallback.no_parsed_json")
        return mappings

    llm_rows = parsed.get("mappings") or []
    # Index by source_column for splicing.
    by_source = {r["source_column"]: r for r in llm_rows
                  if isinstance(r, dict) and "source_column" in r}

    splice_count = 0
    for m in mappings:
        if m.get("method") != "no_match":
            continue
        llm_row = by_source.get(m["source_column"])
        if not llm_row:
            continue
        canonical = llm_row.get("canonical_name") or "unknown"
        if canonical == "unknown":
            # LLM admitted it can't map — keep no_match but record
            # the attempt so audit shows we tried.
            m["uncertainty_flags"] = list(m.get("uncertainty_flags") or []) + [
                "LLM_FALLBACK_UNKNOWN"
            ]
            continue
        m["canonical_name"]    = canonical
        m["data_type"]         = llm_row.get("data_type", "text")
        m["confidence"]        = float(llm_row.get("confidence", 0.5))
        m["method"]            = "llm_fallback"
        m["uncertainty_flags"] = ["LLM_FALLBACK_USED"]
        splice_count += 1

    log.info("llm_column_fallback.enriched",
             batch_size=len(batch),
             spliced=splice_count,
             overflow=len(overflow),
             enterprise_id=enterprise_id)
    return mappings
