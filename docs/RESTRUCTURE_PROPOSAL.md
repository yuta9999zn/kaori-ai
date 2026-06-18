# Kaori AI — Restructure Proposal (v3 codebase → v4 architecture)

> **Status (updated 2026-05-17):**
> - **Phase A** documentation freeze ✅ COMPLETE — 5 strategic docs + BACKLOG_V4 + API_CATALOG_V4 + GAPS_V4 + 14 ADRs (0010-0024) shipped.
> - **Phase B** internal folder restructure 🟢 PARTIAL — shipped opportunistically during 2026-05-17 marathon. `data-pipeline/{ingestion,data_plane/{bronze,silver,gold},quality}/` split + `ai-orchestrator/{reasoning/{trace_distiller,rag,memory},workflow_runtime,org_intel/{process_mining,adoption,economics,observability},chat,routers}/` split. Service-level extraction (P2-S19/S20) still requires explicit Phase B sign-off — em không tự ý extract.
> - **Phase C** sprint code 🟢 PROGRESSING — Phase 1 v4 ship (8 sprints), Phase 1.5 ship (4 sprints), Phase 2 ~7/12 sprints ship (P2-S13/S14/S15/S16/S18/S21/S25 done; S17 skip Features:0; S19/S20 blocked; S22/S23/S24 not started).
>
> **Originally drafted:** 2026-05-08 (status was DRAFT — em chờ anh confirm)
> **Reads:** `docs/GAPS_V4.md` · `docs/strategic/SAD_SKELETON_V2.md` · `docs/BACKLOG_V4.md`.

---

## 0. Nguyên tắc chỉ đạo (anh đã chốt)

1. **Tạm dừng frontend.** Không touch `frontend/` cho đến khi anh đưa template mới.
2. **Không break pilot Olist.** Branch v4 phải tách bạch; pilot tiếp tục chạy trên `main`.
3. **Tài liệu trước, code sau.** Anh review docs xong em mới migrate.
4. **Modular monolith Phase 1, microservices Phase 2.** SAD ADR-001 — em theo đúng.
5. **Vietnam-native.** FPT/Viettel hosting, Zalo/Misa/Fast first-class, VND, VN.
6. **Reuse code v3 đã ship.** Không vứt, chỉ relabel + relocate.

---

## 1. Branching strategy

```
main               ← pilot Olist + Phase 2 Sprint 2.1+2.2 (frozen, hotfix-only)
└── feat/f-061-...  (current branch — agent framework, sẽ merge sau)
└── docs/v4-reset    ← step 0: chỉ docs, không code change
└── feat/v4-restructure  ← step 4-5: rename folders + skeleton services
└── feat/v4-p1-s1    ← step 5: code Sprint 1 (P1-S1)
└── feat/v4-p1-s2    ← Sprint 2 ...
```

Mỗi sprint v4 = 1 branch + 1 PR (theo convention hiện tại). PR description tham chiếu sprint ID `P1-Sx`.

---

## 2. Folder restructure (không phá API hiện tại)

### 2.1 Đổi tên & gom docs (Step 1-2)

```
docs/
├── CLAUDE.md                    ← rewrite v3.0 (giữ K-1..K-16, thêm K-17..K-20)
├── README.md                    ← cập nhật navigation v4
├── BACKLOG_V4.md                ← canonical backlog (đã tạo, 1147 features)
├── API_CATALOG_V4.md            ← 169 endpoints (đã tạo)
├── GAPS_V4.md                   ← gap analysis (đã tạo)
├── RESTRUCTURE_PROPOSAL.md      ← file này
├── strategic/                   ← 5 doc gốc converted MD (đã tạo)
│   ├── PLAYBOOK_90DAY.md
│   ├── PIPELINE_UNIFIED.md
│   ├── REASONING_LAYER.md
│   ├── WORKFLOW_SYSTEM.md
│   ├── SAD_SKELETON_V2.md
│   └── README.md                ← navigation cho 5 doc
├── adr/
│   ├── 001-modular-monolith-to-microservices.md   ← NEW
│   ├── 002-temporal-for-workflow.md                ← NEW
│   ├── 003-postgres-clickhouse-polyglot.md         ← NEW
│   ├── 004-rls-multi-tenancy.md                    ← NEW (formalize cũ)
│   ├── 005-at-least-once-idempotency.md            ← NEW
│   ├── 006-anthropic-first-llm.md                  ← NEW (đảo Qwen-first)
│   ├── 007-fpt-viettel-vn-hosting.md               ← NEW
│   └── (existing v3 ADRs)                           ← giữ history
├── runbooks/                    ← bổ sung temporal-down, dlq-flooding, vault-rotation, ck-replication-lag
├── specs/                       ← rename per-feature theo mã mới v4 (lazy: chỉ rename khi sửa)
├── api-specs/                   ← refresh OpenAPI cho service mới
├── tasks/                       ← BACKEND/FRONTEND tasks per sprint
├── uat/                         ← UAT scripts giữ
└── archive/
    ├── BACKLOG_v3.md            ← move from BACKLOG.md
    ├── PHASE1_CLOSEOUT_PLAN.md  ← move
    ├── PHASE2_PLAN.md           ← move
    └── (existing archive)
```

### 2.2 Restructure `services/` (Step 4)

Phase 1 vẫn modular monolith — folder split nội bộ, KHÔNG tách container.

```
services/
├── api-gateway/              ← giữ Java SCG (port 8080); ADR rationale
├── auth-service/             ← giữ Java (port 8091)
├── data-pipeline/            ← Python FastAPI (8092) — RESTRUCTURE INTERNAL:
│   ├── ingestion/            ← NEW — 8 connectors P1-S3
│   │   ├── connectors/
│   │   │   ├── postgres_cdc/
│   │   │   ├── excel_filesystem/
│   │   │   ├── zalo_metadata/
│   │   │   ├── gmail_imap/
│   │   │   ├── misa/
│   │   │   ├── fast/
│   │   │   ├── generic_api/
│   │   │   └── webhook/
│   │   ├── normalizer.py     ← common event log schema
│   │   └── pii.py            ← PM-PII-009..012
│   ├── data_plane/           ← bronze/silver/gold reorganized
│   │   ├── bronze/           ← move existing bronze/* (MinIO sink Phase 1.5)
│   │   ├── silver/           ← rule_catalog + ClickHouse writer Phase 1.5
│   │   └── gold/             ← move existing gold_aggregator.py
│   ├── quality/              ← NEW — 7-dim scorecard (Pipeline Stage 4)
│   │   ├── dimensions.py
│   │   └── scorecard.py
│   ├── routers/              ← keep current API surface
│   ├── shared/               ← keep kafka_producer, db, etc.
│   └── tests/
├── ai-orchestrator/          ← Python (8093) — RESTRUCTURE INTERNAL:
│   ├── reasoning/            ← NEW — Reasoning Layer (L3)
│   │   ├── insight_engine.py
│   │   ├── recommendation_engine.py
│   │   ├── constraint_engine.py
│   │   ├── formula_library/
│   │   ├── criteria_registry/
│   │   ├── rag/              ← 4-tier source architecture
│   │   └── profiling/        ← 8-dim business profile (Reasoning Phần 1-3)
│   ├── workflow_runtime/     ← NEW — Temporal worker (L4) — Phase 1 Sprint 6
│   │   ├── activities/
│   │   ├── nodes/            ← 25 node types Phase 1, 45 by Phase 2
│   │   ├── saga/
│   │   └── temporal_client.py
│   ├── org_intel/            ← NEW — L4.5 — Sprint 7
│   │   ├── process_mining/   ← 8 sources, Heuristic Miner P1
│   │   ├── adoption/         ← 9 signals
│   │   └── economics/        ← NOV (Revenue + Cost + ROI)
│   ├── analytics/            ← keep existing (template_registry etc.)
│   ├── chat/                 ← keep Sprint 8 chat tool registry
│   ├── consumers/            ← keep
│   ├── shared/
│   └── tests/
├── llm-gateway/              ← keep Python (8095); add Anthropic adapter + drift detection P15
├── notification-service/     ← keep Python (8094); Phase 2 add Zalo Bot
└── process-mining/           ← (Phase 2) — sẽ tách ra service riêng khi extract
└── adoption-intel/           ← (Phase 2)
└── economics/                ← (Phase 2)
└── workflow-engine/          ← (Phase 2 — extract)
```

### 2.3 Infrastructure (Step 4)

```
infrastructure/
├── postgres/                 ← keep migrations
├── kafka/                    ← keep (event backbone, Redis Streams song song)
├── redis/                    ← keep, mở rộng cho Streams
├── ollama/                   ← keep (fallback local LLM)
├── temporal/                 ← NEW — docker-compose dev cluster + helm chart Phase 1.5
│   ├── docker-compose.yml
│   └── helm/
├── clickhouse/               ← NEW — Sprint 4 (Silver)
│   ├── schemas/
│   └── helm/
├── minio/                    ← NEW — Sprint 3 (Bronze)
│   └── docker-compose.yml
├── vault/                    ← NEW — Sprint 2
│   └── policies/             ← per-tenant secret paths
├── otel/                     ← NEW — Sprint 2 (OpenTelemetry collector + Jaeger)
│   ├── collector.yaml
│   └── jaeger.yaml
├── prometheus/               ← NEW — Sprint 2
├── grafana/                  ← NEW (đã có, chính thức hóa)
├── loki/                     ← NEW — Sprint 2
└── k8s/                      ← NEW — Phase 1.5 onwards
    ├── helm-charts/
    ├── kustomize/
    └── README.md             ← FPT Cloud setup guide
```

`docker-compose.yml` (root) sẽ phình to → tách thành `docker-compose.dev.yml` (laptop pilot) + `docker-compose.full.yml` (mọi service mới). Anh chọn pilot dùng cái nào.

---

## 3. Hành động bằng tay (Step 0-3) — em đề xuất em chạy luôn nếu anh OK

Step 0 (đã làm xong cho anh review):
- ✅ Tạo `docs/strategic/` + 5 MD (5500+ lines tổng)
- ✅ Tạo `docs/BACKLOG_V4.md` (1543 lines, 1147 features)
- ✅ Tạo `docs/API_CATALOG_V4.md` (722 lines, 169 endpoints + 42 deps)
- ✅ Tạo `docs/GAPS_V4.md` (gap analysis)
- ✅ Tạo `docs/RESTRUCTURE_PROPOSAL.md` (file này)

Step 1 (✅ DONE 2026-05-08):
- Move `docs/BACKLOG.md`, `docs/PHASE1_CLOSEOUT_PLAN.md`, `docs/PHASE2_PLAN.md` → `docs/archive/`
- Move `kaori-mvp-spec.md` → `docs/archive/` (legacy)
- Tạo `docs/strategic/README.md` (navigation cho 5 doc)
- Tạo `docs/README.md` v4 (refresh navigation index)

Step 2 (✅ DONE 2026-05-08):
- Rewrite `CLAUDE.md` v3.0 — narrative reset theo Phase 1/1.5/2/3 mới, point sang BACKLOG_V4. Giữ K-1..K-16. Thêm K-17..K-20. Phase Status reset: "Phase 1 v4 (4mo) — đang lập kế hoạch, P1-S1 chưa bắt đầu" (vì v4 phase boundaries khác v3).
- Lưu `CLAUDE.md` cũ tại `docs/archive/CLAUDE_v2.5.0.md` cho history.

Step 3 (✅ DONE 2026-05-08):
- 8 ADRs v4 viết xong (`adr/0010-0017-*.md`). Bao gồm sửa tên ADR-0015 sang Qwen-first sau khi anh chốt.

Step 4 — Phase B (✅ B-1 DONE 2026-05-08, B-2 lazy per-sprint):

**B-1 SKELETON ONLY (✅ landed):**
- 4 service skeleton folder + service.yaml + README: `process-mining`, `adoption-intel`, `economics`, `workflow-engine`
- 8 infra skeleton folder + README: `temporal`, `clickhouse`, `minio`, `vault`, `otel`, `k8s`, `loki`, `prometheus` (đã có `alerts.yml` từ trước)
- Smoke test: `pytest --collect-only` data-pipeline (347 tests) + ai-orchestrator (408 tests) PASS, 0 import errors

**B-2 LAZY FILE MOVES (✅ approach chốt 2026-05-08 — anh OK khuyến nghị):**

Thay vì 1 PR move toàn bộ data-pipeline + ai-orchestrator (50+ import path update, risk break pilot Olist), em move file theo sprint khi sprint chạm module đó:

| Sprint | Move khi đó |
|---|---|
| P1-S1 | None (auth + new shared logger module) |
| P1-S2 | None (OTel instrumentation in-place) |
| P1-S3 | `data-pipeline/bronze/` → `data-pipeline/data_plane/bronze/` + tạo `data-pipeline/ingestion/{connectors}/` |
| P1-S4 | `data-pipeline/silver/` `gold/` → `data_plane/` |
| P1-S5 | `ai-orchestrator/analytics/` → `ai-orchestrator/reasoning/` (hoặc gather under `reasoning/legacy_analytics/`) |
| P1-S6 | tạo `ai-orchestrator/workflow_runtime/` (Temporal worker) |
| P1-S7 | tạo `ai-orchestrator/org_intel/{process_mining, adoption, economics}/` |

Mỗi move = 1 PR riêng, smoke test pytest per service, không trigger CI cloud (anh chốt local-only).

Step 5 — Phase C bắt đầu Sprint 1 (P1-S1):
- Xem section 4 dưới đây.

---

## 4. Sprint 1 (P1-S1) — backlog em đề xuất ưu tiên (chỉ BE, FE pause)

> Sprint goal v4: **Cluster ready, monorepo, CI/CD, basic auth.**  
> 21 features tổng (xem `docs/BACKLOG_V4.md` section P1-S1). Em đã ánh xạ sang code hiện có:

| Feature code v4 | Status hiện tại | Hành động P1-S1 |
|---|---|---|
| P1-AUTH-001 Đăng nhập Platform Admin | ✅ Đã có (`auth-service /auth/platform/login`) | Smoke test, không touch |
| P1-AUTH-002 MFA TOTP | ✅ Đã có (Phase 3 batch 2) | Smoke test |
| P1-AUTH-003 Session management + force logout | ✅ Đã có (`/security/sessions[/{id}]`) | Smoke test |
| P1-ADM-001 Invite admin + role | ✅ Đã có (`/platform/admins`) | Smoke test |
| P1-M10-004..009 (đăng xuất, MFA, session, rate limit, force logout) | ✅ Hầu hết đã có | Verify, document gaps |
| P1-M13-001..006 (admin invite + roles) | ✅ Đã có | Smoke test |
| P2-M20-007..011 (first login, MFA, session, SSO Phase 2) | ⚠ first-login force-change-pwd chưa có | NEW work |
| P3-M30-006..008 (Studio first login, MFA, session) | ❌ Chưa có Studio | **DEFER P3 work** — Studio = Phase 2 |
| P4-M40-003/008/009 (Personal OAuth, MFA, session) | ❌ Chưa có Personal | **DEFER P4 work** — Personal = Phase 2 |
| **OBS-012 ⭐ Structured JSON logging (all services)** | ⚠ partial (có per-service) | NEW: chuẩn hóa logger, thêm trace_id placeholder |

**Sprint 1 Net New Work (BE only):**
1. **OBS-012** — chuẩn hóa structured JSON logger (1 module shared, used in 5 services). ~1 day.
2. **P2-M20-007** — first-login force change password flow (`enterprise_users.must_change_password` flag). ~0.5 day.
3. **Skeleton folders** Step 4 above. ~0.5 day.
4. **Smoke test toàn bộ existing auth/MFA endpoints** + write Sprint 1 acceptance test suite. ~1 day.
5. **CI matrix verify**: `services/*/pytest`, `auth-service/mvn verify`, gateway routing test. ~0.5 day.

Total ~3.5 ngày dev cho Sprint 1. **Phần còn lại (K8s cluster + monorepo migration)** anh đã có docker-compose chạy được — em đề xuất **defer K8s đến Phase 1.5 Sprint 9** (đỡ gián đoạn pilot). ADR-007 sẽ ghi rõ rationale.

Sprint 1 dừng FE, không touch frontend/ folder.

---

## 5. Pilot continuity (Olist đang chạy)

- Branch `main` không bị touch trong toàn bộ restructure. Pilot Olist chạy bình thường.
- Khi Sprint 1 v4 land, em chỉ rename internal folder structure → API surface giữ nguyên → pilot không cảm nhận.
- Khi Sprint 3 v4 land (Bronze + connectors), pilot cũ vẫn dùng Bronze cũ; chỉ workspace mới mới dùng connector mới.
- Phase 1.5 Sprint 9 mới triển K8s — pilot có thể migrate sau bằng `kompose convert` hoặc giữ docker-compose cho khách hàng nhỏ.

---

## 6. Câu hỏi anh cần trả lời — đã chốt 2026-05-08

1. ~~**K8s timing:**~~ → **Defer Phase 1.5 Sprint P15-S9** (theo em đề xuất) — không gián đoạn pilot Olist. Phase 1 v4 vẫn dùng docker-compose.
2. ~~**LLM default:**~~ → **Giữ Qwen-first**; `llm-gateway` adapter pluggable Anthropic/OpenAI/... — vendor opt-in qua `consent_external` + per-call flag. ADR-0015 v4 đã rewrite. K-4 giữ ý nghĩa cũ.
3. ~~**Branching:**~~ → **OK** plan `docs/v4-reset` → `feat/v4-restructure` → `feat/v4-p1-s1`.
4. ~~**F-061 Agent Framework:**~~ → **Merge to main as deprecated experiment** (theo em recommend). Branch `feat/f-061-agent-framework` close, không tính burndown v4. Code giữ trong main để reference; nếu Phase 2 muốn revive thì có sẵn.
5. **Sprint 8 Conversational Layer:** anh nói **"update lại trước khi thực thi tiếp"** — em đang xin clarify: (a) update spec/doc chat trước (em làm ngay), hay (b) refactor code `services/ai-orchestrator/chat/` trước Phase B/C?
6. ~~**CI budget:**~~ → **Local-only Phase B-C**, không trigger CI cloud cho đến reset 1/6. Em sẽ chạy `pytest` + `mvn verify` local.
7. ~~**Frontend template review:**~~ → **Sau Phase C** (sau Sprint 1 v4 land). Em không đụng `frontend/` cho đến lúc đó.

---

## 7. Em sẽ KHÔNG làm gì cho đến khi anh OK

- Không sửa code service (Java/Python).
- Không touch `frontend/`.
- Không tạo branch mới.
- Không commit/push gì.
- Chỉ đã viết 4 file MD trong `docs/` (strategic/* + BACKLOG_V4 + API_CATALOG_V4 + GAPS_V4 + RESTRUCTURE_PROPOSAL).

Tới đây em dừng. Anh đọc xong xác nhận từng bước (1→7 trong section 6 + Step 1-5 trong section 3) rồi em mới triển.
