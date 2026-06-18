"""
Phase 2.5 — `extract_structured_data` AI node.

Takes TABLE Blocks from Stage 6 output (Pattern 3 pdfplumber) +
a target schema (column names + types) and returns typed rows
ready to INSERT into Silver per-domain tables.

This is the AI node that closes the loop between MinerU-pattern
extraction (table blocks) and SQL-first ordering (Silver typed
rows). DocSage's existing Schema Discovery + Structured Extraction
uses prose-side blocks; this new node specifically targets table-
shaped blocks where pdfplumber already gave us nested lists.

Use cases (per WORKFLOW_USE_CASES.md — 10 of 20 cases hit this):
- 2  Financial Q report (multi-table)
- 3  Vendor invoice (line items)
- 4  Bank statement (transaction rows)
- 5  VAT report
- 13 Purchase order line items
- 18 CRM master data upsert (PDF imports)
- 20 Insurance claim line items

Design choices
--------------
1. **Schema-driven** — caller passes the target column shape. The LLM's
   job is to MAP table columns to target columns + parse cell values
   to the target type. No "discover schema from scratch" — that's a
   separate node (DocSage Schema Discovery).
2. **Per-table extraction** — em call the LLM once per TABLE block.
   Long docs with 5+ tables get 5+ LLM calls; caller decides whether
   to throttle.
3. **Strict JSON output** — output_schema enforces the row shape so
   typos surface as 502 before they hit Silver.
4. **No INSERT in this module** — caller persists. Keeps the node
   pure read_only per K-17.

K-rules
-------
K-3: LLM via llm_router only. K-4: Qwen default; consent_external opt-in.
K-9: NUMERIC fields stay strings until the caller's Silver INSERT
     converts. Em pass them through without Decimal coercion — the
     prompt asks for canonical "1234567.89" form.
K-17: side_effect_class = read_only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from ..data_plane_shim import Block, BlockType
from ..engine.llm_router import llm_router

log = structlog.get_logger()


@dataclass
class ColumnSpec:
    """One target column the caller wants populated. The LLM reads
    `description` for context — keep it concrete + Vietnamese."""
    name:        str             # snake_case key in the output row
    type:        str             # "string" | "number" | "integer" | "date" | "boolean"
    description: str             # one-line natural-language hint
    required:    bool = True
    enum:        Optional[list[str]] = None    # for finite-value columns


@dataclass
class ExtractInput:
    blocks:        list[Block]
    target_schema: list[ColumnSpec]
    enterprise_id: str
    consent_external: bool = False
    run_id:        Optional[str] = None
    # Confidence floor for accepting the mapping. Tables where the LLM
    # reports column-mapping confidence below this trigger
    # ExtractOutput.warnings entry; caller can reject.
    min_mapping_confidence: float = 0.6


@dataclass(frozen=True)
class ExtractedRow:
    """One typed row + provenance pointer to the source table."""
    values:           dict[str, Any]    # keyed by ColumnSpec.name
    source_page_idx:  int
    source_block_id:  int        # index into ExtractInput.blocks for citation


@dataclass(frozen=True)
class ExtractOutput:
    rows:              list[ExtractedRow]
    warnings:          list[str]        # human-readable per-table notes
    tables_processed:  int
    rows_extracted:    int


def _output_schema_for(columns: list[ColumnSpec]) -> dict[str, Any]:
    """Build a JSON Schema that strictly matches the caller's columns.
    Required vs optional per ColumnSpec.required."""
    props: dict[str, Any] = {}
    required_names: list[str] = []
    type_map = {
        "string":  "string",
        "number":  "number",
        "integer": "integer",
        "date":    "string",        # ISO date as string; caller parses
        "boolean": "boolean",
    }
    for col in columns:
        prop: dict[str, Any] = {"type": type_map.get(col.type, "string")}
        if col.enum:
            prop["enum"] = list(col.enum)
        if col.type == "date":
            prop["format"] = "date"
        props[col.name] = prop
        if col.required:
            required_names.append(col.name)
    return {
        "type": "object",
        "required": ["rows", "mapping_confidence", "notes"],
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": required_names,
                    "properties": props,
                },
            },
            "mapping_confidence": {
                "type": "number", "minimum": 0, "maximum": 1,
            },
            "notes": {"type": "string", "maxLength": 500},
        },
    }


def _column_brief(columns: list[ColumnSpec]) -> str:
    """Render columns as a Vietnamese-friendly cheat sheet for the
    prompt. Includes type + required flag + optional enum hint."""
    lines = []
    for c in columns:
        req = "BẮT BUỘC" if c.required else "tuỳ chọn"
        enum_hint = f" (giá trị: {', '.join(c.enum)})" if c.enum else ""
        lines.append(
            f"  - {c.name} ({c.type}, {req}){enum_hint}: {c.description}"
        )
    return "\n".join(lines)


def _build_prompt(table_md: str, columns: list[ColumnSpec]) -> str:
    """Compose the per-table extraction prompt. Asks the LLM to map
    the table's columns to the target columns then emit typed rows."""
    return "\n".join([
        "Bạn đang trích xuất dữ liệu có cấu trúc từ bảng PDF/DOCX.",
        "",
        "Bảng nguồn (markdown):",
        table_md,
        "",
        "Cấu trúc đích — hãy map cột bảng vào các trường sau:",
        _column_brief(columns),
        "",
        "Trả về JSON đúng schema:",
        "  rows                — mảng các object, mỗi object là 1 dòng đã map",
        "  mapping_confidence  — 0..1; bằng 1 nếu cột bảng khớp hoàn toàn",
        "                        với cấu trúc đích, thấp hơn nếu phải đoán",
        "  notes               — 1-2 câu giải thích quyết định map (tiếng Việt)",
        "Bỏ qua dòng trống, dòng tổng cộng, dòng header lặp giữa bảng.",
        "Số liệu: định dạng canonical '1234567.89' (không dấu phẩy nghìn).",
        "Ngày: ISO 'YYYY-MM-DD'.",
        "Không emit dòng nào không khớp cấu trúc đích.",
    ])


async def extract_structured_data(inp: ExtractInput) -> ExtractOutput:
    """Walk every TABLE block; per-table LLM call mapping table cells
    to target schema; aggregate into ExtractedRow list with
    provenance."""
    tables = [(i, b) for i, b in enumerate(inp.blocks) if b.type == BlockType.TABLE]
    if not tables:
        log.info("extract_structured_data.no_tables",
                  enterprise_id=inp.enterprise_id)
        return ExtractOutput(
            rows=[], warnings=["no_tables_in_input"],
            tables_processed=0, rows_extracted=0,
        )

    out_rows: list[ExtractedRow] = []
    warnings: list[str] = []
    output_schema = _output_schema_for(inp.target_schema)

    for block_idx, block in tables:
        prompt = _build_prompt(block.text, inp.target_schema)
        try:
            result = await llm_router.complete_with_schema(
                prompt=prompt,
                task="extract_structured_data",
                output_schema=output_schema,
                consent_external=inp.consent_external,
                enterprise_id=inp.enterprise_id,
                run_id=inp.run_id,
                max_tokens=2000,
            )
        except AttributeError:
            # Older llm_router — use plain complete + best-effort parse
            text = await llm_router.complete(
                prompt=prompt,
                task="extract_structured_data",
                consent_external=inp.consent_external,
                enterprise_id=inp.enterprise_id,
                run_id=inp.run_id,
                max_tokens=2000,
            )
            from .document_classifier import _parse_json_fallback
            result = _parse_json_fallback(text)
        except Exception as e:   # noqa: BLE001
            log.warning("extract_structured_data.table_failed",
                        block_idx=block_idx, page=block.page_idx, error=str(e))
            warnings.append(
                f"trang {block.page_idx + 1}: trích xuất thất bại ({type(e).__name__})"
            )
            continue

        confidence = float(result.get("mapping_confidence", 0.0))
        rows_raw = result.get("rows", []) or []
        notes = str(result.get("notes", ""))

        if confidence < inp.min_mapping_confidence:
            warnings.append(
                f"trang {block.page_idx + 1}: confidence map cột = "
                f"{confidence:.2f} < {inp.min_mapping_confidence:.2f}. "
                f"Ghi chú: {notes[:100]}"
            )
            # Still emit the rows — caller decides whether to drop or keep.

        for row_dict in rows_raw:
            if not isinstance(row_dict, dict):
                continue
            out_rows.append(ExtractedRow(
                values=row_dict,
                source_page_idx=block.page_idx,
                source_block_id=block_idx,
            ))

    log.info("extract_structured_data.done",
             tables=len(tables),
             rows_extracted=len(out_rows),
             warnings=len(warnings),
             enterprise_id=inp.enterprise_id)

    return ExtractOutput(
        rows=out_rows,
        warnings=warnings,
        tables_processed=len(tables),
        rows_extracted=len(out_rows),
    )
