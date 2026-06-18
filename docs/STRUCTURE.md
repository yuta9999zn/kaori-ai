# Project Structure — Kaori AI v4

> Tách từ `CLAUDE.md` §3 ngày 2026-05-22. Đọc khi cần cây thư mục đầy đủ.

```
D:\Kaori System\
├── CLAUDE.md                          ← living doc (slim version)
├── docker-compose.yml                 ← Phase 1 dev stack
├── .env.example                       ← Vault rotation Phase 1.5
├── docs/
│   ├── README.md                      ← navigation index (v4 reset 2026-05-08)
│   ├── BACKLOG_V4.md                  ← canonical 1147-feature catalog ★
│   ├── API_CATALOG_V4.md              ← 169 endpoints + 42 deps ★
│   ├── GAPS_V4.md                     ← code hiện tại vs v4
│   ├── RESTRUCTURE_PROPOSAL.md        ← Phase A/B/C migration path
│   ├── SPRINT_HISTORY.md              ← lịch sử §14 (mới tách 2026-05-22)
│   ├── STRUCTURE.md                   ← file này
│   ├── MODULE_MAP.md                  ← §14a/14b/14c module map
│   ├── HOWTO.md                       ← §12 Adding New Features
│   ├── architecture/
│   │   └── EVENT_BACKBONE.md          ← §7 Kafka + Redis Streams chi tiết
│   ├── strategic/                     ← 5 source-of-truth docs (docx → MD) ★★★
│   │   ├── SAD_SKELETON_V2.md
│   │   ├── PLAYBOOK_90DAY.md
│   │   ├── PIPELINE_UNIFIED.md
│   │   ├── REASONING_LAYER.md
│   │   ├── WORKFLOW_SYSTEM.md
│   │   └── README.md
│   ├── adr/                           ← v3 ADRs (0001-0009) + v4 ADRs (0010-0026)
│   ├── specs/                         ← per-feature contracts (rename to v4 codes lazily)
│   │   ├── UI_SCREENS_INVENTORY.md    ← ★ FE: 77 screens × 6 portals (P1-P6)
│   │   ├── MESSAGE_DEFINITIONS.md     ← ★ FE: SYS-ERR* + USR-ERR* + BIZ-ERR + RFC 7807
│   │   ├── VALIDATION_RULES.md        ← ★ FE+BE: per-field input constraints
│   │   └── CHAT_TOOL_REGISTRY_V4.md   ← MCP JSON-RPC 2.0 mapping
│   ├── ba/                            ← BA mirror (URD + NFRS + CR Register)
│   ├── runbooks/                      ← ops playbooks (+ v4: temporal-down, dlq-flooding, vault-rotation, ck-replication-lag, workflow-execution-enable, sso-microsoft-setup)
│   ├── api-specs/                     ← committed OpenAPI snapshots
│   ├── sprint/                        ← active sprint artefacts (acceptance + plans + checklists)
│   │   ├── feature-screens.html       ← 77 screen inventory
│   │   ├── feature-workflows.html     ← 40 workflow internal catalog
│   │   ├── workflow-builder-ux.html   ← SME UX mockup
│   │   ├── PHASE_2_6_DEFER_QUEUE.md
│   │   └── PHASE_2_8_FE_IMPL_SPEC.md
│   ├── product/                       ← BRD/PRD/Feature Tree source (.docx/.xlsx) — gitignored
│   ├── uat/                           ← UAT scripts per feature (19 scripts P2.5/2.6/2.7 + Priority 4)
│   ├── perf/                          ← performance benchmarks
│   ├── _v4_extract/                   ← raw JSON dump 25 Excel sheets
│   └── archive/                       ← history: v3 trackers + BACKLOG_v3 + CLAUDE_v2.5.0 + architecture-v3/ + closed sprint folders + specs-v3/CHAT_TOOL_REGISTRY.md + PHASE1_V4_CLOSEOUT.md
├── services/
│   ├── api-gateway/                   ← Java SCG (8080)
│   ├── auth-service/                  ← Java Spring Boot (8091)
│   ├── data-pipeline/                 ← Python FastAPI (8092) — Phase B internal split
│   │   ├── ingestion/                 ← (Phase B) 8 connectors P1-S3
│   │   ├── data_plane/{bronze,silver,gold}/  ← (Phase B)
│   │   └── quality/                   ← (Phase B) 7-dim scorecard
│   ├── ai-orchestrator/               ← Python FastAPI (8093) — Phase B internal split
│   │   ├── reasoning/                 ← (Phase B) L3 — Insight + Recommendation + Constraint + Formula + Criteria + RAG + Profile
│   │   ├── workflow_runtime/          ← (Phase B) L4 Temporal worker P1-S6
│   │   ├── org_intel/                 ← (Phase B) L4.5 — process_mining/, adoption/, economics/
│   │   ├── analytics/                 ← keep (template_registry)
│   │   ├── chat/                      ← keep (Sprint 8 v3 tool registry; relabel `P2-M210-*` Phase 2)
│   │   ├── consumers/                 ← keep
│   │   └── shared/
│   ├── llm-gateway/                   ← Python FastAPI (8095); ADR-0015 Qwen primary
│   ├── notification-service/          ← Python FastAPI (8094)
│   └── (process-mining/, adoption-intel/, economics/, workflow-engine/  ← Phase 3 extract skeleton; ADR-0010 updated 2026-05-18)
├── frontend/                          ← Next.js 16 — TẠM DỪNG, anh restructure trước
├── infrastructure/
│   ├── postgres/migrations/           ← Flyway-managed since auth-service Phase 3 (100 .sql files as of 2026-05-21)
│   ├── kafka/                         ← legacy topic
│   ├── redis/                         ← + Streams config Phase 1
│   ├── ollama/                        ← Qwen + BGE-M3 + Qwen2-VL OCR
│   ├── temporal/                      ← (Phase B) docker-compose dev + Helm Phase 1.5
│   ├── clickhouse/                    ← (Phase B) schemas + Helm
│   ├── minio/                         ← (Phase B) docker-compose dev
│   ├── vault/                         ← (Phase B) policies/
│   ├── otel/                          ← (Phase B) collector + Jaeger
│   ├── prometheus/                    ← (Phase B)
│   ├── loki/                          ← (Phase B)
│   ├── grafana/dashboards/            ← (Phase B) SLI/SLO dashboards (OBS-020)
│   └── k8s/                           ← (Phase 1.5+) Helm charts FPT Cloud
├── scripts/
│   ├── dump_openapi.py                ← OpenAPI regen orchestrator + pipeline
│   ├── check_cr_compliance.py         ← PR commit CR-#### enforce (N8 governance)
│   ├── check_ba_sync.py               ← Tài liệu dự án ↔ docs/ba/ drift detect
│   └── openapi_precommit_hook.sh      ← regen on routers/ stage
├── config/
│   ├── language_dictionary.json       ← 5-lang column synonyms
│   └── bank_rules.json
└── etl/ · utils/ · sql/               ← legacy scripts (kept, reused)
```

Trạng thái: ✅ chạy · 🔵 skeleton hoặc planned · ⏸ paused · ❌ deprecated.
