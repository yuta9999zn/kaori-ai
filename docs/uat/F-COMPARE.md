# UAT — F-COMPARE (AI Node: Template Comparison / Contract Diff)

> **Function:** Phase 2.5 AI node `compare_to_template` — RAG-backed contract diff
> **Portal:** P2 Enterprise (workflow card execution)
> **Service:** ai-orchestrator (`reasoning/template_comparator.py`) → llm-gateway + BGE-M3 embed
> **DB:** Catalog mig 087
> **Owner:** QA Lead + Legal/Compliance reviewer
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ship `0ce5115`)

| Surface | Purpose |
|---|---|
| `reasoning/template_comparator.py` | RAG-backed contract diff: clause extraction (TITLE-grouped) → BGE-M3 embed → cosine match → per-pair LLM diff → risk keyword bump (17 VN/EN defaults) → score 0..1 |
| Catalog row mig 087 | `compare_to_template` registered read_only |
| Pattern | LLM diff per-pair failure fallback (never aborts run) |

Tests pass: `tests/test_template_comparator.py` 22/22 (clause extraction + cosine match + diff + risk bump).

---

## 1. Test scenarios

### TC-1 Happy path (compare new contract vs standard template)
- **Given** New contract PDF + standard template PDF (cùng VN legal); 17 risk keywords default
- **When** compare_to_template card runs
- **Then** output `{clauses_compared: N, diffs: [{template_clause, new_clause, similarity: 0..1, risk_keywords_hit: [...], llm_diff_summary: '...'}], overall_risk_score: 0..1}`; clauses TITLE-grouped, missing clauses flagged

### TC-2 Per-pair LLM diff failure
- **Given** 50 clause pairs; LLM 500 on pair 23
- **When** compare
- **Then** 49 diffs successful + 1 fallback `{template_clause, new_clause, similarity_cosine_only: 0.X, llm_diff: 'failed', error: '...'}`; run completes; risk_score weighted

### TC-3 Custom risk keywords
- **Given** caller passes `risk_keywords=['penalty', 'phạt', 'gia hạn tự động']` (override default)
- **When** compare
- **Then** matches flagged + score bumped per keyword hit

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid 2 contracts | TC-1 |
| **Validation** | template_doc null | 422 |
| **Permission** | VIEWER trigger | 403 |
| **Dependency** | BGE-M3 embed service down | Run fails với 503; retry exponential |

## 3. K-rule invariants

- **K-3** llm-gateway + BGE-M3 (local) ✓
- **K-4** Default Qwen local + BGE-M3 local
- **K-6** audit per LLM diff call mig 098
- **K-17** read_only
- **K-19** OTel span per-clause-pair

## 4. Performance

| NFR | Target |
|---|---|
| Compare 50-clause contract pair | <60s (50 LLM calls parallel batches of 10) |
| Embed 100 clauses (BGE-M3 local) | <10s |

## 5. UAT execution checklist

- [ ] Setup 5 sample contract pairs (VN lease, employment, NDA, vendor agreement, partnership)
- [ ] Trigger compare → verify clauses + diffs + risk score
- [ ] Custom risk keywords: test với VN legal terms ['phạt', 'gia hạn tự động', 'bồi thường thiệt hại']
- [ ] LLM failure fallback: kill llm-gateway mid-compare → verify graceful degradation

---

*UAT ID: UAT-COMPARE-001 · Owner QA Lead + Legal*
