# UAT — F-MINERU (MinerU OCR + Document Pattern Extraction)

> **Function:** Phase 2.5 MinerU pattern-borrow (NOT lib) — 4 patterns from `opendatalab/MinerU` ported in <750 LOC
> **Portal:** P2 Enterprise (Stage 6 Knowledge Extraction pipeline)
> **Service:** data-pipeline (`data_plane/silver/blocks.py` + `table_extractor.py` + `header_footer_strip.py` + `reading_order.py` + `ocr_client.py`) + llm-gateway (`/v1/ocr` Qwen2-VL local)
> **DB:** Catalog migs 085 (block taxonomy + tables + reading order) — no separate mig for patterns themselves
> **Owner:** QA Lead + Data Analyst
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ADR-0025 ship)

| Pattern | Module | Ship commit |
|---|---|---|
| 1. Block taxonomy + header/footer strip | `blocks.py` + `header_footer_strip.py` | `25e82be` + `7dfa2b1` (detect wire-in spoof guard) |
| 2. pdfplumber tables → TABLE blocks (markdown+html+rows metadata) | `table_extractor.py` | `34afe4b` |
| 3. Multi-column reading order (X-histogram bimodality) | `reading_order.py` | `be6867a` |
| 4. OCR Qwen2-VL adapter `/v1/ocr` local-only K-4 schema-enforced | `ocr_client.py` + llm-gateway | `1c4667c` |
| 5. Bbox foundation (Pattern 5) | Bbox dataclass + propagation | `e0ce848` + `8bb944c` |

ADR-0025 rationale: AGPL-3.0 incompatible → port instead of vendor.

Tests pass: `tests/test_blocks.py` 14/14, `test_table_extractor.py` 18/18, `test_reading_order.py` 12/12, `test_ocr_client.py` 16/16.

---

## 1. Test scenarios

### TC-1 Happy path (PDF với tables + multi-column)
- **Given** Bronze PDF có 2-column layout + 3 tables + header/footer repeat
- **When** Stage 6 Knowledge Extraction runs
- **Then** output Block list: TEXT blocks reordered (left col first then right col); TABLE blocks có `markdown + html + rows` metadata + bbox; header/footer stripped; bbox on TABLE (TEXT bbox=None Pattern 5 v0)

### TC-2 OCR escape hatch cho image PDF
- **Given** Bronze JPG/PNG (image-only, no text layer)
- **When** ingestor detect via magic-byte → escape hatch promote OCR'd
- **Then** `/v1/ocr` qwen2.5vl:7b local → text content + confidence; pre-flight gates skip if empty/oversize/non-image; K-4 schema enforced (no consent_external on OcrRequest, pinned by test)

### TC-3 Spoof guard (renamed extension)
- **Given** file `contract.pdf` but magic byte = PNG (renamed)
- **When** ingestor detect
- **Then** detected_kind=PNG authoritative; ext fallback only on UNKNOWN; promote OCR path automatic

### TC-4 Pattern 4 valley-tie midpoint (regression test)
- **Given** 2-column page với X-histogram valley có 2 equal-min bins
- **When** reading order Pattern 4
- **Then** midpoint = avg of valley bins (NOT leftmost — em đã fix bug Pattern 4 dev session)

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid PDF | TC-1 |
| **Validation** | Empty/oversize/non-image to /v1/ocr | Pre-flight gate skips gateway call, returns empty result |
| **Permission** | None — Stage 6 system-level, all roles can trigger upload | N/A |
| **Dependency** | Ollama Qwen2-VL down | OCR returns empty + warning; ingestor escape hatch fails gracefully — caller queue widens |

## 3. K-rule invariants

- **K-2** Bronze append-only ✓ (OCR doesn't modify Bronze)
- **K-4** OCR endpoint REFUSES `consent_external` entirely (schema-level pin via test); vendor vision = Phase 3 + separate ADR
- **K-5** PII not in OCR'd text (text byte-level redaction can't strip; vendor vision impossible per K-4)
- **K-17** OCR = external (Qwen2-VL local Ollama); patterns 1-4 = PURE
- **K-19** OTel span per pattern + per OCR call

## 4. Performance

| NFR | Target |
|---|---|
| NFR-P-12 OCR 1 trang A4 P1 | <8s |
| NFR-P-12 OCR 1 trang A4 P3 | <4s |
| Pattern 3 tables (10 tables / 100 pages) | <5s pdfplumber |
| Pattern 4 reading order (100 pages) | <2s (single-col pages skip = zero cost) |

## 5. UAT execution checklist

- [ ] Setup 5 sample PDFs: 1 simple text · 1 multi-column · 1 with tables · 1 scanned image-only · 1 with header/footer repeat
- [ ] Run Stage 6 pipeline per sample → verify blocks output
- [ ] OCR test: image-only sample → verify Qwen2-VL local extracts VN text
- [ ] Spoof guard test: rename .png → .pdf, upload → verify detected_kind=PNG correct
- [ ] Performance: 100-page document → verify NFR-P-12 OCR latency

---

*UAT ID: UAT-MINERU-001 · Owner QA Lead*
