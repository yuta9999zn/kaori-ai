# UAT — F-AI-DECISION-AUDIT (Immutable Per-LLM-Call Audit)

> **Function:** Phase 2.7 P3 — ai_decision_audit table immutable per LLM call
> **Portal:** P2 Enterprise (P2-21 AI Decision Log màn — claim `view_audit_log` required) + P2-20 Insight Detail audit panel
> **Service:** ai-orchestrator + llm-gateway (`shared/ai_governance.py`)
> **DB:** mig 098 `ai_decision_audit` with conditional immutability trigger
> **Owner:** SEC + QA Lead + Compliance Auditor
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.7 ship `5e750b2` + wiring `7bb4c65`)

| Surface | Purpose |
|---|---|
| Mig 098 `ai_decision_audit` | Conditional immutability trigger (UPDATE allowed ONLY for `user_id/at/note` override fields; DELETE blocked). Captures: model_version + model_provider + prompt_hash + prompt_size + context_refs jsonb + confidence + output_hash + output_validated + consent_external + pii_redacted + latency_ms + token counts + cost_cents + human_override fields |
| `ai_governance.py` | hash_prompt/hash_output (SHA-256 + 1MB truncation) + record_ai_call + record_human_override + list_for_tenant |
| Wiring | llm-gateway records to ai_decision_audit on EVERY /v1/infer + /v1/embed + /v1/ocr call |

Tests pass: `tests/test_ai_governance.py` 15/15.

---

## 1. Test scenarios

### TC-1 Happy path (LLM call → audit row)
- **Given** LLM call via `/v1/infer` with prompt + output
- **When** Call completes
- **Then** New row in ai_decision_audit with full metadata; prompt_hash + output_hash deterministic SHA-256; cost_cents calculated from token count × per-token rate

### TC-2 Human override flow
- **Given** AI decision with low confidence → human override
- **When** User calls `record_human_override(decision_id, user_id, note='wrong category, manual override')`
- **Then** UPDATE allowed ONLY for user_id/at/note fields; other fields unchanged; new audit entry `override_recorded`

### TC-3 Cross-LLM-provider audit
- **Given** Qwen local call + Claude external call same tenant same prompt
- **When** Both complete
- **Then** 2 rows with different model_provider (`qwen-local`, `claude-vendor`); both audited; cross-compare possible for drift

### TC-4 Immutability trigger
- **Given** SQL `UPDATE ai_decision_audit SET prompt_hash='fake' WHERE id=X`
- **When** execute
- **Then** Postgres trigger blocks (only override fields mutable); `DELETE` also blocked

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | LLM call completes | TC-1 |
| **Validation** | Invalid confidence (>1.0) | 422 USR-ERR-422-AUDIT-CONFIDENCE |
| **Permission** | Non-`view_audit_log` claim query | 403 USR-ERR-403-CLAIM |
| **Dependency** | mig 098 DB write fail | LLM call still succeeds (best-effort gov per pattern); warning log; quality_score impact |

## 3. K-rule invariants

- **K-4** consent_external + pii_redacted set TRUE only for `method='external'`; embed/ocr ALWAYS False
- **K-6** Every AI decision audited ✓
- **K-19** OTel span includes audit_recorded boolean

## 4. Performance

| NFR | Target |
|---|---|
| record_ai_call (insert) P99 | <50ms |
| list_for_tenant (1k rows, paginated) | <200ms |

## 5. UAT execution checklist

- [ ] Verify mig 098 applied + immutability trigger present
- [ ] Fire LLM call → verify row inserted with all required fields
- [ ] Try UPDATE non-override field → verify trigger blocks
- [ ] Try DELETE → verify trigger blocks
- [ ] Cross-provider audit: Qwen + Claude same prompt → verify 2 distinct rows
- [ ] Permission: VIEWER without `view_audit_log` → 403
- [ ] Compliance audit: export 1k audit rows → verify integrity (no missing rows for shipped calls)

---

*UAT ID: UAT-AI-DECISION-AUDIT-001 · Owner SEC + Compliance*
