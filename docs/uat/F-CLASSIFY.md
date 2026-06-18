# UAT — F-CLASSIFY (AI Node: Document Classification)

> **Function:** Phase 2.5 AI node `classify_document` — VN-aware document classifier
> **Portal:** P2 Enterprise (rendered trong Workflow Builder card execution)
> **Roles allowed:** All roles can trigger via workflow run; node config edit cần ANALYST+ (Advanced mode)
> **Service:** ai-orchestrator (`reasoning/document_classifier.py`) → llm-gateway
> **DB:** Catalog row mig 085 `node_type_catalog` key=`classify_document`; output persisted to caller's table (read_only K-17)
> **Owner:** QA Lead + Data Analyst
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ship `2792f21`)

| Surface | Purpose |
|---|---|
| `reasoning/document_classifier.py` | 1-LLM-call wrapper → `{category, confidence, reasoning}`. OOV coerced to 'uncertain' |
| Catalog row mig 085 | `classify_document` registered as read_only K-17 node |
| Node executor `executors/ai.py:classify_document` | Wraps via `llm_router.complete_structured(output_schema=...)` |

Tests pass: `tests/test_classify_document.py` 7/7.

---

## 1. Test scenarios — Given/When/Then

### TC-1 Happy path (Vietnamese contract)
- **Given** workflow node `classify_document` config `{categories: ['hợp đồng', 'báo cáo', 'hoá đơn'], document_input: $card.previous.text}`
- **When** workflow run với input là PDF text 1 hợp đồng thuê văn phòng
- **Then** output `{category: 'hợp đồng', confidence: ≥0.8, reasoning: '...'}`; persisted vào `workflow_run_nodes.output_payload`; K-6 audit row in `ai_decision_audit` mig 098

### TC-2 Out-of-vocabulary
- **Given** categories `['hợp đồng', 'hoá đơn']`, input là CV cá nhân (không thuộc 2 category)
- **When** classify
- **Then** output `{category: 'uncertain', confidence: <0.5, reasoning: 'Không khớp category nào đã cho'}`; KHÔNG raise — degraded result with low confidence

### TC-3 Confidence-based routing (per NFRS §13.2)
- **Given** confidence < 0.6 (UNCERTAIN threshold)
- **Then** workflow branch routes to `human_review_card` (per workflow YAML); auto-execute KHÔNG fire

## 2. Negative scenarios (NFRS §13.3 mandatory 4-case)

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid VN doc + categories | Above TC-1 |
| **Validation** | categories=[] (empty) | 422 RFC 7807 `{code: USR-ERR-422-NODE_CONFIG, detail: 'classify_document requires non-empty categories'}` |
| **Permission** | User role VIEWER trigger workflow with classify | 403 USR-ERR-403-ROLE (V không thể trigger; OPERATOR+ required) |
| **Dependency** | llm-gateway down (5xx) | Per-item failure: workflow run completes with degraded entry `{category: 'unknown', error: 'llm_unavailable'}` per pattern "per-item LLM failure ≠ abort run". KHÔNG abort run |

## 3. K-rule invariants

- **K-3** Call via llm-gateway only ✓
- **K-4** Default Qwen local (`prefer_external=False`); external opt-in per tenant consent_external + per-call prefer_external
- **K-6** Every classification logged decision_audit_log + mig 098 ai_decision_audit (model_version + prompt_hash)
- **K-17** read_only — caller persists; node KHÔNG self-write external tables
- **K-19** OTel `tenant_id` + `workflow_id` + `node_key=classify_document` span attribute

## 4. Performance baseline (NFRS §2)

| NFR | Target P1 | Target P3 |
|---|---|---|
| NFR-P-05 Qwen 14B 512 tok P99 | <5s | <3s |
| Classify cost (avg) | ~200-500 tokens per call | — |

Run NFRS §2 AC: 1000 classifications back-to-back P99 < 5s; 0% timeout; 0% 5xx.

## 5. UAT execution checklist

- [ ] Setup: 1 tenant với consent_external_ai=false (default Qwen)
- [ ] Upload sample PDF VN contract + workflow with classify_document card
- [ ] Trigger run → verify output + audit + lineage walk (mig 097)
- [ ] Trigger second run với external opt-in (`consent_external=true`) → verify vendor path + PII masking pre-call
- [ ] Run 1000-batch perf test → verify NFR-P-05
- [ ] DLQ check: simulate llm-gateway 500 → verify per-item degraded entry, run not aborted

---

*UAT ID: UAT-CLASSIFY-001 · Owner QA Lead*
