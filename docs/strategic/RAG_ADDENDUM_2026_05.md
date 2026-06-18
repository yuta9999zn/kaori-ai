# RAG Addendum 2026-05 — Tier 1 retrieval upgrade beyond pgvector

> **Status:** addendum to `docs/strategic/REASONING_LAYER.md` PART IV
> **Date:** 2026-05-08
> **Companion ADR:** [ADR-0019](../adr/0019-vectorless-tree-retrieval-and-structured-sql-rag.md)
> **Companion spec:** [`docs/specs/RAG_VECTORLESS_AND_STRUCTURED.md`](../specs/RAG_VECTORLESS_AND_STRUCTURED.md)

This is a **non-breaking addendum** to the Reasoning Layer doc — Phase 1 v4 closeout (`v4.0-phase1-complete`) shipped per the existing 4-tier RAG architecture. This addendum captures two Phase 1.5 enhancements landing P15-S10 / P15-S11:

1. **PageIndex** — vectorless hierarchical tree retrieval (FinanceBench 98.7% accuracy, MIT licensed)
2. **DocSage** — structured SQL reasoning for multi-entity QA (MEBench 89.2% vs GPT-4o RAG 62%)

Original 4-tier architecture stays intact; PageIndex + DocSage are **additional Tier 1 engines** routed-to alongside pgvector based on query characteristics.

---

## 1. Why this addendum exists

Phase 1 v4 P1-S5 shipped `services/ai-orchestrator/reasoning/rag/` skeleton with pgvector as the canonical retrieval engine. Phase 1.5 plan was: wire pgvector real impl + Pinecone managed alternates.

Two papers / repos surfaced after Phase 1 v4 close (Q1 2026 publications):
- DocSage (HKUST, Mar 2026 arXiv) — +27 percentage points multi-doc QA accuracy via SQL reasoning.
- PageIndex (VectifyAI) — vectorless tree retrieval, 98.7% on FinanceBench (vs ~50% vector RAG baseline on professional documents).

Pure pgvector is fine for short single-entity Q&A. Pure pgvector is **wrong** for:
- Vietnamese SME manager BI questions (multi-entity comparison, cross-doc aggregation).
- Document-deep-dive on PDF reports / contracts / SOPs (where document hierarchy carries meaning).

This addendum locks the architectural decision now so Phase 1.5 P15-S10/S11 ship the right thing.

---

## 2. Reasoning Layer Tier 1 — updated picture

### 2.1 Original v4 plan (REASONING_LAYER.md PART IV)

Tier 1 — pure retrieval — was specified as **pgvector embedding similarity** (Phase 1.5 + Pinecone managed alternative for data residency strict tenants).

### 2.2 Updated plan (this addendum)

Tier 1 becomes a **3-engine pluggable layer**:

| Engine | Best for | Phase | Storage |
|---|---|---|---|
| **pgvector** (default) | Short / single-entity / chat-style | P1-S5 contract → P15-S9 runtime | Postgres + pgvector extension |
| **PageIndex** (vectorless tree) | Document deep-dive (PDF, Markdown) | P15-S10 | `pageindex_trees` JSONB table (Postgres) |
| **DocSage** (structured SQL) | Multi-entity cross-doc QA | P15-S11 | `docsage_schemas` + `docsage_extractions` (Postgres) + ephemeral SQL CTE |

Tier 2 (knowledge graph, Neo4j) + Tier 3 (formula library) + Tier 4 (memory hierarchy) — unchanged.

### 2.3 Router (NEW)

`services/ai-orchestrator/reasoning/rag/router.py` (P15-S10) selects engine per query. Phase 1.5 heuristic; Phase 2 swaps to small classifier LLM.

```
                  ┌──────────────────────────────────────┐
   query  ───→   │   RAGRouter — 3-engine pluggable     │
                  └────┬───────────────┬───────────────┬─┘
                       ▼               ▼               ▼
              ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
              │  pgvector   │ │  PageIndex  │ │  DocSage    │
              │  similarity │ │  tree retr. │ │  schema +   │
              │  + chunks   │ │  + page#    │ │  SQL reas.  │
              └─────────────┘ └─────────────┘ └─────────────┘
                       │               │               │
                       ▼               ▼               ▼
              short Q&A on       PDF/doc deep-      multi-entity
              chat history       dive, hợp đồng     cross-doc QA
              + light RAG        sổ tay quy trình   (manager BI)
```

---

## 3. Why each engine matters cho VN SME context

### 3.1 PageIndex — tài liệu nội bộ

VN SMEs lưu ops trong:
- Hợp đồng PDF
- Báo cáo tài chính quý/năm
- Sổ tay quy trình (HR / vận hành / kinh doanh)
- Catalog sản phẩm

Pure vector RAG trên những docs này = tệ. Vector tìm "câu giống" thay vì "section đúng". Manager hỏi "Điều khoản phạt hợp đồng X" → vector trả 5 chunk ngẫu nhiên có chữ "phạt"; PageIndex trả node chính xác `Hợp đồng X → Điều 12 → Khoản 3 — Phạt vi phạm` với page range để click → preview PDF.

PageIndex giải quyết:
- ✅ Recall trên professional document
- ✅ Citation chuẩn (page numbers)
- ✅ Explainability ("tại sao chọn section này" — LLM reasoning trace)
- ✅ Không vector DB cost cho tenant chỉ deep-dive doc

### 3.2 DocSage — manager BI questions

Manager hỏi:
- "So sánh doanh thu 5 chi nhánh quý vừa rồi"
- "Top 10 khách VIP có churn risk cao nhất + revenue protected"
- "Khách nào có ≥3 đơn từ shop A và đã hủy ≥1 đơn shop B?"

Đây là **multi-entity cross-doc questions**. Pure vector RAG đạt 35% accuracy với >100 entities (DocSage paper). Attention dilution ăn output: LLM "quên" entity giữa context dài.

DocSage:
1. Schema Discovery — LLM đọc câu hỏi, đề xuất minimal schema (ví dụ: `branches(id, name, revenue_q3)`).
2. Structured Extraction — LLM duyệt tài liệu khách, INSERT rows vào schema.
3. SQL Reasoning — compose SQL `SELECT ... GROUP BY ... ORDER BY ...`, execute trên Postgres, format result.

SQL JOIN không bị attention dilute. JOIN 100 entities vẫn chính xác tuyệt đối.

### 3.3 pgvector — chat / insight panel light

Vẫn cần. Insight panel "Tóm tắt 5 customer churn ngày qua" — pgvector nhanh nhất, rẻ nhất. PageIndex/DocSage overkill ở đây.

---

## 4. Mapping với existing v4 features

| BACKLOG_V4 feature | Engine sẽ dùng | Sprint |
|---|---|---|
| `P2-M210-014` RAG cho insights | pgvector (Phase 1.5 P15-S9) + PageIndex (P15-S10 cho doc-heavy queries) | hybrid via router |
| `P2-M210-012` Upload tài liệu nội bộ (PDF/Word/MD) | PageIndex tree-build trigger on upload | P15-S10 |
| `P2-M210-007` Dẫn chứng từ tài liệu user (document citation) | PageIndex citations (doc + node + page_range) — most accurate citation format | P15-S10 |
| `P2-M210-006` Dẫn chứng từ data (data citation) | DocSage cites SQL query + tables joined | P15-S11 |
| `P2-M216-002` Top 3 factors (explainability) | DocSage SQL = inherently explainable; pgvector "top-N similarity" much weaker | mostly P15-S11 |
| `P2-M27-006` Workflow recommendation | DocSage cross-doc analysis identifies workflow patterns from log | P15-S11 |
| `P2-M28-*` Multi-tier analysis (basic/intermediate/advanced) | Advanced tier → DocSage (manager BI questions); basic → pgvector | hybrid |

---

## 5. Cost & latency model

Phase 1.5 estimate (per query):

| Engine | Latency | LLM cost (Qwen local) | Notes |
|---|---|---|---|
| pgvector | <100 ms | ~$0.0001 | Existing baseline |
| PageIndex | 200-800 ms | ~$0.001 | LLM tree-traversal calls; tree pre-built async |
| DocSage | 1-3 s | ~$0.005-0.02 | Schema + Extraction + SQL Reasoning calls |

PageIndex tree-build happens once per doc (cached). DocSage schema + extraction cached per (corpus_hash, question_class). Caching dramatically reduces cost over time.

NOV-CST-009 (AI call cost tracking, P1-S7 shipped) records per-engine cost; Phase 1.5 reports show ROI per engine.

---

## 6. Phase 1.5 sprint allocation

| Sprint | Scope |
|---|---|
| **P15-S9** | pgvector real impl (existing plan unchanged) |
| **P15-S10** | RAGRouter + PageIndex engine + tree builder + Prometheus counters extension + tenant_settings.rag_engines toggle. Migration `pageindex_trees`. |
| **P15-S11** | DocSage 3-module pipeline + cache tables + acceptance benchmark on 50-entity sample. Migrations `docsage_schemas` + `docsage_extractions`. |

P15-S10 + P15-S11 budget: ~1.5 sprints. Could compress into 1 if PageIndex is straight wrap of upstream.

---

## 7. Open questions for Phase 1.5

1. **PageIndex packaging:** PyPI package or vendored fork? Decided P15-S10 kickoff after checking upstream PyPI status.
2. **DocSage upstream availability:** HKUST may release reference impl on HKUSTDial GitHub. Watch for permissive license; otherwise implement from paper.
3. **Tenant_settings UI:** opt-in toggle for engines. FE work — paused per anh.
4. **Routing heuristic vs classifier:** Phase 1.5 heuristic (length + keyword); Phase 2 small classifier LLM. When to upgrade?

---

## 8. References

- [PageIndex (VectifyAI, MIT)](https://github.com/VectifyAI/PageIndex)
- [DocSage paper (HKUST, arXiv 2603.11798, Mar 2026)](https://arxiv.org/abs/2603.11798)
- [HKUSTDial awesome-data-agents](https://github.com/HKUSTDial/awesome-data-agents)
- [HKUSTDial NL2SQL Handbook](https://github.com/HKUSTDial/NL2SQL_Handbook)
- ADR-0019 (companion architectural decision)
- `docs/specs/RAG_VECTORLESS_AND_STRUCTURED.md` (engineering spec for P15-S10/S11)
- `docs/strategic/REASONING_LAYER.md` PART IV (4-tier RAG architecture — original)
- `docs/archive/PHASE1_V4_CLOSEOUT.md` deferred-to-Phase-1.5 list (now updated to include P15-S10/S11)
