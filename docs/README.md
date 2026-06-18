# Kaori AI — Docs Index

> Navigation map for `docs/`. Read this first.
> Last reorganized: **2026-05-17** (Phase 1.5 closeout cleanup — sprint artefacts archived, v3 architecture + v3 tasks moved to `archive/`); 2026-06-03 EU AI Act compliance landed (ADR-0041, K-22..K-26, migs 134-136); 2026-06-04 docs indices added (`adr/README.md` backfilled to 0041, new `uat/README.md` + `audit/README.md` + `K_RULES_INDEX.md`)
> Prior reset: 2026-05-08 (v4.0 — Feature Tree v4.0 onboarded; v3 trackers archived)

---

## What changed 2026-05-08 — v4.0 reset

Anh đã chốt lại scope hệ thống bằng 6 tài liệu mới ở `D:\Kaori Document\` (Feature Tree v4.0 + 5 strategic docs). v4 không phải nâng cấp tiệm tiến — nó **redesign nền tảng** (24 tháng × 36 sprint × 1147 features × kiến trúc Kubernetes + Temporal + ClickHouse + MinIO + Vault + OTel + 8 connectors VN + 3 module mới).

Phase 1 v3 + Phase 2 Sprint 2.1+2.2 đã ship — code đó vẫn giữ, được relabel sang mã v4 (xem `GAPS_V4.md` §3). Tracker và backlog v3 đã chuyển sang `archive/`.

---

## Reading priority

### 🚨 Đọc TRƯỚC khi code (mới onboard hoặc bắt đầu sprint v4)

- [`strategic/SAD_SKELETON_V2.md`](./strategic/SAD_SKELETON_V2.md) — kiến trúc tổng thể v4. Bắt đầu từ Part I-II.
- [`strategic/README.md`](./strategic/README.md) — navigation cho 5 strategic docs.
- [`GAPS_V4.md`](./GAPS_V4.md) — code hiện tại vs v4: cái gì giữ, cái gì restructure, K-rules cập nhật.
- [`RESTRUCTURE_PROPOSAL.md`](./RESTRUCTURE_PROPOSAL.md) — Phase A/B/C migration path.

### 📌 Daily (khi code Phase 1 v4)

- [`BACKLOG_V4.md`](./BACKLOG_V4.md) — canonical sprint catalog (1147 features, 36 sprints). Tick status khi ship.
- [`API_CATALOG_V4.md`](./API_CATALOG_V4.md) — 169 REST endpoints + 42 dependency edges.
- `CLAUDE.md` (root) — project instructions, K-rules, tech stack pinning, sprint status.

### 📖 Per-layer (khi đụng layer cụ thể)

- [`strategic/PIPELINE_UNIFIED.md`](./strategic/PIPELINE_UNIFIED.md) — L1-L2 (12-stage data pipeline)
- [`strategic/REASONING_LAYER.md`](./strategic/REASONING_LAYER.md) — L3 (8-dim profile, criteria registry, RAG 4-tier)
- [`strategic/WORKFLOW_SYSTEM.md`](./strategic/WORKFLOW_SYSTEM.md) — L4 + L4.5 (45 nodes, Process Mining moat, Adoption, NOV)
- [`strategic/PLAYBOOK_90DAY.md`](./strategic/PLAYBOOK_90DAY.md) — operational onboarding (CSM playbook)

### 🏛️ ADRs (khi cần biết "tại sao quyết định thế")

- [`adr/`](./adr/) — Architecture Decision Records.
  - **v4 ADRs (0010-0019):** modular monolith → microservices · Temporal · Postgres+ClickHouse · RLS multi-tenancy · at-least-once + idempotency · Qwen-first LLM with pluggable vendor adapters · VN hosting · Redis Streams Phase 1 · pluggable bot adapter (Telegram default) · vectorless tree retrieval (PageIndex) + structured SQL reasoning (DocSage) for RAG
  - **v3 ADRs (0001-0009):** giữ làm history.

### 📕 Per-feature deep-dive

- [`specs/`](./specs/) — per-feature contracts (Pipeline V5 medallion, cleaning rules, chart registry, decision quality, multi-language file). Một số spec sẽ được rename sang mã v4 khi sửa lần tới (lazy migration).

### 🛠️ Operational / runtime

- [`runbooks/`](./runbooks/) — kafka lag, redis OOM, llm-gateway down, AI cost overrun, temporal-down, dlq-flooding, vault-rotation, clickhouse-replication-lag, telegram-bridge, slo-burn-rate.
- [`api-specs/`](./api-specs/) — committed OpenAPI specs. CI gates trên `dump_openapi.py --check`.
- [`uat/`](./uat/) — UAT scripts per feature.
- [`sprint/`](./sprint/) — active sprint artefacts (P1-S*_ACCEPTANCE, current resume checklist, BUILD_WEEK_*). Closed-sprint plans/reviews moved to `archive/sprint/`.

### 📦 Source documents

- [`../`(repo root)](../) — `D:\Kaori Document\` chứa docx/xlsx gốc, KHÔNG checkin (lý do: bí mật + binary). MD versions trong `strategic/` được sync lại từ docx.

### ⛔ Archive (history only)

- [`archive/`](./archive/) — history. v3 trackers + `BACKLOG_v3.md` + v3 phase plans + `CLAUDE_v2.5.0.md` snapshot + `PHASE1_V4_CLOSEOUT.md` (closed 2026-05-08) + `architecture-v3/` (v3 SAD) + `sprint/{p15-s9,p15-s10,resume-checklists}/` (closed sprint artefacts) + `specs-v3/CHAT_TOOL_REGISTRY.md` (superseded by V4 spec).

---

## Folder layout

```
docs/
├── README.md                       ← you are here
├── BACKLOG_V4.md                   ← canonical sprint catalog (v4, 1147 features)
├── API_CATALOG_V4.md               ← 169 endpoints + 42 deps (v4)
├── GAPS_V4.md                      ← code hiện tại vs v4 architecture
├── RESTRUCTURE_PROPOSAL.md         ← migration path Phase A/B/C
├── DEMO_RUNBOOK.md                 ← pilot UAT script (Olist)
├── HOW_TO_RUN_PILOT.md             ← anh-driven local pilot guide
├── PILOT_SEED.md                   ← Olist seed data ref
├── strategic/                      ← 5 strategic docs converted from docx ★
│   ├── README.md, SAD_SKELETON_V2, PLAYBOOK_90DAY, PIPELINE_UNIFIED,
│   ├── REASONING_LAYER, WORKFLOW_SYSTEM
│   ├── CDFL_INTEGRATION.md          ← descriptive framework port (ADR-0020)
│   └── RAG_ADDENDUM_2026_05.md      ← RAG router + PageIndex + DocSage addendum
├── adr/                            ← Architecture Decision Records (0001-0020)
├── specs/                          ← per-feature contracts (16 docs; CHAT_TOOL_REGISTRY_V4, MEDALLION_CONTRACT, UI_SCREENS_INVENTORY, MESSAGE_DEFINITIONS, VALIDATION_RULES, RAG_VECTORLESS_AND_STRUCTURED, …)
├── runbooks/                       ← 11 ops playbooks
├── api-specs/                      ← committed OpenAPI snapshots
├── sprint/                         ← active sprint artefacts (acceptance, resume checklist, build-week prep)
├── product/                        ← BRD/PRD .docx + Feature Tree .xlsx (gitignored)
├── uat/                            ← UAT scripts per feature (15 docs)
├── _v4_extract/                    ← raw JSON dump of 25 Excel sheets (regen MD source)
└── archive/                        ← history (do NOT edit; for reference only)
    ├── BACKLOG_v3.md, kaori-mvp-spec.md, CLAUDE_v2.5.0.md
    ├── PHASE1_CLOSEOUT_PLAN.md, PHASE2_PLAN.md, phase_{1,2,3}_execution.md
    ├── PHASE1_V4_CLOSEOUT.md          ← Phase 1 v4 closed 2026-05-08 (tag v4.0-phase1-complete)
    ├── BACKEND_TASKS_PHASE.md, FRONTEND_TASKS_PHASE.md  ← v3 task scope (BACKLOG_V4 replaces)
    ├── architecture-v3/               ← v3 SAD: ARCHITECTURE_REVIEW + SCALE_PLAN + TARGET_ARCHITECTURE_1M
    ├── specs-v3/CHAT_TOOL_REGISTRY.md ← v3 chat spec (V4 wrapper in active specs/)
    └── sprint/
        ├── p15-s9/                    ← P15-S9 PLAN + REVIEW + CI_BACKLOG + PR_BODY
        ├── p15-s10/                   ← P15-S10 PLAN + REVIEW
        └── resume-checklists/         ← JUNE_2026 + BUILD_WEEK_NEXT_SESSION (superseded by P2_S15_RESUME)
```

---

## Source-of-truth rules

| Câu hỏi | Trả lời ở đây |
|---|---|
| Sprint v4 nào, feature nào, status gì? | `BACKLOG_V4.md` |
| API nào tồn tại, endpoint contract? | `API_CATALOG_V4.md` + `api-specs/*.openapi.json` |
| Tech stack, K-rules, project structure? | `CLAUDE.md` (root) |
| Kiến trúc tầng X chi tiết? | `strategic/<layer-doc>.md` (xem strategic/README.md) |
| Tại sao quyết định kỹ thuật Y? | `adr/00XX-*.md` |
| Spec chi tiết feature Z? | `specs/*.md` |
| Onboarding khách hàng D-7 → D90? | `strategic/PLAYBOOK_90DAY.md` |
| Pilot Olist anh chạy laptop? | `HOW_TO_RUN_PILOT.md` + `PILOT_SEED.md` + `DEMO_RUNBOOK.md` |
| F-001..F-092 cũ map sang mã v4? | `GAPS_V4.md` §3 |

Khi 2 doc disagreed: **`docs/strategic/*.md` win cho kiến trúc**; **`BACKLOG_V4.md` win cho status feature**; **docx ở `D:\Kaori Document\` win nếu khác MD strategic**.

---

## Tại sao reset 2026-05-08 (v4.0)

Trước: BACKLOG.md có 92 functions (F-001..F-092), Phase 1+2 đã ship, Phase 2 Sprint 2.1+2.2 close. Tracker phù hợp với scope v3.

Sau: Anh đưa ra 6 tài liệu mới (Feature Tree v4.0 + Playbook + Pipeline + Reasoning + Workflow + SAD v2). v4 mở rộng scope ra 24 tháng × 36 sprint × 1147 features và đổi nền tảng (K8s + Temporal + ClickHouse + ...). Code v3 đã ship vẫn dùng (cover ~30-40% mặt feature) nhưng cần restructure folder + onboard 3 module mới (Process Mining, Adoption Intel, NOV).

`docs/archive/` lưu state v3 — không xóa, chỉ chuyển. Nếu cần ref pilot Olist vẫn xem được.

Migration path: `RESTRUCTURE_PROPOSAL.md` Phase A (docs) → Phase B (code restructure) → Phase C (Sprint 1 v4).
