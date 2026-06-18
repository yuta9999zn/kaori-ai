# ADR-0021 — Trace-augmented reasoning via T-Cube distillation

> **Status:** accepted
> **Date:** 2026-05-17
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0015 (Qwen-first LLM) · ADR-0019 (RAG vectorless + structured) · K-1 / K-3 / K-4 / K-5 / K-6 / K-20 · arXiv 2605.03344 "RAG over Thinking Traces"

## Context

Sprint P15-S11 shipped Stage 7 Memory hierarchy với 4 tier (L1 Working, L2 Short, L3 Episodic, L4 Long), kèm 5 memory types (EPISODIC / SEMANTIC / PROCEDURAL / OPERATIONAL / DECISION). L4 PROCEDURAL tier hiện tại **không có producer** — service infrastructure đã sẵn nhưng không có data flow vào.

Cùng thời điểm, paper arXiv 2605.03344 (Arabzadeh, Zaharia et al., UC Berkeley) chứng minh: với benchmark toán học khó AIME, retrieve **thinking traces** (chuỗi suy nghĩ thô của AI giải bài tương tự) tăng accuracy Gemini 2.5 Flash từ 53.3% → 83.3% (+56% tương đối), và tăng GPT-5 từ 86.7% → 93.3%. Cost giảm 15% vì retrieval thay generation.

Kaori đã có ingredients:
- `decision_audit_log` (K-6, mig 001) ghi mỗi automated decision + `reasoning` text column + alternatives + confidence
- Memory L4 PROCEDURAL tier ship trong P15-S11 (`2ed08e4`)
- RAG router pluggable 3-engine (ADR-0019, ship P15-S10)
- LLM gateway adapter (ADR-0015) cho cross-model trace producers (Qwen / Anthropic / OpenAI)

Tension:
- **Pro:** Paper validate pattern Kaori đã chọn (Memory L4 + Stage 12 Loop "reusable learning across runs"). Adding T-Cube fills the missing producer side.
- **Con:** Multi-tenant complication. Paper assumes shared corpus cross-task; Kaori is RLS-strict (K-1). Single-tenant trace recall has cold-start problem (first 90 days = no L4 PROCEDURAL data). Cross-tenant L4b shared tier requires legal review (deferred in `feedback_rbac_a_b_decision`).
- **Cost:** T-Cube distillation needs 3 LLM calls per source decision. Paper used Gemini-2-Flash-Lite (cheap small model). Kaori defaults to Qwen 2.5 14B local (K-4) — no external cost but inference time.

## Decision

We adopt T-Cube as the producer for Memory L4 PROCEDURAL tier, scoped per-tenant in Phase 2.

Implementation surfaces:

1. **`reasoning/trace_distiller/`** — async transformer wrapping the LLM gateway. Takes one `ThinkingTrace` (decision_audit_log row), emits 3 `TCubeOutput` forms (Struct / Semantic / Reflect) in parallel via `asyncio.gather`. Stores 3 `MemoryRecord` into L4 PROCEDURAL with metadata `{tcube_form, source_decision_id, source_llm_provider, source_llm_version (K-20), distiller_model, problem_context}`.

2. **`reasoning/rag/engines/trace_recall.py`** — 4th RAG engine. Retrieves top-k semantic-form traces from L4, joins with sibling reflect-form (same `source_decision_id`) to surface "watch out for" hints. Engine is opt-in via `RAGRouter(trace_recall=...)` constructor — default `RAGRouter()` ships with 3 engines unchanged (avoids forcing MemoryService dep on stub tests).

3. **`rag/router.py` Rule 4** — reasoning-task keywords (`tính toán`, `tối ưu`, `kế hoạch`, `đề xuất`, `what should`, `how do I`, `strategy`, `plan`) AND query length ≥ 8 words → route to `trace_recall`. Placed AFTER Rule 1 (doc-citation pageindex) so contractual queries still pageindex, BEFORE length-based pgvector/docsage rules.

4. **`reasoning/augment.py`** — helper `augment_prompt_with_traces()` for AI node handlers (mig 068 catalog: `call_insight_engine`, `call_recommendation_engine`, `call_risk_detection`, `call_forecasting`). NO-OP when no traces match — base prompt passes through unchanged so cold-start environments still work.

Tenant scope: trace_recall is single-tenant only Phase 2. L4b shared cross-tenant memory remains deferred pending legal review.

K-20 enforcement: trace metadata carries `source_llm_version` so retrievers can filter by version compatibility (avoid mixing Qwen-2.5 traces with Qwen-3.0 reasoning).

K-5 enforcement: PII redaction MUST happen before storing traces. T-Cube distillation runs on already-masked content (Vietnamese-aware mask from P15-S11). Distiller's prompts further compress traces, reducing re-leak risk.

## Consequences

### Positive

- Memory L4 PROCEDURAL tier gets a producer — kéo Stage 7 từ "infrastructure-only" thành "active learning loop".
- Stage 12 Loop (60-day baseline + 90-day A/B + Promotion) gains retrieval-side leverage — promoted strategies feed into trace recall.
- AI nodes (mig 068) get a free quality boost without changing their interfaces — augmentation is prepend-only.
- Cross-model transfer: Qwen-distilled traces from one tenant's GPT-5 sessions (if `consent_external=true`) become reusable Qwen prompts → cost reduction for that tenant's future GPT-5 calls.

### Negative / accepted trade-offs

- Cold-start: first 90 days per tenant has empty L4 PROCEDURAL → no augmentation benefit. Mitigation: ship 25 production templates (mig 069) seed thinking traces from canonical workflows.
- Three additional LLM calls per source decision distilled. Mitigation: batch async via `embedding_worker` pattern; defer distillation for low-confidence decisions (confidence < 0.6).
- Single-tenant cold-start vs paper's shared corpus assumption — paper's headline metrics may not transfer to per-tenant scope until L4 fills.
- Memory L4 grows unbounded; needs forget policy (90-day age + score < 0.3 already in MemoryService).

### Neutral / follow-ups

- L4b shared cross-tenant memory: trigger to revisit = legal review complete + PII redaction quality measured ≥ 99% precision on Vietnamese corpus.
- Distiller model upgrade: when Qwen 3 ships, run shadow distillation + compare retrieval quality before swap.
- Cost monitoring: track `distiller_model` tokens-per-trace as a separate billable line item (NOT counted toward customer's pricing tier — system internal).

## Alternatives considered

- **Alt 1: Use raw `decision_audit_log.reasoning` directly without distillation.** Rejected — paper §3.1 explicitly demonstrates raw traces are too noisy/long for retrieval (their AIME tests showed raw retrieval underperformed by 10-15 pts). Distillation is the discriminator.
- **Alt 2: Store only one form (semantic).** Rejected — paper shows Reflect-form (pitfalls) is what jumps GPT-5 from 86.7 → 93.3, not Semantic alone. Struct form is cheap and useful for human review.
- **Alt 3: Build a separate "trace_kb" table outside Memory tier system.** Rejected — Memory L4 already has the schema (mig 067 pgvector + RLS + importance scoring + forget policy). Adding another table duplicates infrastructure + breaks Stage 7 unification.
- **Alt 4: Distill at query time (lazy).** Rejected — paper's cost claim (-15%) depends on pre-computed traces. Lazy distillation adds latency to AI node calls (the hot path).

## References

- arXiv 2605.03344 — RAG over Thinking Traces Can Improve Reasoning Tasks (Arabzadeh, Zaharia et al., UC Berkeley, 2026)
- `docs/strategic/PIPELINE_UNIFIED.md` §7 Memory System (4-tier hierarchy spec)
- `services/ai-orchestrator/reasoning/trace_distiller/transformer.py` (D1 impl)
- `services/ai-orchestrator/reasoning/rag/engines/trace_recall.py` (D2 impl)
- `services/ai-orchestrator/reasoning/augment.py` (D3 hook)
- `services/ai-orchestrator/tests/test_p2_s21_trace_distiller_and_recall.py` (25 tests, 8 sections)
