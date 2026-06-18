# MinerU Pattern Analysis — research, not adoption

> **Status:** Research 2026-05-18. NO code changes yet — em ship docs analyzing what to learn from `opendatalab/MinerU` and what to keep as-is in Kaori.
>
> **Anh's directive 2026-05-18:** "phải có SQL trước khi dùng RAG" — re-emphasized. MinerU output is an INPUT to Kaori's Silver tier; SQL-first ordering on Gold/Silver tables is non-negotiable.

## TL;DR

| Question | Answer |
|---|---|
| Is MinerU better than Kaori's current Stage 6? | At extraction quality for layout-rich docs, **yes** (tables, multi-column, formulas, scanned PDFs). |
| Should we pip-install + wrap it? | **No** — same reason as ADR-0024 mem0 + PageIndex defer. 1.2B parameter VLM model violates K-4 (Qwen-first), needs 2-8 GB VRAM, brings LiteLLM bridge complexity. |
| Should we borrow patterns? | **Yes** — 5 patterns are valuable + lightweight. Em proposes ADR-0025 for the decision. |
| Does this change SQL-first ordering? | **No** — MinerU's strong table extraction would FEED Silver tier earlier, not replace it. The flow stays: extract → Silver → SQL → RAG-fallback. |

## What MinerU is

`opendatalab/MinerU` (Apache 2.0 since v3) — document parsing engine that converts PDF/DOCX/PPTX/XLSX/scanned-images into structured JSON or markdown for LLM workflows.

Pipeline backends:
- **Pipeline** — CPU-friendly, ~85% accuracy
- **VLM-engine** — uses MinerU2.5-Pro 1.2B parameter vision-LLM, ~95% accuracy, needs 2-8 GB VRAM
- **Hybrid** — combines native parse + VLM verification

Output formats:
- `content_list.json` — flat reading-order array (RAG-friendly)
- `middle.json` — hierarchical (Level 1 blocks → Level 2 → Lines → Spans)
- Markdown (multimodal + NLP variants)

Block taxonomy (every block has `type` + `bbox` + `page_idx`):
- `text`, `title`, `list`, `interline_equation`
- `table_body` + `table_caption` + `table_footnote`
- `image_body` + `image_caption` + `image_footnote`
- `chart`, `code`, `header`, `footer`, `page_number`, `aside_text`, `page_footnote`

Tables convert to HTML; formulas to LaTeX; images extracted as separate files with descriptions.

## What Kaori does today

`services/data-pipeline/data_plane/silver/docsage_extract.py` (Stage 6, P15-S11 ship):

```python
class ExtractResult:
    text: str               # one long string, '\n'-joined per-page
    page_offsets: list[int] # for citation span back to original PDF page
    status: str             # ok / partial / unsupported_today / failed
    error_message: Optional[str]
    page_count: int
    char_count: int
```

Backends:
- PDF: `pypdf` — `page.extract_text()` per page, no layout awareness
- DOCX: `python-docx` — paragraph iteration
- Image / scanned PDF: `status='unsupported_today'` (defer to Qwen2-VL Phase 2)

Strengths Kaori already has that MinerU doesn't replace:
1. **Vietnamese-aware downstream** — `docs/specs/MESSAGE_DEFINITIONS.md` + ngôn ngữ kinh doanh in error copy
2. **Citation contract** — `(page_offset_start, page_offset_end)` flows through DocSage rows → FE highlights original PDF
3. **Medallion separation** — extraction is in `silver/`, NOT bronze (memory `feedback_medallion_separation`)
4. **Idempotent K-13** — `write_idempotent` declared per CLAUDE.md K-17
5. **Bronze appendix preserved** — raw bytes stay; Silver is the typed view

Weaknesses vs MinerU:
1. ❌ No table extraction — tables flatten into plain text run-ons
2. ❌ No reading-order awareness — multi-column reports interleave columns wrong
3. ❌ No header/footer/footnote auto-removal — page numbers + boilerplate pollute the text
4. ❌ No block-type vocabulary — `text` is all DocSage gets, can't distinguish title from body
5. ❌ No image extraction with captions
6. ❌ No formula recognition (probably fine — Vietnamese business docs rarely have LaTeX-grade math)
7. ❌ No OCR for scanned PDFs (defer to Phase 2 Qwen2-VL adapter is in plan)

## Patterns Kaori SHOULD borrow (lightweight, no GPU)

### Pattern 1 — Block-type taxonomy

Extend `ExtractResult` to optionally carry block-level structure:

```python
@dataclass(frozen=True)
class Block:
    type:        str       # 'text' | 'title' | 'list' | 'table' | 'header' | 'footer' | …
    page_idx:    int
    char_start:  int       # offset into ExtractResult.text
    char_end:    int
    metadata:    dict      # table_html / table_caption / list_marker / …

@dataclass(frozen=True)
class ExtractResult:
    text:          str
    page_offsets:  list[int]
    blocks:        list[Block]  # NEW — populated when extractor supports it
    status:        str
    error_message: Optional[str] = None
    page_count:    int = 0
    char_count:    int = 0
```

Backwards compatible — existing callers ignore `blocks`. DocSage Schema Discovery + Structured Extraction get a richer signal to find table-shaped data without re-implementing detection.

**Effort:** ~1 dev-day. Pure Python, no new dep.

### Pattern 2 — Header/footer/page-number auto-removal

Heuristic: lines that repeat ≥3 times across pages at the same vertical position are header/footer. Strip them BEFORE feeding to DocSage.

```python
def strip_repeating_lines(pages_text: list[str], *, min_repeats: int = 3) -> list[str]:
    """Remove lines that appear at the same vertical position on ≥
    min_repeats pages. Catches headers, footers, page numbers, watermarks.
    """
    ...
```

Avoid false positives: don't strip if the line is the ONLY content on a short page (single-line cover page).

**Effort:** ~0.5 dev-day. Phase 2.5 task — light + valuable.

### Pattern 3 — Table extraction (markdown fallback)

`pypdf` alone can't reconstruct tables. But `pdfplumber` (~5 MB pure Python) extracts tables as nested lists. Render to markdown:

```
| Mã KH      | Doanh thu     | Trạng thái |
|------------|---------------|------------|
| KH-001     | 1.500.000₫    | ✓          |
| KH-002     | 2.300.000₫    | ✗          |
```

DocSage Schema Discovery already understands markdown tables (LLM prompt mention). Tables become first-class — em can detect "this PDF page has 12 rows of customer data" instead of one giant text blob.

**Effort:** ~2 dev-days. Adds `pdfplumber` dep (5 MB).

### Pattern 4 — Reading-order normalization

For multi-column PDFs, `pypdf.page.extract_text()` reads top-to-bottom-left-to-right which interleaves columns. MinerU's content_list.json sorts by bbox. We can use `pdfplumber.page.extract_text(layout=True)` to get layout-preserved text, then sort blocks by (column-band, y-position).

**Effort:** ~1.5 dev-days. Critical for Vietnamese financial reports (often 2-column).

### Pattern 5 — Citation enrichment (bbox alongside page)

Current DocSage citation: `(page_start, page_end)`. With MinerU pattern: `(page, bbox)` lets the FE highlight the SPECIFIC region on the PDF.

`bronze_files.metadata.docsage_blocks: jsonb` stores blocks list; DocSage Structured Extraction Row gets `source_block_idx` instead of (or alongside) `source_segment`.

**Effort:** ~1 dev-day plus FE PDF viewer changes (FE paused per CLAUDE.md §2).

## Patterns Kaori SHOULD NOT borrow

1. **MinerU2.5-Pro 1.2B VLM model** — violates K-4 (Qwen-first); needs 2-8 GB VRAM; 1.2 GB model weights download; conflicts with our `llm-gateway` routing.
2. **LiteLLM bridge** — same reason as PageIndex defer (50 MB dep + indirection layer).
3. **PaddleOCR 109-language pack** — heavy (~2 GB models). Em already defer OCR to Qwen2-VL adapter via llm-gateway — narrower scope + reuses existing LLM dispatch.
4. **REST API surface (`POST /file_parse`)** — Kaori has `POST /api/v1/upload` already wired to bronze → silver → DocSage. Don't add a parallel surface.
5. **Standalone CLI (`mineru -p input -o output`)** — Kaori's flow is web-driven; CLI is friction.

## Anh's SQL-first directive — re-emphasized

> "đặc biệt nhắc lại chắc chắn phải có sql trước khi dùng rag"

The flow stays:

```
1. Stage 6 extract — bytes → text + blocks (proposed Pattern 1)
   ↓
2. Silver per-domain tables (mig 051 + 084 grants)
   — DocSage Structured Extraction lands customer/vendor/contract
     rows here as deterministic SQL-queryable data
   ↓
3. Gold views (mig 052 Gold-from-Silver-only)
   ↓
4. KPI engine SQL compute (reasoning/kpi_engine/) — DETERMINISTIC,
   answers questions like "tổng doanh thu tháng 5" in milliseconds
   without ANY LLM call
   ↓
5. RAG only as fallback when SQL can't answer
   (e.g., "what does this customer's contract say about late fees")
```

MinerU pattern adoption STRENGTHENS this ordering because better Stage 6 extraction = more rows land in Silver as structured = more questions answered by deterministic SQL before falling back to RAG.

**Failure mode to avoid:** treating MinerU's JSON output as RAG corpus directly. That bypasses Silver/Gold + makes every question an LLM call. SQL-first means the JSON output FEEDS Silver Schema Discovery first; RAG only sees text after the structured-extraction layer has had its pass.

## Proposed ADR-0025 (not yet shipped)

```
Title: Adopt MinerU patterns selectively without the library

Status: Proposed 2026-05-18

Context:
  Stage 6 unstructured doc extraction uses pypdf + python-docx —
  basic text-per-page only. MinerU offers superior block-type
  taxonomy + table extraction + reading order. But the library
  ships a 1.2B VLM model + LiteLLM bridge that violates K-4
  (Qwen-first) and adds 2-8 GB VRAM requirement.

Decision:
  Borrow 5 patterns (block taxonomy / header-footer strip / table
  extraction via pdfplumber / reading-order normalization /
  bbox citation), implement natively in Kaori. Do NOT wrap the
  MinerU library.

  Same model as ADR-0024 mem0 (borrow patterns NOT library) and
  the 2026-05-18 PageIndex re-decision.

Consequences:
  + Stage 6 output quality jumps for multi-column docs + tables
  + DocSage Schema Discovery gets a richer signal; more rows
    land in Silver as deterministic SQL data
  + Anh's SQL-first directive strengthened
  - pdfplumber dep (5 MB) added; pypdf stays for the simple path
  - ~5 dev-days of work spread across Phase 2.5 / Phase 3
  - Need to maintain in-house heuristics (header/footer stripping,
    reading-order sorting) that MinerU would have done for us

Alternatives considered:
  - Pip install MinerU + wrap. Rejected: K-4 + VRAM + LiteLLM
    indirection.
  - Wrap MinerU's pipeline-CPU backend (no VLM). Rejected: still
    pulls PaddleOCR + LiteLLM; AGPL→Apache transition only just
    landed (commercial risk window).
  - Do nothing — current pypdf text path is fine for v0. Rejected:
    multi-column Vietnamese reports interleave columns wrong;
    tables flatten unusably.
```

## Suggested rollout order (Phase 2.5)

| Order | Pattern | Effort | Blocker |
|---|---|---|---|
| 1 | Header/footer/page-number strip | 0.5 day | none |
| 2 | Block-type taxonomy (data model) | 1 day | none |
| 3 | Table extraction via pdfplumber | 2 days | new dep |
| 4 | Reading-order normalization | 1.5 day | depends on 3 |
| 5 | Bbox citation enrichment | 1 day | FE work, FE paused |

Total Phase 2.5 budget: ~6 dev-days. Items 1+2+3 give 80% of the value (better Stage 6 output flowing to SQL-first Silver).

## What to do next

If anh signs off ADR-0025, em propose this rollout:
1. **Week 1** — Pattern 1 (block taxonomy) + Pattern 2 (header/footer strip). Light + builds new contract.
2. **Week 2** — Pattern 3 (pdfplumber tables). Bigger lift; adds dep.
3. **Phase 3** — Pattern 4 + 5 (reading order + bbox citation). Tied to FE PDF viewer work that can't happen until template restructure done.

Em can ship Week 1 in 1.5 dev-days end-to-end. Anh chốt khi nào ship.

## References

- `opendatalab/MinerU` repo: https://github.com/opendatalab/MinerU
- ADR-0024 (borrow patterns not library): `docs/adr/0024-borrow-patterns-not-libraries.md` (TODO — anh hasn't written explicit ADR yet; the principle is referenced from mem0 + PageIndex commits)
- `services/data-pipeline/data_plane/silver/docsage_extract.py` — current Stage 6 implementation
- `services/ai-orchestrator/reasoning/kpi_engine/` — SQL-first deterministic compute that this analysis preserves
- CLAUDE.md K-4 (Qwen-first), K-9 (NUMERIC precision), K-17 (side_effect_class)
