# P15-S11 DocSage Implementation Plan

> **Created:** 2026-05-17 (after Stage 4 + Stage 6 + Hướng A ship)
> **Sprint:** P15-S11 Tuần 9 (RAG addendum batch)
> **Companion docs:** [ADR-0019](../adr/0019-vectorless-tree-retrieval-and-structured-sql-rag.md) · [`RAG_ADDENDUM_2026_05.md`](../strategic/RAG_ADDENDUM_2026_05.md) · [`RAG_VECTORLESS_AND_STRUCTURED.md`](../specs/RAG_VECTORLESS_AND_STRUCTURED.md) §4
> **Stub today:** `services/ai-orchestrator/reasoning/rag/engines/docsage_stub.py` — raises `NotImplementedError`; RAG router catches and falls back to pgvector.
> **Unblocks:** Stage 6 unstructured docs (commit `8494608`) — DocSage is what turns the `unstructured_pending` placeholder into actual queryable content.
> **Estimate:** 6 dev-days net. Ships as 5 D-pieces over Tuần 9-10.

This is the engineering plan that converts the spec into ship-able commits. It does NOT redo the strategy in ADR-0019 — read that for the "why DocSage at all". Read this for the "what files, what migrations, what tests".

---

## 1. Goal in one paragraph

When a manager asks a multi-entity cross-document question — *"So sánh doanh thu 5 chi nhánh quý vừa rồi"*, *"Khách nào có ≥3 đơn shop A và đã hủy ≥1 đơn shop B?"*, *"Top 10 hợp đồng vendor có rủi ro thanh toán cao nhất"* — the RAG router picks DocSage (not pgvector, not PageIndex) and DocSage walks: (1) discover the minimal joinable schema for the question; (2) extract entity rows from each candidate document into that schema; (3) compose a SQL query, execute against an ephemeral Postgres CTE, and return the rendered answer with citations to the source rows. End-to-end accuracy target ≥80% on a 50-entity test set (paper's 89.2% is the ceiling).

---

## 2. What is already in place

Implementation can **assume** the following are done:

| Surface | State | Where |
|---|---|---|
| RAG router 3-engine dispatch | ✅ shipped P15-S10 D6 (commit `5d36fea`) | `services/ai-orchestrator/reasoning/rag/router.py` |
| `RAGEngine` base ABC + `RAGQuery` / `RAGAnswer` / `Citation` shapes | ✅ shipped | `…/rag/engines/base.py` |
| DocSage stub registered + router whitelist + fallback | ✅ shipped | `…/rag/engines/docsage_stub.py` |
| HTTP endpoint `POST /rag/answer` | ✅ shipped P15-S10 D6 wired (commit `5d36fea`) | `services/ai-orchestrator/routers/rag.py` |
| LLM Gateway with output_schema JSON validation (Issue #3) | ✅ shipped Phase 2 B3 | `services/llm-gateway/main.py` |
| BGE-M3 embedding via Ollama (not used by DocSage but available) | ✅ shipped | `infrastructure/ollama/` |
| Stage 6 unstructured placeholder — PDF/DOCX accepted as `unstructured_pending` | ✅ shipped today (`8494608`) | `services/data-pipeline/data_plane/bronze/ingestor.py` |
| `corpus_filter` parameter on RAGQuery | ✅ shipped | `…/rag/engines/base.py` |
| Per-tenant LLM token budget enforcement | ✅ shipped P15-S10 | `services/llm-gateway/main.py` (budget middleware) |

This means D1-D5 below are pure additions. No refactor needed in shipped code.

---

## 3. D-piece breakdown

### D1 — Migration 066: DocSage cache tables (½ day)

Per spec §4.4. Two tables under RLS (K-1) + GRANT to `kaori_app`.

```sql
-- infrastructure/postgres/migrations/066_docsage_cache.sql
BEGIN;

CREATE TABLE IF NOT EXISTS docsage_schemas (
    schema_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    corpus_hash      TEXT         NOT NULL,
    question_class   TEXT         NOT NULL,
    schema_json      JSONB        NOT NULL,
    llm_model        TEXT         NOT NULL,    -- K-20: model+version pinned per row
    llm_version      TEXT         NOT NULL,
    token_count      INT          NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, corpus_hash, question_class)
);

CREATE TABLE IF NOT EXISTS docsage_extractions (
    extraction_id    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    schema_id        UUID         NOT NULL REFERENCES docsage_schemas(schema_id) ON DELETE CASCADE,
    doc_id           TEXT         NOT NULL,    -- bronze_files.file_id::text usually
    rows_json        JSONB        NOT NULL,    -- list[Row] per spec §4.3
    extraction_status VARCHAR(20) NOT NULL DEFAULT 'ok'
        CHECK (extraction_status IN ('ok', 'partial', 'failed')),
    error_message    TEXT,
    token_count      INT          NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, schema_id, doc_id)
);

CREATE INDEX idx_docsage_schemas_lookup
    ON docsage_schemas (enterprise_id, corpus_hash, question_class);
CREATE INDEX idx_docsage_extractions_lookup
    ON docsage_extractions (enterprise_id, schema_id);

ALTER TABLE docsage_schemas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE docsage_extractions  ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_docsage_schemas ON docsage_schemas
    USING (enterprise_id = (current_setting('app.enterprise_id', true))::uuid);
CREATE POLICY tenant_docsage_extractions ON docsage_extractions
    USING (enterprise_id = (current_setting('app.enterprise_id', true))::uuid);

GRANT SELECT, INSERT ON docsage_schemas, docsage_extractions TO kaori_app;

COMMIT;
```

Companion shape test `scripts/test_migrations_066_shape.py` per Build Week pattern.

**Drift artefacts:** mig 066 → schema_snapshot refresh (per `feedback_endpoint_addition_drift_checks.md`).

### D2 — Stage 6 text extraction module (1 day)

Stage 6 currently registers PDF/DOCX/PNG/JPG as `unstructured_pending` with no content. D2 extracts plain text so DocSage has a string to work on.

Location: `services/data-pipeline/data_plane/silver/docsage_extract.py` (sits in Silver tier per Medallion separation per `feedback_medallion_separation.md` — extraction is a Silver-tier transformation, not a Bronze augmentation).

Library choice per format:

| Format | Lib | Status |
|---|---|---|
| PDF text-layer | `pypdf==5.0.1` (pure-Python, MIT) | add to data-pipeline requirements.txt |
| PDF scanned (image-only) | defer to OCR — Phase 2 unblock once Qwen2-VL via llm-gateway lands | skip if `pdf.is_scanned()` |
| DOCX | `python-docx==1.1.2` | add |
| PNG/JPG | defer to Phase 2 (OCR) | mark as `extraction_status='unsupported_today'` in bronze_files.metadata |

Function shape:

```python
def extract_text(
    *, file_path: Path, mime_type: str
) -> ExtractResult:
    """Pure stateless. Returns text + per-page boundaries for citation
    (PageIndex needs pages; DocSage uses pages as doc segment IDs)."""
```

On extraction:
- Update `bronze_files.metadata.docsage_text` (JSONB) with extracted plain text + per-page offsets.
- Update `pipeline_runs.status` from `unstructured_pending` → `silver_complete` (the existing happy path for structured uploads — DocSage extraction IS the Silver step for unstructured uploads).
- Audit log row: `decision_audit_log` event `docsage.extract.complete` with token estimate.

**Side_effect_class:** `write_idempotent` (re-extracting same file = same text — SHA + lib version pinned in cache key).

**Tests:** 5 unit tests (text-layer PDF / DOCX / empty / scanned-fallback / OCR-deferred).

### D3 — Schema Discovery module (1 day)

Per spec §4.3. LLM call with output_schema validation.

Location: `services/ai-orchestrator/reasoning/rag/engines/docsage/schema_discovery.py`.

```python
class SchemaDefinition(BaseModel):
    """Output schema for the Schema Discovery LLM call. Issue #3
    enforces this; LLM gets 1 repair pass on validation fail per
    K-20 + REL-002 spirit."""
    tables: list[Table]
    join_keys: list[JoinKey]
    question_class: str   # "comparison" / "aggregation" / "relationship" / "ranking"

class Table(BaseModel):
    name: str           # snake_case, ≤32 chars
    columns: list[Column]

class Column(BaseModel):
    name: str
    sql_type: str       # SQL-92 subset: TEXT, INTEGER, NUMERIC, DATE, BOOLEAN
    nullable: bool = True
    role: str           # "key" | "attribute" | "measure" | "fk"
    fk_target: str | None = None   # "table.column" when role='fk'
```

**Prompt template** (`docsage_prompts.py`):

```
SYSTEM: You are a database schema architect. Given a business question
in Vietnamese (with English allowed for technical terms) and a corpus
sample (3 documents), propose the MINIMAL joinable schema that would
answer the question via SQL. Prefer narrow tables (3-8 columns) over
wide ones. Every measure column should have a unit hint in the name
(revenue_vnd, count_orders, days_overdue).

USER: Question: {question}
Corpus sample (3 docs):
{corpus_excerpt_max_2000_chars}

Output strictly the JSON schema below.
```

Caching key: `(enterprise_id, sha256(corpus[:5].titles), question_class)` →  `docsage_schemas` row.

**Tests:** 6 (3 question classes × output_schema valid; 1 retry-on-invalid; 1 cache-hit; 1 K-19 trace span attr).

### D4 — Structured Extraction module (1½ days)

Per spec §4.3 step 2. Per-doc LLM call that returns rows matching the schema.

Location: `services/ai-orchestrator/reasoning/rag/engines/docsage/extraction.py`.

```python
class Row(BaseModel):
    table: str
    values: dict[str, Any]
    source_segment: tuple[int, int] | None   # (page_from, page_to) for citation
```

Cost-control rules (D4-specific, on top of per-tenant budget):
1. Per-doc extraction LLM call capped at 8K tokens out (Pydantic max_length).
2. If a doc would exceed 8K, split into 4 segments and merge results — track `partial` status on extraction row.
3. Cache deterministically keyed on `(schema_id, sha256(doc_text))`; second call same doc = cache hit, zero LLM cost.
4. Failed extractions store `extraction_status='failed'` + `error_message` — caller may proceed with partial corpus.

**Prompt template:**

```
SYSTEM: You are a data extraction agent. Given a JSON schema and a
source document, output rows for the schema. Cite the page range
(source_segment) for every row. Skip rows you cannot extract with
confidence ≥ 80% — better partial than wrong.

USER: Schema:
{schema_json}

Document (pages {page_from}-{page_to}):
{doc_text}

Output strictly: { "rows": [Row, ...] }
```

PII redaction (K-5) is applied to doc_text BEFORE prompt assembly when `consent_external=true` and routing chooses an external vendor — Qwen local default path skips redaction (data stays inside).

**Tests:** 8 (happy path / cap exceeded / split-merge / cache hit / extraction failure / PII-redacted external call / Pydantic validation / K-19 span).

### D5 — SQL Reasoning + DocSageEngine assembly (1½ days)

Per spec §4.3 step 3. Compose SQL from `(schema, rows_by_doc, question)`, execute on Postgres temp tables (CREATE TEMP TABLE … inside transaction; auto-dropped at txn end), format result with LLM.

Location: `services/ai-orchestrator/reasoning/rag/engines/docsage/sql_reasoning.py` + glue in `…/engines/docsage/__init__.py`.

Key design:
- Use Postgres **TEMPORARY** tables, not real CREATE TABLE. Temp tables are session-scoped + auto-dropped at txn commit → no schema drift, no cleanup task. RLS does not apply (temp tables are caller-private).
- LLM emits SQL, we **parse + reject anything that touches non-temp tables** (whitelist regex on `FROM` / `JOIN` clauses). Defence in depth: even if LLM tries to read `enterprise_users`, the connection runs as `kaori_app` (no SELECT on non-tenant rows) and the SET LOCAL `app.enterprise_id` is unset for this temp-only path.
- Result rendering: LLM rewrites the rowset as Vietnamese prose with per-row citations to `source_segment` from D4.

**Prompt templates:**

```
SYSTEM (SQL composer): Compose a single SQL query against the temp
schema below. Use only standard SQL-92 features. No DDL. Return JSON:
  { "sql": "<query>", "explanation_vi": "<≤2 sentence>" }

SYSTEM (result formatter): Given rows + question, render a manager-
friendly Vietnamese answer with inline citations [page X-Y].
```

DocSageEngine.answer() flow:
1. Call Schema Discovery (D3) → SchemaDefinition + cache check.
2. For each doc in corpus_filter: call Structured Extraction (D4) → rows + cache check.
3. CREATE TEMP TABLEs + INSERT rows (transactional).
4. Call SQL Reasoning (D5) → SQL + execute → rowset.
5. Format rowset → Vietnamese answer + citations.
6. Return `RAGAnswer(engine_used='docsage', confidence=…, citations=[…])`.

**Tests:** 10 (incl. acceptance §4.6: 50-entity fixture from `data/vinfast/` VinFast workflow_dataset.json — comparison question against the multi-branch sample).

### D6 — Update router heuristic + replace stub (½ day)

Switch `services/ai-orchestrator/reasoning/rag/engines/__init__.py` from `DocSageStubEngine` to the real `DocSageEngine`. Tighten the router decision tree per spec §2.2 — add keyword detection for comparison/aggregation/relationship triggers (`so sánh`, `top`, `tổng`, `ít nhất`, `nhiều nhất`, etc.).

Add Prometheus counter labels `engine='docsage'` already present from D6 P15-S10 (no code change there).

**Tests:** 4 (router picks DocSage on comparison query / fallback on engine error / cost guard rejects oversized query / telemetry label correct).

---

## 4. Day-by-day order

| Day | Deliverable | Cumulative tests added |
|---|---|---|
| 1 | D1 (½d) + D2 (½d) start | +5 (extract) |
| 2 | D2 finish | +5 |
| 3 | D3 | +6 |
| 4 | D4 start | +4 |
| 5 | D4 finish | +8 |
| 6 | D5 start | +5 |
| 7 | D5 finish + D6 | +10 + 4 |

Net: ~7 dev-days. Buffer 1 day → 8 days total. Spec said "P15-S11 DocSage 3-module pipeline" — em scope it tighter at 6 net + 2 polish.

---

## 5. Compliance check

| Invariant | How DocSage honours it |
|---|---|
| K-1 RLS | All cache reads/writes via `acquire_for_tenant`. Temp tables exempt (session-private). |
| K-3 LLM via gateway | Schema / Extraction / SQL / Format → all four calls go through `services/llm-gateway/`. No direct SDK. |
| K-4 Qwen default | Default routing per ADR-0015 — Qwen for all 4 calls. External vendor only with `consent_external` + per-call `prefer_external`. |
| K-5 PII redaction | `extraction.py` calls `shared.pii.redact()` before any external-vendor doc submission. |
| K-6 Decision audit | Every DocSage call writes a `decision_audit_log` row with engine, schema_id, latency, token count. |
| K-9 NUMERIC for money | Schema Discovery prompt instructs `NUMERIC` not FLOAT for money/rates. Validator enforces. |
| K-13 Idempotency | Schema + Extraction caches ARE the idempotency layer for DocSage. |
| K-17 side_effect_class | Stage 6 extraction = `write_idempotent`. SQL Reasoning = `pure` (TEMP table only). |
| K-19 OTel span tenant_id | All 4 modules wrap LLM calls in named span with `tenant_id` attr. |
| K-20 LLM version pin | Each cache row records `(llm_model, llm_version)`. Cache miss when model changes. |

---

## 6. Risks + open questions

### Risks

1. **LLM token cost explosion on first cache-miss** — a 50-doc corpus × 8K tokens per extraction = 400K input tokens. At Qwen local ≈ 30 sec/doc on the laptop. Mitigation: corpus_filter MUST be tight (≤20 docs per question Phase 1.5). Hard cap in DocSageEngine; reject with friendly error otherwise.
2. **Hallucinated SQL** — LLM emits `SELECT * FROM bronze_files` instead of temp table. Mitigation: SQL parser whitelist + connection role isolated (kaori_app, no SET LOCAL enterprise_id on the temp-table-only connection).
3. **Schema instability across question rephrasing** — "compare branches by revenue" vs "branch revenue ranking" might produce different schemas. Mitigation: `question_class` is one of 4 enum values; cache key uses the class, not raw question.
4. **Vietnamese tokenization on Qwen2.5** — long Vietnamese paragraphs (legal contracts) might blow the input window. Mitigation: per-doc chunking at 2K-char boundaries; D4 already handles the partial/merge case.

### Open questions (decide pre-D1)

1. **Temp table or CTE?** CTE is more reproducible but harder to debug; temp table allows `EXPLAIN ANALYZE`. Default: TEMP TABLE for dev observability; switch to CTE if pg_temp namespace contention shows up. **Default: TEMP TABLE.**
2. **Per-doc extraction parallelism?** P15-S11 ship sequential (simpler); Phase 2 add `asyncio.gather` with semaphore. Anh chốt P15-S11 = sequential.
3. **Cost budget per query?** Per-tenant existing budget covers it; DocSage-specific budget needed? Default: rely on tenant budget; add `kaori_rag_docsage_cost_vnd` metric to detect runaway.
4. **Acceptance fixture source?** VinFast workflow_dataset.json has 50+ branches × orders — perfect for comparison question test. Use it.

---

## 7. Test acceptance (per spec §4.6 + benchmark)

Hard pass requirements before merging:
- All 5 module test files green locally.
- ai-orchestrator pytest count ≥ current 917 + 37 (5+6+8+10+4+4) = 954.
- 50-entity comparison fixture: DocSage answer matches manual-computed truth on ≥ 4 of 5 questions (80% accuracy floor).
- Cache hit rate test: 2nd run of same question on same corpus = 0 LLM calls (assertion on mock).
- K-19 span attr test for each of the 4 LLM calls.
- Drift artefacts refreshed (schema_snapshot for mig 066; OpenAPI no change — endpoint shape unchanged; FE types no change).

---

## 8. What gets unblocked when D6 lands

- Stage 6 unstructured docs (shipped today, commit `8494608`) — placeholder becomes queryable content.
- BACKLOG_V4 `P2-M210-006` (data citation) — DocSage cites SQL + tables.
- BACKLOG_V4 `P2-M216-002` (top-3 factors / explainability) — DocSage answer IS the explanation (SQL + rows).
- BACKLOG_V4 `P2-M27-006` (workflow recommendation) — DocSage cross-doc analysis on process logs.
- BACKLOG_V4 `P2-M28-*` advanced multi-tier analysis — DocSage path on the wizard.

---

## 9. Files this plan creates / touches

```
infrastructure/postgres/migrations/
  066_docsage_cache.sql                                                  NEW

scripts/
  test_migrations_066_shape.py                                           NEW

services/data-pipeline/
  data_plane/silver/docsage_extract.py                                   NEW
  routers/upload.py                                                      MODIFIED
  tests/test_docsage_extract.py                                          NEW
  requirements.txt                                                       MODIFIED (+pypdf, +python-docx)

services/ai-orchestrator/
  reasoning/rag/engines/docsage/__init__.py                              NEW
  reasoning/rag/engines/docsage/schema_discovery.py                      NEW
  reasoning/rag/engines/docsage/extraction.py                            NEW
  reasoning/rag/engines/docsage/sql_reasoning.py                         NEW
  reasoning/rag/engines/docsage/prompts.py                               NEW
  reasoning/rag/engines/docsage/types.py                                 NEW (Pydantic shapes)
  reasoning/rag/engines/__init__.py                                      MODIFIED (drop stub)
  reasoning/rag/router.py                                                MODIFIED (keyword heuristic)
  tests/test_docsage_schema_discovery.py                                 NEW
  tests/test_docsage_extraction.py                                       NEW
  tests/test_docsage_sql_reasoning.py                                    NEW
  tests/test_docsage_engine_integration.py                               NEW
  tests/test_rag_router_docsage_path.py                                  NEW
  tests/fixtures/docsage_50_branches.json                                NEW (from data/vinfast/)
```

Net 18 new files + 4 modified.

---

## 10. Resume signal

When picking this up:
1. Read `JUNE_2026_RESUME_CHECKLIST.md` first — CI budget might still be exhausted; do not push without local sweep.
2. Apply mig 066 to local Postgres (per drift artefact recipe in [[feedback_endpoint_addition_drift_checks]]).
3. Start D1 (½ day). D2 begins when D1 commits.
4. Each D-piece commits independently — small reviewable PRs.

When D6 lands + green CI: tag `v4.5-docsage-complete` and mark `RAG-DOCSAGE-001/002/003` ✅ in `docs/BACKLOG_V4.md`.

---

*Plan author: Kaori (em). Sign-off: anh.*
