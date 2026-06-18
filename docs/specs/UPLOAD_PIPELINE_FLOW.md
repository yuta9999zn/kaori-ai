# Upload pipeline — structured / unstructured split + workflow integration

> **Status:** Spec — Phase 2.5 design. Code starts shipping in same session (Pattern 1+2). Pattern 3-5 follow when anh signs off.
>
> **Constraint:** "phải có SQL trước khi dùng RAG" (anh, 2026-05-18). Both pipelines converge on Silver typed tables before any retrieval layer.

## Case anh asked about — contract approval workflow

```
Phòng ban A — Quy trình phê duyệt hợp đồng
─────────────────────────────────────────────────
  ┌───────────────────────┐
  │ Bước 1 — Tạo lập      │  user uploads contract (PDF/DOCX)
  │ hợp đồng              │  → bronze + extract + DocSage
  └──────────┬────────────┘
             ↓
  ┌───────────────────────┐
  │ Bước 2 — Trình ký     │  approval_gate (mig 058 + 068)
  │ (approval_gate)       │  → approver_role = MANAGER
  └──────────┬────────────┘
             ↓
        ┌────┴────┐
        ↓ OK      ↓ Không OK
  ┌──────────┐  ┌──────────┐
  │ Bước 3a  │  │ Bước 3b  │
  │ Đóng     │  │ if_else  │  (mig 068 'if_else' node)
  │ dấu đỏ + │  │ → loop   │
  │ send_    │  │   back   │
  │ email    │  │   to     │
  │          │  │   Bước 1 │
  └──────────┘  └──────────┘
```

### Catalog support (already shipped)

| Node type | Category | side_effect_class | Available |
|---|---|---|---|
| `step` (form upload) | basic | write_idempotent | mig 053 |
| `approval_gate` | decision | write_idempotent + Saga | mig 068 #35 |
| `if_else` | decision | pure | mig 068 #31 |
| `switch` | decision | pure | mig 068 #32 |
| `send_email` | action | external (Saga: send_retraction_email) | mig 068 #51 |
| `extract_structured_data` (AI) | ai | read_only | mig 068 ai category |
| `classify_document` (AI — future) | ai | read_only | NOT in mig 068; proposed extension |

**Conclusion:** anh's described workflow is **buildable today** with the existing node catalog. The branching (if/else loop back) maps to `if_else` node with `false_target_id` pointing to Bước 1.

### AI can / cannot do on contract content

| Question | AI capability | Where in Kaori |
|---|---|---|
| Extract parties (Bên A / Bên B) | ✅ Reliable (LLM structured extraction with schema) | DocSage Structured Extraction P15-S11 |
| Extract contract amount + currency | ✅ Reliable | DocSage + NUMERIC(14,4) Silver column per K-9 |
| Extract dates (sign date, effective date, expiry) | ✅ Reliable | DocSage with date format hints |
| Extract payment terms | 🟡 Variable confidence; legal vocabulary | DocSage with `expected_mapping_template_id` hint |
| Classify contract type (NDA / service / lease / employment) | ✅ Reliable | `classify_document` node (proposed Phase 2.5) |
| Compare contract clauses against policy template | 🟡 Possible with RAG over policy corpus | RAG layer, AFTER SQL-first extraction |
| Verify signature authenticity | ❌ Out of scope — needs cryptographic / forensic tooling | — |
| Verify red stamp authenticity | ❌ Out of scope — image forensics, legal weight | — |
| Detect clauses that DEVIATE from standard template | 🟡 Possible with embedding diff vs template corpus | RAG embedding similarity |
| Legal interpretation / risk assessment | ❌ NOT AI's job — lawyer's job. AI surfaces evidence; human decides. | — |

**Boundary line:** AI extracts + classifies + compares. AI does NOT make legal decisions. Approver still sees the document + the AI's extracted summary + the AI's "deviation flags" — approver clicks Approve/Reject.

### What anh's workflow needs (Phase 2.5+ to fully support)

1. ✅ Catalog has all node types — **already in mig 068**
2. ⏳ **Document type detector** — split structured vs unstructured at upload (this commit ships)
3. ⏳ **Stage 6 enrichment** — block taxonomy + header/footer strip so contract clauses extract cleanly (this commit ships Patterns 1+2)
4. ⏳ **Phase 2.5** — `classify_document` AI node for "contract type detection"
5. ⏳ **Phase 2.5** — `extract_clauses` AI node that returns `{party_a, party_b, amount, dates, terms}` structured JSON
6. ⏳ **Phase 3** — clause deviation detection vs template corpus (RAG layer)
7. ❌ Signature/stamp authenticity — explicit out-of-scope (legal tooling, not Kaori)

## Current state — what's wrong with the single /upload endpoint

`services/data-pipeline/routers/upload.py` accepts any mime + any filename → goes through one path:

```
[upload bytes] → [SHA-256 dedupe]
              → [bronze_files row]
              → IF mime IN whitelist (csv/xlsx/json):
                    → Stage 3 cleaning
                    → Silver typed
              → ELIF mime IN unstructured (pdf/docx):
                    → Stage 6 docsage_extract (one big text string)
                    → DocSage Schema Discovery
                    → Silver typed (no block awareness)
              → ELSE:
                    → status='unsupported_today'
```

Problems:
1. Detection logic interleaved with side effects (hard to test in isolation)
2. No block taxonomy — DocSage gets `text=str` only, can't distinguish title from body, table from prose
3. Header/footer pollute extracted text → noise in Schema Discovery
4. Workflow context (`X-Workflow-Step-ID` + `required_document_types`) validated AFTER bronze insert; em should validate BEFORE bytes touch disk
5. Multi-column PDFs interleave columns (pypdf top-to-bottom-left-to-right) — Vietnamese 2-column financial reports come out garbled

## Proposed flow — bifurcated pipeline

```
                ┌──────────────────────────┐
                │  POST /api/v1/upload      │
                │  + X-Workflow-Step-ID    │
                └─────────────┬────────────┘
                              ↓
                  ┌───────────────────────┐
                  │ 1. Detect document type│  ← NEW (this commit)
                  │    (mime + magic bytes)│
                  └───────┬───────────────┘
                          ↓
                  ┌───────────────────────┐
                  │ 2. Validate against    │  ← already partial
                  │    step.required_      │
                  │    document_types      │
                  └───────┬───────────────┘
                          ↓
                ┌─────────┴─────────┐
                ↓                   ↓
       ┌─────────────────┐ ┌──────────────────┐
       │ STRUCTURED PATH │ │ UNSTRUCTURED PATH│
       │ (CSV/XLSX/JSON) │ │ (PDF/DOCX/IMG)   │
       └────────┬────────┘ └────────┬─────────┘
                ↓                   ↓
       ┌─────────────────┐ ┌──────────────────┐
       │ pandas/polars   │ │ Stage 6 extract  │
       │ parse → typed   │ │ → blocks[]       │  ← NEW (this commit)
       │ DataFrame       │ │ (title/text/table│
       │                 │ │  /header/footer) │
       └────────┬────────┘ └────────┬─────────┘
                │                   ↓
                │          ┌──────────────────┐
                │          │ Header/footer    │  ← NEW (this commit)
                │          │ auto-strip       │
                │          └────────┬─────────┘
                │                   ↓
                │          ┌──────────────────┐
                │          │ DocSage Schema   │
                │          │ Discovery (LLM)  │
                │          └────────┬─────────┘
                │                   ↓
                │          ┌──────────────────┐
                │          │ DocSage          │
                │          │ Structured       │
                │          │ Extraction (LLM) │
                │          └────────┬─────────┘
                └─────────┬─────────┘
                          ↓ CONVERGE
                ┌───────────────────────┐
                │ Stage 3 cleaning      │
                │ (universal + domain + │
                │  AI-detected)         │
                └───────┬───────────────┘
                        ↓
                ┌───────────────────────┐
                │ Stage 4 quality scorecard│
                │ 7-dim weighted (mig 065)│
                └───────┬───────────────┘
                        ↓
                ┌───────────────────────┐
                │ Silver per-domain     │
                │ tables (mig 051)      │
                └───────┬───────────────┘
                        ↓
                ┌───────────────────────┐
                │ Gold views (mig 052)  │
                │ — Gold-from-Silver-only│
                └───────┬───────────────┘
                        ↓
              ┌──────── SQL-FIRST ─────────┐
              │                             │
              ↓                             ↓
   ┌────────────────────┐         ┌─────────────────┐
   │ KPI engine         │         │ RAG fallback    │
   │ deterministic SQL  │ default │ (only if SQL    │
   │ (ms latency, 100%) │         │  can't answer)  │
   └────────────────────┘         └─────────────────┘
```

## Detection layer (this commit)

Mime + magic bytes + filename extension:

```python
def detect_document_type(*, content: bytes, mime_type: str, filename: str) -> DocumentType:
    """Returns one of:
      STRUCTURED_CSV / STRUCTURED_XLSX / STRUCTURED_JSON / STRUCTURED_TSV
      UNSTRUCTURED_PDF / UNSTRUCTURED_DOCX / UNSTRUCTURED_TXT
      IMAGE_RASTER / IMAGE_VECTOR
      UNKNOWN

    Magic bytes win when mime + filename disagree (browsers often send
    application/octet-stream for Excel uploads from VN office workflows).
    """
```

### Magic byte signatures used

| Type | Bytes (hex) | Confidence |
|---|---|---|
| PDF | `25 50 44 46` (`%PDF`) | High |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | High |
| JPEG | `FF D8 FF` | High |
| ZIP-based (XLSX/DOCX/PPTX) | `50 4B 03 04` | Medium (need inner content check) |
| TIFF | `49 49 2A 00` / `4D 4D 00 2A` | High |
| CSV | text + commas at ≥3 line breaks | Heuristic only |

Inner content for ZIP-based: peek at central directory for `xl/` (Excel), `word/` (DOCX), `ppt/` (PPTX).

## Workflow integration

Each `workflow_node` of type `step` (mig 053) declares:
- `required_document_types` (string[]) — whitelist for the step
- `expected_mapping_template_id` — DocSage hint when path is unstructured

Upload validation order:
1. Detect type from bytes (above)
2. Lookup workflow step by `X-Workflow-Step-ID`
3. If `step.required_document_types` is non-empty AND detected type NOT in whitelist → 400 `USR-ERR-DOC-TYPE-MISMATCH`
4. Bronze insert (raw bytes; SHA-256; dedup K-8)
5. Branch flow: structured → parse; unstructured → extract → DocSage

## What this commit ships

| File | Purpose |
|---|---|
| `silver/document_type.py` (NEW) | `detect_document_type(content, mime, filename)` + `DocumentType` enum + magic byte registry |
| `silver/blocks.py` (NEW) | `Block` dataclass with `type` enum (`text`/`title`/`list`/`table`/`header`/`footer`/`page_number`/`image_ref`/`caption`); helper `text_from_blocks(blocks)` reconstructs reading-order string |
| `silver/header_footer_strip.py` (NEW) | `strip_repeating_lines(pages_text, min_repeats=3)` heuristic |
| `silver/docsage_extract.py` (UPDATED) | Extended `ExtractResult` with optional `blocks: list[Block]` field (backwards-compat — old callers ignore); header/footer strip integrated into PDF path |
| tests for above | 8-section template; pure Python, no DB / no LLM |

NO changes to:
- Bronze append-only (K-2)
- Silver schemas (mig 051) — same destination tables
- DocSage Schema Discovery / Structured Extraction — they accept richer input but old `text` field still works
- Workflow node catalog (mig 068) — `classify_document` AI node deferred Phase 2.5

## What ships Phase 2.5 (sign-off pending)

| Pattern | Effort |
|---|---|
| 3. `pdfplumber` table extraction → markdown | 2 dev-days |
| 4. Multi-column reading-order normalization | 1.5 dev-days |
| 5. Bbox citation enrichment | 1 dev-day (BE) + FE work (paused) |
| `classify_document` AI node | 0.5 dev-day |
| `extract_clauses` AI node (contracts) | 1 dev-day |

## Anti-patterns explicitly refused

1. **RAG-first** for questions that have SQL aggregates. "Doanh thu tháng 5?" goes to `silver_orders` SUM, not vector search.
2. **One pipeline for both** — structured data does NOT need block extraction. CSVs already have columns.
3. **Bypass Silver** — upload PDF → embed → answer. Loses citation traceability + makes every question an LLM call.
4. **Bypass workflow validation** — uploads outside a workflow step skip `required_document_types` whitelist. We always require either a step ID or an explicit "ad-hoc" flag.
5. **Wrap MinerU vendor lib** — see `MINERU_PATTERN_ANALYSIS.md`; native borrow only.
