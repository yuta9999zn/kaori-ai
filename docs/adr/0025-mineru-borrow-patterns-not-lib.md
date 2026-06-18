# ADR-0025 — Borrow MinerU patterns, do NOT vendor the library

> **Status:** accepted
> **Date:** 2026-05-19
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0021 (T-Cube trace-augmented reasoning) · ADR-0024 (Mem0 patterns into Stage 7 — same model) · `opendatalab/MinerU` (AGPL-3.0) · `services/data-pipeline/data_plane/silver/{blocks,header_footer_strip,table_extractor,reading_order}.py` · CLAUDE.md §14 P2.5 row + §14c module map

## Context

`opendatalab/MinerU` (公司开源团队 2024-2026) is the best-in-class open-source PDF/Office layout-aware parser. It ships a `Block` taxonomy + reading-order + bbox extraction + content-list schema that aligns 1-to-1 with what DocSage Schema Discovery, AI-node prompts, FE citation highlighting, and downstream RAG citation want from Stage 6.

We faced two genuine choices when designing Phase 2.5 Stage 6 unstructured extraction:

1. **Vendor MinerU**: take the library as a runtime dependency, send PDF bytes through its pipeline, consume its JSON output.
2. **Borrow patterns**: read MinerU's content schema + algorithm sketches, then implement pure-Python ports inside `services/data-pipeline/data_plane/silver/`.

Forces in tension:

| Pulling us toward **vendor** | Pulling us toward **borrow** |
|---|---|
| Faster: skip implementing 4 patterns | License: MinerU is **AGPL-3.0**; vendoring forces our entire SaaS surface AGPL or proves a clean SaaS exception per customer contract (legal hates this) |
| MinerU has battle-tested OCR + DocLayout-YOLO + UniMERNet weights for math/tables | Model weights are 6+ GB total; ship size + cold-start time bad for 16 GB pilot box ([[project-pilot-deployment]]) |
| Active project, regular releases | Heavy dep tree (torch + transformers + paddle + opencv); pip resolve already painful, this would dominate |
| Vietnamese OCR works decently | Em already need Qwen2.5-VL via Ollama for /v1/ocr (Phase 2.5 OCR adapter ship); MinerU's OCR is duplicate path |
|   | Pattern surface is small (4 patterns × <300 LOC each ports); ROI of full vendor lib doesn't justify the lock-in |
|   | Same model already accepted for Mem0 → Stage 7 (ADR-0024); precedent set |

The decision is structurally identical to ADR-0024 (Mem0). Em consider this ADR a sibling: same trade-offs, same conclusion, different upstream library.

## Decision

**We borrow the MinerU pattern schema + algorithm ideas but ship pure-Python ports inside `services/data-pipeline/data_plane/silver/`.** No MinerU package goes into `requirements.txt`. No MinerU weight files ship in our Docker images. The 4 patterns em ported in Phase 2.5 are:

| Pattern | Em's port | LOC |
|---|---|---|
| 1. Block taxonomy (text/title/list/table/header/footer/page_number/image_ref/caption/code/quote/equation) | `silver/blocks.py` — frozen dataclass + enum mirroring MinerU `content_list` schema | ~110 |
| 2. Header/footer/page-number repeat detection | `silver/header_footer_strip.py` — pure-Python repeat-line heuristic across pages | ~150 |
| 3. PDF table extraction via pdfplumber | `silver/table_extractor.py` — pdfplumber `extract_tables()` + cleanup + markdown/html render | ~200 |
| 4. Multi-column reading order | `silver/reading_order.py` — pdfplumber word-level bbox + X-histogram bimodality + per-column reorder | ~285 |

**Pattern 5 (bbox citation)** is FE-paused — em port when FE restructure resumes.

For OCR specifically em chose **Qwen2.5-VL via Ollama** (Phase 2.5 OCR adapter, commit `1c4667c`) rather than MinerU's bundled OCR. Reuses the existing Ollama runtime already pulled for Qwen2.5:14b. Single vendor surface (Ollama) for both LLM + vision, simpler ops.

## Consequences

### Positive

- **License clarity**: zero AGPL exposure. The 4 pattern files em wrote are MIT-compatible (no copy of MinerU code, only structural ideas + public-schema fields).
- **Pinning**: pdfplumber 0.11.x is a small focused dep already in tree; em control upgrade cadence.
- **Cold-start time + image size**: no 6 GB of model weights in Bronze containers. Pilot box ([[project-pilot-deployment]]) keeps headroom for Qwen2.5:14b.
- **Test surface stays small**: 4 modules × pure-Python tests with no model fixtures. data-pipeline test suite stayed in the seconds at 663 tests.
- **Single vision runtime** (Ollama for both Qwen2.5:14b and Qwen2.5-VL:7b) — one model server, one circuit breaker, one health check.

### Negative / accepted trade-offs

- **Per-pattern catch-up cost**: when MinerU lands a new pattern (e.g. table-structure recognition with TSR-Net), em pay re-port cost vs vendor's get-for-free. Mitigated by the small pattern surface — 4 patterns in ~10 dev-days total.
- **No bbox in Patterns 1+3**: em deferred bbox per-block citation (Pattern 5) until FE consumes it. MinerU gives this out of the box. Em accept the lag.
- **Math + complex tables less accurate**: MinerU UniMERNet on equations + nested tables is genuinely SOTA. Em's pdfplumber + heuristics handle 90% of VN business docs (invoices, contracts, reports, regulations); the 10% (academic papers, complex financial annexes) gets degraded extraction.
- **No DocLayout-YOLO equivalent**: em can't detect "this region is a figure vs sidebar vs body column" the way MinerU's vision model can. Em's column detection (Pattern 4) is X-histogram only.

### Neutral / follow-ups

- **Re-evaluate annually**: if MinerU relicenses (Apache 2.0 / MIT) OR em hit a customer whose docs em can't extract, em revisit. Trigger: ≥5 customer escalations on extraction quality in one quarter.
- **Bbox port (Pattern 5) is owed to FE** when FE restructure resumes. Em author it as part of the FE bbox-highlight surface work, not standalone.
- **Vendor vision adapter (Phase 3)**: when em add Anthropic Vision / GPT-4o Vision per ADR-not-yet-authored, em revisit whether MinerU-bundled OCR ever makes sense. Probably not — vendor vision is for English-heavy specialised content where vendor models beat Qwen2.5-VL; that segment also gets vendor's own layout parsing.

## Alternatives considered

- **Alt 1 — Vendor full MinerU library**. Rejected on AGPL-3.0 license. Even with a SaaS exception clause, em make legal review every pilot contract. Cost compounds.
- **Alt 2 — Vendor MinerU's content-list schema only (no code)**. We did this implicitly — em mirror the schema in `silver/blocks.py`. Schemas aren't copyrightable; this is the "borrow" part.
- **Alt 3 — Use only pdfplumber + own everything**. What em ended up doing for Patterns 2 + 4 (no MinerU equivalent borrowed). Pattern 1 + 3 use pdfplumber under the hood but the schema is MinerU-shaped.
- **Alt 4 — Wait for Phase 3 + ship MinerU vendor as a separate microservice with its own licensing boundary**. Rejected as over-engineering; em'd still need to negotiate the AGPL exception per deployment + maintain a service em barely use.

## References

- `opendatalab/MinerU` GitHub — https://github.com/opendatalab/MinerU
- ADR-0024 (Mem0 pattern-port — structurally identical decision) — `docs/adr/0024-mem0-inspired-ports-into-stage-7-memory.md`
- Phase 2.5 commits: `25e82be` (Patterns 1+2) · `34afe4b` (Pattern 3) · `be6867a` (Pattern 4) · `1c4667c` (OCR Qwen2.5-VL adapter) · `7dfa2b1` (detection + spoof guard wiring)
- CLAUDE.md §14 P2.5 row + §14c module map (introduced commit `e2251fc`)
- 20-case VN business workflow analysis — `docs/strategic/WORKFLOW_USE_CASES.md` (commit `d3d722d`)

---

**Editing note** — ADRs are append-only by convention. If a decision is superseded, set `Status: superseded by ADR-XXXX` here and write the new one. Don't rewrite history; future readers want to see what we believed and when.
