# ADR-0019 — Vectorless tree retrieval (PageIndex) + structured SQL reasoning (DocSage) for RAG

> **Status:** proposed
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0012 (polyglot persistence) · ADR-0015 (Qwen-first LLM) · `docs/strategic/REASONING_LAYER.md` PART IV (RAG Knowledge Engine) · `docs/specs/RAG_VECTORLESS_AND_STRUCTURED.md`

## Context

v4 Reasoning Layer (P1-S5 shipped) định nghĩa RAG là 4-tier source architecture với pgvector embedding làm Tier 1 retrieval. Phase 1 ship contract surface; Phase 1.5+ wire pgvector + Pinecone alternates.

Hai paper / repo công bố Q1 2026 chỉ ra 2 hạn chế nghiêm trọng của pure-vector RAG mà v4's Phase 1.5 plan sẽ gặp:

1. **Attention dilution với context dài.** GPT-4o + traditional RAG đạt chỉ 35% accuracy khi xử lý >100 entities trong multi-document QA (DocSage paper, MEBench). Long-context window không cứu được — attention bị loãng. Pilot Olist đã thấy: insight panel với nhiều khách hàng = nói lung tung.

2. **"Similarity ≠ relevance" trong professional documents.** PDF báo cáo tài chính, hợp đồng, tài liệu nội bộ doanh nghiệp — vector similarity match keyword không nắm được hierarchy của document (chương → mục → tiểu mục → đoạn). PageIndex (VectifyAI) demo: 98.7% accuracy trên FinanceBench (gấp đôi vector RAG baseline) bằng cách traverse table-of-contents tree thay vì similarity search.

Hai approach mới giải quyết 2 góc khác nhau:

**PageIndex (vectorless tree retrieval) — github.com/VectifyAI/PageIndex (MIT licensed, Python):**
- Build hierarchical Table-of-Contents tree từ PDF/Markdown (no chunking, no vector DB).
- LLM reasoning traverses tree để chọn relevant section dựa trên query intent.
- Output: JSON tree với node titles + page ranges + summaries.
- Tốt cho: "tài liệu nội bộ" use case (P2-M210-012/014/015 — RAG cho insights), tài liệu khách upload PDF, hợp đồng/báo cáo dày.
- Yếu khi: cross-document multi-entity questions (cần JOIN dữ liệu giữa nhiều file).

**DocSage (structured SQL reasoning) — arXiv 2603.11798 (HKUST, Mar 2026):**
- 3 module: Schema Discovery (suy ra schema từ câu hỏi) → Structured Extraction (transform unstructured docs → relational tables) → SQL Reasoning (multi-hop relational query).
- 89.2% accuracy trên MEBench (vs GPT-4o + RAG 62%, +27.2 percentage points).
- 87.9% với >100 entities (vs 41.5%).
- Loong (250K tokens): perfect rate 0.47, gấp đôi mọi baseline.
- Tốt cho: cross-document entity comparison ("So sánh KPI 5 chi nhánh quý vừa rồi"), aggregation ("Tổng doanh thu nhóm khách VIP"), relationship questions ("Khách nào có ≥3 đơn từ shop A và đã hủy ≥1 đơn shop B?").
- Tận dụng SQL JOIN — không hallucinate, không attention dilution.

Hai approach **bổ sung** (không thay thế) cho pgvector. Pilot Vietnamese SME use case sẽ cần cả ba:
- **pgvector** cho insight panel ngắn ("Tóm tắt 5 customer churn ngày qua") — fastest, lowest cost.
- **PageIndex** cho RAG trên tài liệu nội bộ (PDF báo cáo, sổ tay quy trình) — better recall + traceability.
- **DocSage** cho multi-entity BI questions (manager hỏi cross-doc analysis) — far higher accuracy.

## Decision

Chúng ta nâng v4 Reasoning Layer Tier 1 retrieval từ **pgvector-only** lên **3-engine pluggable router**:

```
                  ┌──────────────────────────────────────┐
   query  ───→   │   RAG Router (services/ai-           │
                  │   orchestrator/reasoning/rag/        │
                  │   router.py — Phase 1.5 P15-S10)     │
                  └────┬───────────────┬───────────────┬─┘
                       ▼               ▼               ▼
              ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
              │  pgvector   │ │  PageIndex  │ │  DocSage    │
              │  similarity │ │  tree retr. │ │  schema +   │
              │  (P1-S5     │ │  (vectorless│ │  SQL reas.  │
              │  contract)  │ │  P15-S10)   │ │  (P15-S11)  │
              └─────────────┘ └─────────────┘ └─────────────┘
                       │               │               │
                       ▼               ▼               ▼
              short Q&A on       PDF/doc deep-      multi-entity
              chat history       dive, FinanceBench cross-doc QA
              + light RAG        + contracts        (manager BI)
```

**Routing rules** (Phase 1.5+):
1. Query length ≤ 200 chars + single entity intent → **pgvector** (cheap fast path).
2. Query mentions a specific document title / section / clause → **PageIndex** (tree traversal).
3. Query has comparison / aggregation / relationship keywords + ≥2 entities → **DocSage** (Schema Discovery → SQL).
4. Default fallback: pgvector (lowest latency).

**Phase 1.5 implementation order:**
- **P15-S10**: PageIndex adapter — embed VectifyAI's repo as a vendored dependency or fork; markdown-first impl (PDF Phase 1.5 follow-up). Replaces zero v4-shipped behaviour; opt-in per tenant via `tenant_settings.rag_engines` JSONB flag (default `["pgvector"]`).
- **P15-S11**: DocSage pipeline — Schema Discovery + Structured Extraction + SQL Reasoning. Sit on top of PostgreSQL (DocSage tables Materialised Views or temporary CTE per query — not new DB). Reuse Issue #3 output_schema validation for Schema Discovery LLM call. Reuse `idempotency_records` for cache (same query + corpus = skip extraction).

**Licensing:** PageIndex is MIT — fine to vendor / fork / wrap. DocSage paper not yet have public reference impl as of writing; em monitor HKUSTDial/awesome-data-agents repo. Phase 1.5 P15-S11 either implements DocSage independently from paper (reasoning module is LLM + standard SQL — no specialised models needed) or waits if reference impl ships under permissive license.

**Not in scope of this ADR:**
- Real implementation — covered by P15-S10 / P15-S11 sprints.
- Replacing pgvector — pgvector stays the default; PageIndex + DocSage are alternates routed-to per query characteristics.
- Replacing Pinecone Phase 1.5+ — Pinecone is for embedding-based vector storage; PageIndex/DocSage operate on different retrieval paradigms.

## Consequences

### Positive

- **Accuracy lift on Phase 1 v4's biggest known gap.** Pilot Olist multi-customer insight queries already show pgvector struggles; +27 percentage points on the multi-entity case is meaningful product differentiation.
- **No vector DB cost on PageIndex path.** Tier 1 cheaper for tenants who only do document-deep-dive (some VN customers may opt out of pgvector entirely Phase 2+).
- **Better explainability** (Tenet #6) — PageIndex returns the exact section traversed; DocSage returns the SQL query + tables joined. Both far more auditable than "vector top-5 cosine similarity".
- **Aligns with K-3 (LLM router) + K-20 (LLM version pinning).** Both engines call llm-gateway for their LLM steps; pinned model per workflow stays the rule.

### Negative / accepted trade-offs

- **3 engines = more code, more failure modes.** Routing logic adds complexity. Mitigation: contract surface (router.py + adapter ABC) lock at P15-S10; tests cover each engine independently.
- **DocSage Schema Discovery cost.** Each new query may trigger an LLM call to derive schema. Cache aggressively in idempotency_records — same (corpus_hash, query_class) → reuse schema.
- **PageIndex tree-build is pre-compute.** Adds onboarding latency (PDF upload → tree build minutes). Acceptable: builds are async, results cached. UX shows "Indexing..." progress.
- **Phase 1 v4 closeout doesn't include this.** v4 closed 2026-05-08; this ADR + spec ship as Phase 1.5 prep on `docs/v4-rag-addendum` branch. Em không touch v4 commits.

### Neutral / follow-ups

- Phase 1.5 P15-S10/S11 budget: ~1.5 sprints. Could compress into 1 sprint if PageIndex impl is straight wrap of upstream repo.
- DocSage paper re-read at P15-S11 kickoff for any updates to MEBench / methodology.
- Telemetry: P15-S10 add Prometheus counter `kaori_rag_engine_calls_total{engine}` to verify routing decisions match expected distribution.

## Alternatives considered

- **Keep pgvector-only Phase 1.5+.** Rejected: 27 percentage points accuracy gap on multi-entity is too meaningful to defer for "simplicity". Vietnamese SME manager BI questions mostly ARE multi-entity ("compare branches", "aggregate by department").
- **Replace pgvector entirely with PageIndex.** Rejected: pgvector is fine for short chat scenarios + lowest latency; tree traversal overkill there.
- **Wait for upstream DocSage reference impl.** Rejected: paper has all the info to implement; HKUST is an academic group, not a SaaS vendor — open-source impl uncertain timeline.
- **Use vendor RAG-as-a-service** (Pinecone Inference, Cohere RAG, etc.). Rejected: data residency (VN customers) + cost + ADR-0015 spirit (route-flexibly via adapters).

## References

- [PageIndex (VectifyAI, MIT licensed)](https://github.com/VectifyAI/PageIndex)
- [DocSage paper (HKUST, arXiv 2603.11798, Mar 2026)](https://arxiv.org/abs/2603.11798)
- [HKUSTDial NL2SQL Handbook](https://github.com/HKUSTDial/NL2SQL_Handbook)
- ADR-0012 (Postgres + ClickHouse polyglot)
- ADR-0015 (Qwen-first LLM with pluggable vendor adapters — DocSage SQL Reasoning step uses same routing)
- `docs/strategic/REASONING_LAYER.md` PART IV (RAG Knowledge Engine, 4-tier source architecture)
- `docs/specs/RAG_VECTORLESS_AND_STRUCTURED.md` (this addendum's companion spec)
- `docs/strategic/RAG_ADDENDUM_2026_05.md` (narrative addendum)
