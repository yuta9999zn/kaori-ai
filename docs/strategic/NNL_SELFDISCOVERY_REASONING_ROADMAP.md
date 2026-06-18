# NNL Self-Discovery & Reasoning Convergence — Roadmap

> Updated: 2026-05-27 · Owner: data-pipeline + ai-orchestrator · Governance: CR-0016 (`docs/ba/4.2_Change_Request_Register.md`)
> Mục tiêu: port các cải tiến **self-discovery (không hardcode)** + **reasoning (CDFL / học-1-hiểu-10 / kho tri thức)** đã chứng minh ở prototype local (NNL-Harness) vào production Kaori System, **theo đúng spec + governance**.
> Ràng buộc cốt lõi: **ĐO được thì đo (deterministic); QUYẾT (diễn giải) thì đưa bằng chứng cho người/LLM — không hardcode, không bịa.**

---

## 1. ĐÃ XONG (2026-05-27) — CR-0016, PR #281

Silver layer tự khám phá thay 2 chỗ hardcode/thiếu (xem `docs/specs/MEDALLION_CONTRACT.md §6`):

| # | Thay đổi | File | Test |
|---|---|---|---|
| 1 | **Hướng ngày** đo từ data (`_infer_dayfirst`), bỏ `dayfirst=True` cứng; default env `KAORI_DATE_DAYFIRST_DEFAULT` | `data-pipeline/data_plane/silver/rule_catalog.py` | `TestInferDayfirstHelper`, `TestRuleParseDateDirectionInference` |
| 2 | Canonical **`unit_price`** + bỏ `"price"` rò khỏi `amount` | `config/language_dictionary.json` | (mapping) |
| 3 | **`rule_derive_line_total`** (`safe=False`, user duyệt) — `amount = unit_price × quantity` khi chưa có total | `rule_catalog.py` | `TestRuleDeriveLineTotal` |
| 4 | **`measure_amount_signals`** — ĐO bằng chứng để người/LLM QUYẾT | `rule_catalog.py` | `TestMeasureAmountSignals` |

- Gold (`gold/aggregator.py`) **không đổi** — normalize ở Silver, Gold strict (Medallion contract).
- **738 test data-pipeline pass, 1 skip, 0 regress.**
- **PR #281** (`silver-self-discovery-cr0016` → `main`). **Merge an toàn, không cần fix FE trước**: BE không có enum/CHECK trên canonical/rule_id; FE (`pipeline/SchemaReview.tsx` input tự do + `pipeline/CleaningReview.tsx` render động, tự bỏ chọn `safe=false`) hiển thị đúng canonical/rule mới.

---

## 2. BACKLOG — các mục cần làm (theo thứ tự ưu tiên)

### B1 · Closeout CR-0016  🟢 BE+FE DONE
- **BE** (đã ship): `/clean/suggestions` gắn `amount_signals` + `suggested` + `rationale` vào rule `DERIVE_LINE_TOTAL` (`_amount_signals_for_run` + `_suggest_line_total`). Gợi ý **dựa trên PRESENCE facts (ĐO thuần, không ngưỡng cứng)**: có unit_price+quantity & chưa có total → gợi ý; đã có total → không. *Chọn ĐO thay vì gọi LLM — grounded, không hallucinate, đúng "đo được thì đo"; ca thực sự mơ hồ để user quyết với bằng chứng.* Best-effort.
- **FE** (đã ship): `CleaningReview.tsx` pre-select `DERIVE_LINE_TOTAL` khi `suggested`, badge "Gợi ý" + panel bằng chứng; `SchemaReview.tsx` hint nhãn canonical (`unit_price` vs `amount`). +4 test, suite data-pipeline 742 pass.
- Governance: CR-0016 (BE+FE done). Tuỳ chọn tương lai: LLM rationale layer cho ca cột-tiền-đơn-lẻ mơ hồ.

### B2 · Gap (a) — Kho tri thức ngành ("kho tri thức")  🟢 BE DONE (CR-0017), CÒN FE
- **Foundation (PR #282)**: `mig 106 knowledge_documents` (VECTOR 1024, 4-tier authority, RLS global+own) + `reasoning/knowledge/{store,embed}` + router `/knowledge-base/{documents,search}` + 12 test.
- **Increment 2 (PR mới)**: wire vào **RAG answer** — `reasoning/rag/engines/pgvector_real.py::_load_knowledge` (search `<=>` dùng embedding ĐÃ LƯU, blend vào ranking; trả lời cả khi tenant chưa upload) +3 test · **seed** `mig 107` (5 mục ngành: RFM/Pareto/AOV · churn · retention · NOV — tier 2-3 advisory) · `scripts/reembed_knowledge.py` (admin re-embed rows seed). → Tri thức ngành CHẢY vào insight (như local).
- **Còn lại**: **FE F-061** — thay placeholder `28-insight-knowledge-base.tsx` bằng search thật + ingest tenant; chạy `reembed_knowledge.py` post-deploy (cần llm-gateway).
- Governance: **CR-0017** (MEDIUM, IMPLEMENTING — BE done).

### B3 · Gap (b) — Grounding self-verify cho insight (CR-0018)  🟢 BE+FE DONE
- **Làm rõ (quan trọng)**: paper `|OR| = I(I:M)` (Hilbert mutual information, `cdfl/hilbert_metric.py`) là độ đo **observability** trên ma trận mật độ — KHÔNG áp được lên "số nêu có thật không". B3 dùng **`|OR|` number-overlap thực dụng** (số insight ∩ số đo được) như `reason_grounded` local — analog cùng tinh thần, KHÔNG phải Hilbert metric. ⟹ **KHÔNG đụng ADR-0020**; là hiện thực **Phần 14 Anti-Hallucination** (spec đã có) → **MEDIUM, không cần Sponsor**.
- **BE (đã ship, PR mới)**: `reasoning/grounding.py` (`extract_claims`/`collect_facts`/`ground_claims`/`disclaimer_for`) + `insights_feed`: đưa số liệu thật vào prompt (phòng bịa) + verify output gắn `grounding_score`+`flagged_claims`+disclaimer BR-9 (bắt bịa). KHÔNG auto-rewrite (an toàn). +13 test, suite 2604 pass. CDFL RAG re-rank/observability không đụng.
- **FE (đã ship)**: `insights/page.tsx` đồng bộ contract `{insights}` + badge "Khớp dữ liệu %" + ⚠ số nghi-bịa + disclaimer; mock dashboard.ts cập nhật. (Phát hiện: FE↔BE contract insight-feed vốn lệch — đã reconcile.)
- **Deferred**: cột audit `grounding_score` ở `ai_decision_audit` — cần `llm_router.complete` trả model metadata (hiện chỉ trả `str`); grounding đã có ở response + structlog nên chưa gấp. Mở rộng grounding sang multi-tier/report narrative (xa hơn).
- Governance: **CR-0018** (MEDIUM, PO+TL).

### B4 · Gap (c) — Platform AI config / admin tuning (CR-0019)  🟢 DONE (BE+FE+wire)
- **BE (đã ship)**: `mig 108 platform_ai_config` (global, bounds validate trong DB) + `shared/ai_config.py` (cache + fallback hằng số, fail-open) + `llm_ops` GET/PATCH `/platform/llm/config` (SUPER_ADMIN). **Wire `grounding_tolerance`** vào `insights_feed` → chứng minh đổi-knob-không-redeploy. 7 knob seed (1 applied, 6 reserved). +17 test, suite 2622 pass.
- **FE + gateway (đã ship)**: màn `/platform/llm-config` + `lib/api/llm-config.ts` + nav "LLM & AI". **Đính chính:** `/platform/llm` CHƯA có route gateway (đi vào auth-service catch-all) → đã THÊM route `platform-llm` → ai-orchestrator (+test 19/19) — fix luôn cho cả llm_ops P2-S22.
- **Wire (đã ship, mig 109 applied=true)**: `rag_max_corpus_docs` (pgvector `_load_corpus`) + `memory_promotion_threshold`/`forget_threshold`/`forget_age_days` (memory service đọc config khi không pin). Để applied=false CÓ CHỦ ĐÍCH: `rag_max_citations` (per-request, không hợp global), `embedding_model` (K-20 — đổi qua env + re-embed). (Tiện tay sửa latent bug import `...shared.db`→`ai_orchestrator.shared.db` ở pgvector `_load_corpus`.)
- **Còn lại (xa)**: sửa prompt chưng cất/framework qua UI.
- Governance: **CR-0019** (MEDIUM, PO+TL).

---

## 3. ĐIỂM SỬA HÔM NAY (code-level, chưa có UI) — tham chiếu nhanh

| Hệ | Chỉnh gì | File / vị trí |
|---|---|---|
| **RAG** | luật chọn engine | `ai-orchestrator/reasoning/rag/router.py:58-91` |
| | top-K trích dẫn | `ai-orchestrator/routers/rag.py:111` (`max_citations`) |
| | trần corpus | `engines/pgvector_real.py:64` (50) · `engines/docsage/engine.py:39` (20) |
| | embedding (BGE-M3 1024d) | `llm-gateway` + pin `memory_l3.embedding_model` (K-20) |
| | HNSW (m=16, ef=64) | mig `067_memory_l3_pgvector.sql:84-85` |
| **Memory** (4-tier) | backend tầng | `reasoning/memory/service.py:56-74` |
| | promote / forget | `service.py:47` (0.7) · `:49-50` (0.3 / 90d) |
| **CDFL** | IG knobs | `reasoning/cdfl/agent.py:57-61` (horizon=5, rollouts=6, weights=1.0, temp=0.1) |
| | bật re-rank RAG | query `?ranking=cdfl_ig` |
| **Học 1 hiểu 10** | prompt chưng cất (struct/semantic/reflect) | `reasoning/trace_distiller/prompts.py:14,35,55,92` |
| | tiêm ca tương tự vào prompt | `reasoning/augment.py:43-46,55` (top_k=3) |
| | khung SWOT/6W/2H/Fishbone | `frameworks/templates.py:44-190` (REGISTRY Python) |
| | seed nguội | mig `069_production_templates_seed.sql` |

---

## 4. Thứ tự thực hiện (đã chốt với owner)
1. **Merge PR #281** (an toàn). → FE closeout B1 (nhãn + evidence panel).
2. **B1** BE closeout (LLM auto-suggest + confirm gate).
3. **B2** kho tri thức ngành (CR mới) — gần nhất với giá trị local.
4. **B3** CDFL grounding self-verify (CR mới, Sponsor).
5. **B4** Admin UI (CR mới).

> Cập nhật HTML: `docs/sprint/system-architecture.html` (§Silver + §roadmap) phản ánh CR-0016 + backlog này.
