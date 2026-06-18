# RAG Engine Spec — Vectorless Tree (PageIndex) + Structured SQL (DocSage)

> **Status:** spec draft (Phase 1.5 prep)
> **Sprint owners:** P15-S10 (PageIndex adapter), P15-S11 (DocSage pipeline)
> **ADR:** [ADR-0019](../adr/0019-vectorless-tree-retrieval-and-structured-sql-rag.md)
> **Strategic addendum:** [`docs/strategic/RAG_ADDENDUM_2026_05.md`](../strategic/RAG_ADDENDUM_2026_05.md)

This spec captures the contract surface for two new RAG engines that will land Phase 1.5 alongside the existing pgvector default. Phase 1 v4 already has the package skeleton at `services/ai-orchestrator/reasoning/rag/` (P1-S5) — this spec defines what code populates that skeleton when P15-S10/S11 ship.

The companion strategic addendum is the narrative; this spec is the engineering contract.

---

## 1. Engine taxonomy

The Reasoning Layer routes one of three engines per query:

| Engine | Best for | Latency | Cost/query (est) | Phase |
|---|---|---|---|---|
| **pgvector** (default) | Short chat / single-entity Q&A / loose-keyword retrieval | <100 ms | ~$0.0001 | P1-S5 contract; runtime P15-S9 |
| **PageIndex** (vectorless tree) | Deep-dive into a known document (PDF/MD); contracts; financial reports; SOPs | 200-800 ms (after tree built) | ~$0.001 | P15-S10 |
| **DocSage** (structured SQL) | Multi-entity comparison / aggregation / relational ("compare 5 branches", "top revenue per department") | 1-3 s (Schema + Extract + SQL) | ~$0.005-0.02 | P15-S11 |

Engine selection is a **router decision**, not a per-tenant default. The router lives at `services/ai-orchestrator/reasoning/rag/router.py` (P15-S10 ships).

---

## 2. RAG Router contract

### 2.1 Class shape

```python
# services/ai-orchestrator/reasoning/rag/router.py (P15-S10)
class RAGRouter:
    """Selects the best RAG engine per query + orchestrates the call.

    Phase 1.5 default heuristic; Phase 2 swaps to a small classifier
    LLM call (Qwen-7B) for routing decisions.
    """
    def __init__(
        self,
        *,
        pgvector: PgVectorEngine,
        pageindex: PageIndexEngine | None = None,
        docsage: DocSageEngine | None = None,
        llm_router: LLMRouter,
    ) -> None: ...

    async def answer(
        self,
        *,
        tenant_id: UUID,
        question: str,
        corpus_filter: CorpusFilter,
        consent_external: bool = False,
        prefer_external: bool = False,
    ) -> RAGAnswer:
        """Pick engine → run engine → return answer with citations."""
```

### 2.2 Routing decision tree (Phase 1.5 heuristic)

```
question:
├── len(question) ≤ 200 AND single_entity_signal?
│       → pgvector
├── mentions specific document name / section?
│       → PageIndex
├── has comparison/aggregation/relationship keywords AND ≥2 entities?
│       → DocSage
├── default fallback
│       → pgvector
```

Single-entity signal: NER pass over question (Qwen local) returns ≤1 named entity that maps to a domain object (customer, product, branch). Cheap heuristic Phase 1.5; tighten Phase 2.

### 2.3 RAGAnswer envelope

```python
@dataclass(frozen=True)
class RAGAnswer:
    text: str
    engine_used: str        # "pgvector" / "pageindex" / "docsage"
    confidence: Decimal     # NUMERIC(5,4)
    citations: list[Citation]
    latency_ms: int
    cost_estimate_vnd: Decimal | None  # NOV-CST-009 cost track
```

```python
@dataclass(frozen=True)
class Citation:
    """One source attribution. Engine-specific shape:

    - pgvector: doc_id + chunk_id + score
    - pageindex: doc_id + node_id + page_range
    - docsage: corpus_hash + sql_query + table_names
    """
    engine: str
    doc_id: str
    locator: dict[str, Any]   # engine-specific shape
    score: Decimal | None
```

---

## 3. PageIndex engine spec (P15-S10)

### 3.1 Vendoring strategy

Wrap upstream `github.com/VectifyAI/PageIndex` (MIT) as a vendored Python dependency:

- Add `pageindex>=X.Y.Z` to `services/ai-orchestrator/requirements.txt` if PyPI publish.
- Otherwise: vendor source tree under `services/ai-orchestrator/reasoning/rag/_pageindex_vendor/` + apply patches (LICENSE preserved, attribution README pointing to upstream).
- Decision at P15-S10 kickoff after checking PyPI availability.

### 3.2 Class shape

```python
# services/ai-orchestrator/reasoning/rag/pageindex.py (P15-S10)
class PageIndexEngine:
    def __init__(
        self,
        *,
        llm_router: LLMRouter,
        tree_store: PageIndexTreeStore,  # Postgres-backed JSONB
    ) -> None: ...

    async def build_tree(
        self,
        *,
        tenant_id: UUID,
        doc_id: str,
        document_bytes: bytes,
        document_format: str,  # "pdf" / "markdown"
    ) -> PageIndexTree:
        """Async tree-build (called from upload pipeline). Stores result
        in pageindex_trees table for reuse."""

    async def retrieve(
        self,
        *,
        tenant_id: UUID,
        question: str,
        corpus_filter: CorpusFilter,
    ) -> RAGAnswer:
        """Load tenant's tree(s), run LLM-traversal to pick relevant
        nodes, synthesise answer with citations including page_range."""
```

### 3.3 Persistence

Migration `pageindex_trees` (P15-S10):

```sql
CREATE TABLE pageindex_trees (
    tree_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID            NOT NULL,
    doc_id         TEXT            NOT NULL,
    tree_json      JSONB           NOT NULL,
    built_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ,    -- optional TTL for ephemeral docs
    UNIQUE (tenant_id, doc_id)
);
ALTER TABLE pageindex_trees ENABLE ROW LEVEL SECURITY;
-- RLS policy on tenant_id (K-1)
```

### 3.4 Caller contract

Upload pipeline (`data-pipeline/routers/upload.py`) on PDF / Markdown success → publish `kaori.pipeline.events {type: 'doc.uploaded', doc_id, format}` → ai-orchestrator consumer triggers `PageIndexEngine.build_tree` async.

Insight panel (P2-M210-014 RAG) → call `RAGRouter.answer()` → returns RAGAnswer with citations including PDF page numbers for "click → jump to PDF page" UX.

### 3.5 Tests P15-S10

- Tree-build idempotent (same doc_id twice → same tree).
- Retrieve returns citations pointing to existing nodes.
- Empty corpus returns RAGAnswer with `confidence=0` + helpful note (not raising).
- Tenant isolation: tenant A's tree never returned for tenant B query.

---

## 4. DocSage engine spec (P15-S11)

### 4.1 Independent implementation

DocSage paper (HKUST, arXiv 2603.11798) describes 3 modules sufficient to re-implement without upstream code (LLM + standard SQL — no specialised models). Phase 1.5 P15-S11 implements directly. Watch HKUSTDial GitHub for reference impl; if released under permissive license, em swap to upstream.

### 4.2 Class shape

```python
# services/ai-orchestrator/reasoning/rag/docsage.py (P15-S11)
class DocSageEngine:
    def __init__(
        self,
        *,
        llm_router: LLMRouter,
        schema_store: DocSageSchemaStore,
        extraction_store: DocSageExtractionStore,
    ) -> None: ...

    async def answer(
        self,
        *,
        tenant_id: UUID,
        question: str,
        corpus_filter: CorpusFilter,
    ) -> RAGAnswer:
        """3-step pipeline:
            1. Schema Discovery (LLM call → minimal joinable schema for
               this question; cached in docsage_schemas table)
            2. Structured Extraction (LLM call per doc → SQL INSERT into
               temp tables; cached in docsage_extractions table)
            3. SQL Reasoning (compose SQL JOIN → execute on Postgres
               temp schema → format result with LLM)
        """
```

### 4.3 Three-module split

```python
class SchemaDiscovery:
    """Step 1 — LLM-derived minimal joinable schema for the question.

    Reuses Issue #3 output_schema validation: the discovery LLM call
    returns JSON matching SchemaDefinition Pydantic model.
    """
    async def discover(
        self, question: str, corpus_sample: list[Document],
    ) -> SchemaDefinition: ...

class StructuredExtraction:
    """Step 2 — LLM extracts entities + relationships per document
    into provisional rows for the schema. Error-aware correction
    pass per DocSage paper.
    """
    async def extract(
        self, schema: SchemaDefinition, doc: Document,
    ) -> list[Row]: ...

class SQLReasoning:
    """Step 3 — composes SQL query against the populated tables,
    executes on Postgres temp/CTE, formats result.
    """
    async def query(
        self, schema: SchemaDefinition, question: str,
        rows_by_doc: dict[str, list[Row]],
    ) -> SQLAnswer: ...
```

### 4.4 Persistence + cache

Migrations P15-S11:

```sql
-- Cached schema per (corpus_hash, question_class)
CREATE TABLE docsage_schemas (
    schema_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID            NOT NULL,
    corpus_hash      TEXT            NOT NULL,
    question_class   TEXT            NOT NULL,
    schema_json      JSONB           NOT NULL,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, corpus_hash, question_class)
);

-- Cached extraction per (schema, doc) - extraction is deterministic for the same doc + schema
CREATE TABLE docsage_extractions (
    extraction_id    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID            NOT NULL,
    schema_id        UUID            NOT NULL REFERENCES docsage_schemas(schema_id),
    doc_id           TEXT            NOT NULL,
    rows_json        JSONB           NOT NULL,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, schema_id, doc_id)
);
-- Both under RLS (K-1) + grants to kaori_app
```

### 4.5 Cost guard rails

Each query potentially triggers Schema + N×Extraction + 1×SQL Reasoning LLM calls. Without caching, cost explodes for 100-doc corpora.

- Schema cached per (corpus_hash, question_class) — same question class on same corpus = cache hit.
- Extraction cached per (schema, doc) — extraction is deterministic.
- SQL Reasoning step is cheap (LLM produces SQL string + interprets result; both small prompts).

Per-tenant token budget enforcement (P15-S10) blocks runaway DocSage queries.

### 4.6 Tests P15-S11

- Schema Discovery returns Pydantic-valid SchemaDefinition.
- Extraction populates rows under tenant scope (RLS).
- SQL Reasoning produces deterministic answer for the same input.
- 100-entity test (mirroring DocSage paper benchmark) — accuracy threshold 80%+ on a sample.
- Caching effective: 2nd call same (corpus, question) hits cache.

---

## 5. Routing telemetry

P15-S10 adds Prometheus counters (extends OBS-008):

```
kaori_rag_engine_calls_total{engine, status, tenant_id}
kaori_rag_engine_latency_ms{engine, tenant_id}    # histogram
kaori_rag_engine_cost_vnd{engine, tenant_id}      # NOV input
```

Grafana dashboard "RAG Router Distribution" — verifies Phase 1.5 routing heuristic matches expectations. Adjust thresholds per actual traffic.

---

## 6. Migration path from pgvector-only

Phase 1 v4 + Phase 1.5 P15-S9: pgvector remains default for all queries.

Phase 1.5 P15-S10:
1. Ship PageIndex engine + tree builder.
2. Add `tenant_settings.rag_engines: jsonb` (default `["pgvector"]`).
3. Tenants opt in via UI: `/p2/settings/ai → Engines: ☑ pgvector ☑ PageIndex`.
4. Router uses opted-in engines only; falls back to pgvector when none.

Phase 1.5 P15-S11:
1. Ship DocSage engine.
2. Add `docsage` to allowed values in `tenant_settings.rag_engines`.
3. Default rollout: existing tenants stay pgvector-only; new tenants in onboarding wizard see all 3 enabled.

Phase 2: routing heuristic → small classifier LLM (Qwen-7B fine-tuned) for better engine selection.

---

## 7. Out of scope

- **Replacing pgvector.** It stays. P15-S9 still ships pgvector real impl.
- **Replacing Pinecone Phase 1.5+.** Pinecone for cross-tenant analytics + bigger corpus; PageIndex/DocSage for per-tenant docs.
- **Cross-engine fusion** ("ask all 3, ensemble answers"). Phase 2+ if accuracy demands.
- **Frontend UX** for engine choice. P15-S10 ships only the BE toggle in tenant_settings; FE wiring per "frontend paused per anh" rule.

---

## 8. Acceptance criteria

P15-S10 (PageIndex):
- ☐ PageIndexEngine.build_tree completes for 100-page PDF in <60s.
- ☐ PageIndexEngine.retrieve returns RAGAnswer with citations including page_range.
- ☐ Multi-tenant test: tenant A query never returns tenant B's nodes.
- ☐ Empty-corpus + missing-doc paths return graceful RAGAnswer (not raising).
- ☐ Prometheus counters increment per engine call.

P15-S11 (DocSage):
- ☐ Schema Discovery output validates against SchemaDefinition.
- ☐ Extraction cache effective: 2nd call same (schema, doc) hits cache.
- ☐ SQL Reasoning produces deterministic SQL for same schema + question.
- ☐ Sample 50-entity test corpus achieves ≥80% accuracy (vs paper's 89.2% on full benchmark).
- ☐ Per-tenant token budget enforces — runaway queries blocked.

---

## 9. References

- ADR-0019 [vectorless tree retrieval + structured SQL RAG](../adr/0019-vectorless-tree-retrieval-and-structured-sql-rag.md)
- Strategic addendum [`docs/strategic/RAG_ADDENDUM_2026_05.md`](../strategic/RAG_ADDENDUM_2026_05.md)
- [PageIndex (MIT)](https://github.com/VectifyAI/PageIndex)
- [DocSage paper (HKUST, Mar 2026)](https://arxiv.org/abs/2603.11798)
- [HKUSTDial NL2SQL Handbook](https://github.com/HKUSTDial/NL2SQL_Handbook)
- `services/ai-orchestrator/reasoning/rag/` Phase 1 P1-S5 skeleton (target dir for impl)
- `docs/strategic/REASONING_LAYER.md` PART IV (RAG Knowledge Engine, 4-tier source architecture)
- `docs/BACKLOG_V4.md` Phase 1.5 P15-S10/S11 (this spec drives those sprint scopes)
