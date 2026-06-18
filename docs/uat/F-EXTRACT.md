# UAT — F-EXTRACT (AI Node: Structured Data Extraction)

> **Function:** Phase 2.5 AI node `extract_structured_data` — per-table LLM extract VN/EN
> **Portal:** P2 Enterprise (workflow card execution)
> **Roles allowed:** Workflow trigger any role; config edit ANALYST+
> **Service:** ai-orchestrator (`reasoning/structured_extractor.py`) → llm-gateway
> **DB:** Catalog mig 085; output có provenance (page + block_id from MinerU blocks)
> **Owner:** QA Lead + Data Analyst
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ship `2792f21`)

| Surface | Purpose |
|---|---|
| `reasoning/structured_extractor.py` | Per-TABLE LLM call → typed rows với provenance (page index + block_id) |
| Catalog row mig 085 | `extract_structured_data` registered |
| Pattern | Per-table failure isolated — 1 fail không abort run |

Tests pass: `tests/test_structured_extractor.py` 12/12 (incl. TABLE blocks chunking + bbox propagation).

---

## 1. Test scenarios

### TC-1 Happy path (extract 3 tables từ PDF hoá đơn)
- **Given** Bronze PDF (post MinerU Pattern 3 table extraction) có 3 TABLE blocks; schema `{invoice_no: text, amount_vnd: numeric, issued_date: date}`
- **When** workflow run extract_structured_data card
- **Then** output 3 row sets với provenance: each row có `{page: N, block_id: bblk-XYZ, bbox: {x0,top,x1,bottom}}`; persisted; lineage walk upstream → bronze_file

### TC-2 Per-table failure isolated
- **Given** 5 TABLE blocks; LLM call fails on block 3 (schema mismatch)
- **When** run
- **Then** output 4 row sets (blocks 1,2,4,5) + 1 degraded entry `{block_id: 3, error: 'schema_mismatch', skipped: true}`; run NOT aborted; warning + manual queue widens

### TC-3 OCR'd image table
- **Given** Bronze JPG (post OCR Qwen2-VL `/v1/ocr` K-4 local-only) → TABLE block via OCR
- **When** extract
- **Then** rows extracted với confidence chip; bbox=None for OCR'd (Pattern 5 v0 limitation, không phải bug)

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid PDF + schema | TC-1 |
| **Validation** | schema field type invalid (e.g. `{amount: 'banana'}`) | 422 USR-ERR-422-NODE_CONFIG |
| **Permission** | VIEWER trigger | 403 |
| **Dependency** | MinerU patterns chưa extract table (no TABLE blocks) | Output empty array + warning "no_tables_in_document" |

## 3. K-rule invariants

- **K-3** llm-gateway ✓
- **K-4** Default Qwen local; vendor opt-in
- **K-6** audit per-table call mig 098
- **K-17** read_only
- **K-19** OTel span per-table extract

## 4. Performance

| NFR | Target |
|---|---|
| Per-table extract P99 | <8s |
| Multi-table batch (5 tables) | <30s parallel |

## 5. UAT execution checklist

- [ ] Setup PDF hoá đơn VN có 3 bảng (or use sample `samples/invoice_vn_3tables.pdf`)
- [ ] Trigger workflow extract → verify rows + provenance pointing to correct page+block
- [ ] Test schema strict mode (extra fields rejected) vs lenient mode
- [ ] Verify per-table failure isolation: corrupt block 3 → 4/5 rows still extracted

---

*UAT ID: UAT-EXTRACT-001 · Owner QA Lead*
