# Module Map — Kaori AI v4

> Tách từ `CLAUDE.md` §14a + §14b + §14c ngày 2026-05-22. Reference table — đọc khi cần biết "module X ở đâu, side-effect class gì, catalog mig nào".

---

## P15-S10 endpoint wiring (2026-05-12)

Library code + tests shipped HTTP routers + tests + drift artefacts. All 5 endpoints callable now.

| Endpoint | Router | Tests |
|---|---|---|
| `POST /rag/answer` (D6) | `services/ai-orchestrator/routers/rag.py` | `tests/test_rag_endpoint.py` 6/6 |
| `POST /adoption/interventions/trigger` (D3+D4) | `routers/adoption.py` | `tests/test_adoption_endpoint.py` 5/5 |
| `POST /economics/revenue/estimate` dispatcher (D5) | extended `routers/economics.py` | `tests/test_economics_revenue_estimate.py` 5/5 |
| `POST /process-mining/connectors/gmail-outlook` (D1) | `services/data-pipeline/routers/process_mining.py` | `tests/test_process_mining_router.py` 4/8 |
| `POST /process-mining/connectors/calendar` (D2) | same | 2/8 |

Test deltas: ai-orchestrator 623 → **639**, data-pipeline 416 → **424**. OpenAPI specs regenerated (`pipeline` 19→21 paths, `orchestrator` 43→46 paths). FE TypeScript types regenerated (pipeline.d.ts 1202→1386 lines, orchestrator.d.ts 3495→3877 lines). The S9 D7 NOV ROI dashboard IS the `/economics/nov/{current,trend}` pair shipped earlier — no new endpoint needed there.

Note: connector registration endpoints return a `session_id` handle but do NOT trigger polling — that's the Temporal worker's job (gated behind `TEMPORAL_ENABLE_WORKER=true`, default false P15-S10). FE wires the "Connect Gmail / Connect Calendar" wizard against these endpoints today; live polling lights up when worker enables (P15-S11+).

---

## P2-S15 follow-up infra (post-sprint additions)

After P2-S15 ship, em added 2 cross-cutting modules on top of mig 068 catalog:

| Module | Purpose | Files |
|---|---|---|
| `reasoning/trace_distiller/` | T-Cube paper port (ADR-0021) | `transformer.py` + `worker.py` + `runner.py` + `prompts.py` |
| `reasoning/rag/engines/trace_recall.py` | 4th RAG engine for thinking-trace recall | one file |
| `reasoning/augment.py` | Prompt augmentation hook for AI nodes (mig 068) | one file |
| `org_intel/economics/{recommendations,simulation}.py` | NOV-RPT-023/024 pure compute | two files |
| `org_intel/observability/` | OBS-018/021/023 pure compute (anomaly + capacity + redaction) | three files |
| `chat/tool_necessity.py` | Knowing-doing gap heuristic gate (ADR-0023) + DPEPO-style depth/width loop guardrail on tool-call history (2026-05-21, ADR-0023 Alt 5) | one file |
| `shared/{crypto,totp}.py` | AES-256-GCM + RFC 6238 TOTP | two files |

---

## P2.5 MinerU + AI node catalog map (2026-05-18 → 19)

9 new modules behind catalog rows in mig 085-087. All read_only or pure per K-17 — caller persists results.

| Module | Catalog mig | Side-effect | What |
|---|---|---|---|
| `data-pipeline/data_plane/silver/blocks.py` | — (taxonomy only) | n/a | MinerU-style Block + BlockType enum (text/title/list/table/header/footer/page_number/image_ref/caption/code/quote/equation) |
| `data-pipeline/data_plane/silver/header_footer_strip.py` | — | pure | Pattern 2 — repeating-line detection across pages |
| `data-pipeline/data_plane/silver/table_extractor.py` | — | pure | Pattern 3 — pdfplumber tables → TABLE blocks with markdown+html+rows |
| `data-pipeline/data_plane/silver/reading_order.py` | — | pure | Pattern 4 — X-histogram bimodality detection + per-column reorder; single-col pages skip (zero cost) |
| `data-pipeline/data_plane/silver/ocr_client.py` | — | external | Thin async wrapper over llm-gateway `/v1/ocr`; pre-flight gates (empty / oversize / non-image short-circuit); never raises |
| `llm-gateway/providers.py:ocr_image` + `/v1/ocr` route | — | external (Ollama Qwen2.5-VL local) | K-4 ENFORCED at schema (no consent_external on OcrRequest); vendor vision = Phase 3 + ADR; pinned by test |
| `ai-orchestrator/reasoning/document_classifier.py` | 085 | read_only | 1 LLM call → category + confidence + reasoning; OOV coerced to 'uncertain' |
| `ai-orchestrator/reasoning/structured_extractor.py` | 085 | read_only | Per-TABLE LLM call → typed rows with provenance (page + block_id); per-table failure isolated |
| `ai-orchestrator/reasoning/document_summariser.py` | 086 | read_only | 1 LLM call → summary + bullets + next-action hint + reading_time_seconds |
| `ai-orchestrator/reasoning/sentiment_analyser.py` | 086 | read_only | 5-point symmetric scale + per-aspect; "unknown" sentinel for aspects not mentioned; PII smoke alarm |
| `ai-orchestrator/reasoning/record_dedup.py` | 086 | **PURE** | Deterministic dedup w/ VN normalisers (vn_phone, vn_name strip diacritics+đ, email, lower, raw); fuzzy gated to keys-with-vn_name; conflict policies first/last/longest_non_empty or caller merge_fn |
| `ai-orchestrator/reasoning/template_comparator.py` | 087 | read_only | RAG-backed contract diff — clause extraction → BGE-M3 embed → cosine match → per-pair LLM diff → 17-keyword risk bump (VN + EN business terms) → score 0..1; LLM diff failure falls back per-pair, never aborts run |
| `ai-orchestrator/data_plane_shim.py` | — | n/a | Cross-service Block + BlockType re-export (data-pipeline owns the canonical defs; ai-orchestrator dupes for compile-independence per Phase B-2 boundary) |

**Pattern em can lift to new nodes**: per-item LLM failure ≠ abort run. ocr_client, extract_structured_data, and template_comparator all return their result envelope with a degraded entry for failing items + a warning, not a 5xx. Caller's manual queue widens; pipeline completes.

**K-4 enforcement at schema level** (em pin via test): OcrRequest has no `consent_external` / `prefer_external`. Future vendor vision adapter MUST add the field → test fails before regression lands → forces deliberate ADR review.
