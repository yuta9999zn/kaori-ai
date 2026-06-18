"""
Pattern 3 (MinerU borrow) — PDF table extraction via pdfplumber.

Why this exists
---------------
pypdf's `page.extract_text()` returns a single flat string per page.
For tables, that string contains all the cells but no structure —
columns interleave with header rows + body rows, separators get lost.
DocSage Schema Discovery downstream cannot tell "12 rows of customer
data starting at line 84" from "12 lines of prose mentioning
customers".

pdfplumber parses the PDF content stream + reconstructs the table
grid by clustering text positions. Output is nested lists. We
convert each table into:
  - `rows`: list[list[str]] — raw cell content
  - `markdown`: renderable for prompt feed (DocSage prompts)
  - `html`: minimal HTML for FE renderer
  - `n_rows`, `n_cols`: counts for telemetry

Design choices
--------------
1. **Tables emitted as separate Block(type=TABLE)** alongside the
   page's TEXT block — so DocSage can iterate `blocks_by_type(BlockType.TABLE)`
   independently of prose extraction.
2. **char_start / char_end refer to the table's markdown serialization
   inside the assembled text**, NOT the table's bbox in the original
   PDF. The TEXT block for that page covers prose only (with table
   regions blanked).
3. **No bbox storage in this commit** — Pattern 5 (citation
   enrichment) adds bbox later. Today we just track `page_idx` for
   citation-back-to-page accuracy.
4. **pdfplumber is best-effort**: complex layouts (merged cells,
   nested tables, rotated tables) come back as raw nested lists where
   some cells are None. We pass them through; downstream extractors
   can decide whether to repair or reject.

K-rules
-------
K-3 N/A — no LLM. K-5 N/A — bytes never leave the process.
side_effect_class = pure compute (write_idempotent at most via the
caller that persists to bronze metadata).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

log = structlog.get_logger()


@dataclass(frozen=True)
class ExtractedTable:
    """One table extracted from one page. Reading order via the
    natural pdfplumber `extract_tables()` ordering (top → bottom →
    left → right per the cluster algorithm)."""
    page_idx:  int
    rows:      list[list[str]]    # cell strings; empty cells = ""
    markdown:  str                # rendered for LLM prompts
    html:      str                # minimal table HTML for FE
    # Pattern 5 (BE foundation 2026-05-19) — pdfplumber's table.bbox
    # tuple (x0, top, x1, bottom) in PDF user-space points. None when
    # pdfplumber couldn't compute (rare; falls through extract_tables
    # success path without find_tables sidecar data).
    bbox:      Optional[tuple[float, float, float, float]] = None

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        if not self.rows:
            return 0
        return max(len(r) for r in self.rows)


def extract_tables_from_pdf(content: bytes) -> list[ExtractedTable]:
    """Extract every table from every page of the PDF bytes.

    Returns an empty list when pdfplumber is unavailable OR the PDF has
    no detectable tables OR every page's table-detect raised. Errors
    are logged at WARNING (so the caller can ship without failing the
    whole upload), but never re-raised — table extraction is enrichment,
    not gate.
    """
    try:
        import pdfplumber
    except ImportError:
        log.warning("table_extractor.pdfplumber_unavailable")
        return []

    tables_out: list[ExtractedTable] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                # Pattern 5 BE — em fetch find_tables() in parallel with
                # extract_tables() so em get both the rows + the bbox
                # per table. extract_tables alone returns nested lists
                # without coords; find_tables returns Table objects with
                # .bbox + .rows in the same order as extract_tables
                # output (pdfplumber API contract). Em zip the two.
                try:
                    page_tables_rows = page.extract_tables() or []
                except Exception as e:   # noqa: BLE001
                    log.warning("table_extractor.page_failed",
                                page_idx=page_idx, error=str(e))
                    continue
                try:
                    page_tables_objs = page.find_tables() or []
                except Exception:   # noqa: BLE001
                    # find_tables is enrichment; if it fails em still
                    # get the rows just without bbox.
                    page_tables_objs = []
                for tbl_idx, raw_rows in enumerate(page_tables_rows):
                    cleaned = _clean_rows(raw_rows)
                    if not _is_useful_table(cleaned):
                        continue
                    bbox: Optional[tuple[float, float, float, float]] = None
                    if tbl_idx < len(page_tables_objs):
                        try:
                            raw_bbox = page_tables_objs[tbl_idx].bbox
                            bbox = (float(raw_bbox[0]), float(raw_bbox[1]),
                                     float(raw_bbox[2]), float(raw_bbox[3]))
                        except Exception:   # noqa: BLE001
                            bbox = None
                    tables_out.append(ExtractedTable(
                        page_idx=page_idx,
                        rows=cleaned,
                        markdown=rows_to_markdown(cleaned),
                        html=rows_to_html(cleaned),
                        bbox=bbox,
                    ))
    except Exception as e:   # noqa: BLE001
        log.warning("table_extractor.open_failed", error=str(e))
        return tables_out
    return tables_out


# ─── Cleaning ────────────────────────────────────────────────────────


def _clean_cell(cell: Optional[str]) -> str:
    """Normalise one cell: None → ""; collapse newlines + multi-space
    inside a cell. pdfplumber sometimes returns multi-line cells when
    a cell spans rows in the source."""
    if cell is None:
        return ""
    s = str(cell).strip()
    # Collapse internal whitespace runs (newlines/tabs/multiple spaces)
    s = re.sub(r"\s+", " ", s)
    return s


def _clean_rows(rows: list[list[Optional[str]]]) -> list[list[str]]:
    """Normalise every cell in the table. Drops rows that are 100%
    empty (pdfplumber adds gridline-only rows sometimes)."""
    out: list[list[str]] = []
    for r in rows:
        if r is None:
            continue
        cleaned = [_clean_cell(c) for c in r]
        if any(cell for cell in cleaned):   # at least one non-empty cell
            out.append(cleaned)
    return out


def _is_useful_table(rows: list[list[str]]) -> bool:
    """Filter pdfplumber false positives. A "table" with 1 row + 1 cell
    is just text in a box; not worth a TABLE block.
    """
    if not rows:
        return False
    if len(rows) < 2:
        return False
    max_cols = max(len(r) for r in rows)
    return max_cols >= 2


# ─── Renderers ───────────────────────────────────────────────────────


def rows_to_markdown(rows: list[list[str]]) -> str:
    """Render rows as a GitHub-flavored markdown table. First row
    treated as the header (best-effort; DocSage prompts handle the
    "header is actually data" case)."""
    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)
    # Pad each row to max_cols so columns line up
    padded = [(r + [""] * (max_cols - len(r))) for r in rows]
    header = padded[0]
    body = padded[1:] if len(padded) > 1 else []
    # Escape pipes inside cells
    def _esc(s: str) -> str:
        return s.replace("|", r"\|")
    lines: list[str] = []
    lines.append("| " + " | ".join(_esc(c) for c in header) + " |")
    lines.append("|" + "|".join("---" for _ in range(max_cols)) + "|")
    for row in body:
        lines.append("| " + " | ".join(_esc(c) for c in row) + " |")
    return "\n".join(lines)


def rows_to_html(rows: list[list[str]]) -> str:
    """Minimal HTML table — first row → <thead><th>, rest → <tbody><td>.
    No styling; intended for FE renderer to apply table CSS itself.
    Escapes &, <, >, " to keep emitted HTML safe."""
    if not rows:
        return ""
    def _esc(s: str) -> str:
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;"))
    parts: list[str] = ['<table>']
    header = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    parts.append("<thead><tr>")
    for cell in header:
        parts.append(f"<th>{_esc(cell)}</th>")
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for row in body:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{_esc(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)
