# UAT — F-SUMMARISE (AI Node: Document Summarisation)

> **Function:** Phase 2.5 AI node `summarise_document` — TL;DR + bullets + reading time
> **Portal:** P2 Enterprise (workflow card execution)
> **Service:** ai-orchestrator (`reasoning/document_summariser.py`) → llm-gateway
> **DB:** Catalog mig 086 (category='processing')
> **Owner:** QA Lead
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ship `99471cd`)

| Surface | Purpose |
|---|---|
| `reasoning/document_summariser.py` | 1 LLM call → `{summary, bullets[], next_action_hint, reading_time_seconds}` |
| Catalog row mig 086 | `summarise_document` registered (gotcha: category='processing' not 'transform') |
| Reading-time heuristic | 17 chars/sec VN average |

Tests pass: `tests/test_summariser.py` 9/9.

---

## 1. Test scenarios

### TC-1 Happy path (VN contract 5 trang)
- **Given** Bronze PDF text content extracted (post DocSage)
- **When** summarise_document card runs
- **Then** output `{summary: '...3-5 dòng tiếng Việt...', bullets: [3-5 bullets], next_action_hint: '...', reading_time_seconds: ~N}`; reading_time matches 17 chars/sec heuristic ±10%

### TC-2 Empty document
- **Given** Bronze file post DocSage có 0 text content (image-only chưa OCR)
- **When** summarise
- **Then** output `{summary: 'Tài liệu không có nội dung text. OCR trước.', bullets: [], reading_time_seconds: 0}`; warning logged

### TC-3 Multi-section structured doc
- **Given** DocSage output có sections (heading hierarchy)
- **When** summarise
- **Then** bullets reflect per-section summaries; reading_time = total

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid VN PDF text | TC-1 |
| **Validation** | document_input null | 422 USR-ERR-422-NODE_CONFIG |
| **Permission** | VIEWER trigger | 403 |
| **Dependency** | LLM 500 | Per-item degraded entry, KHÔNG abort run |

## 3. K-rule invariants

- **K-3** llm-gateway ✓
- **K-4** Default Qwen local
- **K-6** decision_audit_log + mig 098
- **K-17** read_only
- **K-19** OTel span

## 4. Performance

| NFR | Target |
|---|---|
| NFR-P-05 LLM call P99 | <5s |
| Reading_time accuracy ±10% vs human estimate | manual sample 20 docs |

## 5. UAT execution checklist

- [ ] Setup 5 sample VN documents: contract, report, invoice, CV, email thread
- [ ] Trigger summarise per doc → verify summary VN + bullets + reading_time
- [ ] Verify "OCR trước" hint cho image-only doc
- [ ] Reading-time accuracy: anh read manually 20 docs, compare estimate vs actual

---

*UAT ID: UAT-SUMMARISE-001 · Owner QA Lead*
