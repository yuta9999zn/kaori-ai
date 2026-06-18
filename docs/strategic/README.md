# `docs/strategic/` — Source-of-truth strategic documents

These 5 documents are the canonical reference for what Kaori AI is, how it's organised, and how it grows over 24 months. They're MD conversions of the docx originals at `D:\Kaori Document\` (kept in sync as anh updates them).

Every other doc in `docs/` derives from these. When in doubt, **strategic docs win**.

## Reading order

| # | File | What it answers | Read when |
|---|---|---|---|
| 0 | `SAD_SKELETON_V2.md` | "What does Kaori look like as a whole system?" Layer 0-5, polyglot persistence, Temporal, K8s, ClickHouse, MinIO, Vault, OTel — plus 7 master ADRs and Phase 1→3 roadmap. | First thing for anyone joining. |
| 1 | `PLAYBOOK_90DAY.md` | "How does a customer go from D-7 to D90?" Pre-launch handoff, week-by-week onboarding, 5 archetypes, AI quality framework, pricing quotas, Studio collab, enterprise health state machine. | When working on CSM flow, onboarding UX, archetype-aware features. |
| 2 | `PIPELINE_UNIFIED.md` | "What happens to data from upload to insight?" 12 stages: Upload → Bronze → Schema Detection → Cleaning/Silver → Quality Gate → Semantic Enrichment → Knowledge Extraction → Memory → Gold → AI Decision → Reports → Loop. | When working on L1 (ingestion) or L2 (data plane). |
| 3 | `REASONING_LAYER.md` | "How does the AI brain reason?" 8-dimensional business profile, dynamic criteria registry with lifecycle, source authority hierarchy, 4-tier RAG, conflict resolution, tenant-custom criteria. | When working on L3 (reasoning, insight, recommendation, constraint). |
| 4 | `WORKFLOW_SYSTEM.md` | "How are workflows built, executed, and discovered?" 45 node types in 6 categories, 8 workflow states, 60-day baseline + 90-day testing, **Process Mining (the moat)** with 8 sources + Heuristic Miner + bypass detection, **Adoption Intelligence** (9 signals + intervention), **NOV / Operational Economics**, Workflow as Code (YAML). | When working on L4 (workflow engine), L4.5 (org intel), saga, idempotency, DLQ. |

## How they connect

```
SAD_SKELETON_V2 (master architecture)
        │
        ├── L1-L2 details → PIPELINE_UNIFIED
        ├── L3 details   → REASONING_LAYER
        ├── L4 + L4.5    → WORKFLOW_SYSTEM
        └── operational  → PLAYBOOK_90DAY
```

`SAD_SKELETON_V2` references the other 4 in its bibliography; the other 4 zoom into one slice each. Don't deep-dive a layer doc until you've read SAD Part I-II first.

## Where the source-of-truth lives

The MD files here are converted from `D:\Kaori Document\` docx. **Anh edits the docx**, then runs the conversion script to refresh MDs. Conversion command (when needed):

```bash
# from repo root
python scripts/convert_strategic_docs.py
```

(Script TBD in Phase A — currently the conversion was done one-off via `python -c` with `python-docx` on 2026-05-08.)

If a docx and an MD disagree, **the docx is canonical**. Open a PR to refresh the MD.

## Versions

| Doc | Source filename | Source version | Snapshot date |
|---|---|---|---|
| Playbook 90-day | `1Kaori_90day_Playbook_v3_Unified.docx` | v3 Unified | 2026-05-07 |
| Pipeline Unified | `2Kaori_Pipeline_Unified.docx` | v1.1 | 2026-05-07 |
| Reasoning Layer | `3Kaori_AI_Reasoning_Layer.docx` | v4.0 | 2026-05-07 |
| Workflow System | `4Kaori_AI_Workflow_System.docx` | v2.0 | 2026-05-07 |
| SAD Skeleton | `5Kaori_AI_SAD_Skeleton_v2.docx` | v2.0 | 2026-05-07 |

## Related files in this repo

- `docs/strategic/NNL_SELFDISCOVERY_REASONING_ROADMAP.md` — **working roadmap** (không phải canonical): port self-discovery (CR-0016: hướng ngày + line-total, no-hardcode) + reasoning convergence (CDFL grounding · học-1-hiểu-10 · kho tri thức ngành) từ prototype local vào production. Done/backlog + điểm-sửa code-level.
- `docs/BACKLOG_V4.md` — sprint-by-sprint feature catalog derived from `Kaori_AI_Feature_Tree_v4_0.xlsx`.
- `docs/API_CATALOG_V4.md` — 169 REST endpoints + 42 dependency edges from same Excel.
- `docs/GAPS_V4.md` — gap analysis: current code vs v4 architecture.
- `docs/RESTRUCTURE_PROPOSAL.md` — migration path from v3 codebase to v4.
- `docs/adr/0010-0017-*.md` — v4 architecture decision records (modular monolith → microservices, Temporal, polyglot persistence, RLS, idempotency, Qwen-first LLM with pluggable vendor adapters, VN hosting, Redis Streams).
- `docs/_v4_extract/*.json` — raw dump of all 25 Excel sheets (regenerate MDs from these).
