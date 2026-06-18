# UAT — F-DEDUP (Pure Node: Record Deduplication VN-aware)

> **Function:** Phase 2.5 PURE node `dedup_records` — deterministic VN-aware dedup
> **Portal:** P2 Enterprise (workflow card execution)
> **Service:** ai-orchestrator (`reasoning/record_dedup.py`) — PURE K-17 (no LLM)
> **DB:** Catalog mig 086 (category='processing')
> **Owner:** QA Lead + Data Analyst
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ship `99471cd`)

| Surface | Purpose |
|---|---|
| `reasoning/record_dedup.py` | Deterministic dedup với VN normalisers |
| VN normalisers | `vn_phone` unifies +84/0 prefix; `vn_name` strips diacritics + đ→d; email lower; raw |
| Fuzzy gating | Only keys with `vn_name` get fuzzy (Levenshtein); other keys exact match |
| Conflict policies | first/last/longest_non_empty hoặc caller merge_fn |
| **K-17 PURE** | No LLM call, no external — fully deterministic, idempotent |

Tests pass: `tests/test_record_dedup.py` 18/18 (incl. VN diacritics edge cases).

---

## 1. Test scenarios

### TC-1 Happy path (dedup khách hàng theo SĐT)
- **Given** input 100 rows với SĐT trong các format: +84912345678, 0912345678, (+84) 912-345-678
- **When** dedup_records card với keys=[phone] using vn_phone normalizer + conflict='first'
- **Then** output ~95 unique rows (5 duplicates collapsed); rest preserved order; deterministic re-run gives same result

### TC-2 VN name fuzzy match
- **Given** rows: "Nguyễn Văn A", "Nguyen Van A", "nguyễn văn a"
- **When** dedup keys=[name] với vn_name normalizer + fuzzy_threshold=0.95
- **Then** 1 row remains (3 collapsed); diacritics + case normalized

### TC-3 Composite key + conflict resolution
- **Given** rows với (phone + email) composite key; conflict='longest_non_empty'
- **When** dedup
- **Then** kept row có most non-null fields (longest non-empty wins per col)

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid rows + keys | TC-1 |
| **Validation** | keys=[] | 422 USR-ERR-422-NODE_CONFIG |
| **Permission** | VIEWER trigger | 403 |
| **Dependency** | None — PURE compute, no external | N/A |

## 3. K-rule invariants

- **K-17 PURE** Deterministic, no side effects, idempotent infinitely ✓
- **K-19** OTel span (rows in / rows out + dedup count)

## 4. Performance

| NFR | Target |
|---|---|
| Dedup 10k rows | <2s |
| Dedup 100k rows | <30s |

## 5. UAT execution checklist

- [ ] Setup 100-row CSV với SĐT VN trộn 5 formats
- [ ] Trigger dedup → verify ~95 unique + idempotent (re-run same output)
- [ ] VN name fuzzy: test 50-name dataset với diacritics variants
- [ ] Composite key + longest_non_empty conflict mode
- [ ] Performance: 100k row dataset perf test

---

*UAT ID: UAT-DEDUP-001 · Owner QA Lead*
