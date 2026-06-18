# Kaori AI — BACKLOG v4.0

> **Source:** Feature Tree v4.0 (`Kaori_AI_Feature_Tree_v4_0.xlsx`) — 24-month roadmap, 36 sprints, ~1147 features.
> **Generated:** 2026-05-08 from 4 sprint-backlog sheets.
> **Replaces:** the original `docs/BACKLOG.md` (Phase 1/2 with F-001..F-068 numbering).

Status legend: ⭐ = NEW v2.0 capability (Process Mining, Adoption Intel, NOV, Runtime Reliability, Observability). Items without ⭐ existed in v3 but may need re-mapping to new module/layer names.

## Phase Summary

| Phase | Months | Sprints | Theme | Acceptance |
|---|---|---|---|---|
| **Phase 1 — Foundation** | M1-M4 | 8 (P1-S1..S8) | Modular monolith MVP, first 10-15 customers | ≥10 customers, workflow ≥99.5%, 0 cross-tenant leaks, NOV positive ≥3 customers |
| **Phase 1.5 — Stabilization** | M5-M6 | 4 (P15-S9..S12) | Critical gaps + 90-day testing infra | 10-15 active customers, NPS >30, full 9 adoption signals |
| **Phase 2 — Differentiation** | M7-M12 | 12 (P2-S13..S24) | Moat features, microservices extraction, international | 100 customers, SOC 2 Type 1, 99.9% API uptime |
| **Phase 3 — Platform** | Year 2 | 12 (P3-S25..S36) | Multi-region, marketplace, self-hosted LLM | 1000 customers, SOC 2 Type 2 + ISO 27001 |

Total: **36 sprints across 24 months**, ~1147 distinct features.

---

## Phase 1 (M1-M4)

### ~~P1-S1~~ ✅ DONE — Cluster ready, monorepo, CI/CD, basic auth  
*Batch:* `B1.1 — Foundation Setup`  ·  *Window:* Week 1-2  ·  *Features:* 21

**Platform (10)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-AUTH-001` | Đăng nhập Platform Admin | L5 + Cross | `POST /api/v1/platform/auth/login` |  |
| `P1-AUTH-002` | MFA bắt buộc SUPER_ADMIN (TOTP) | L5 + Cross | `POST /platform/auth/mfa/setup` |  |
| `P1-AUTH-003` | Session management + force logout | L5 + Cross | `GET /platform/auth/sessions` |  |
| `P1-ADM-001` | Invite admin + gán role (SUPER_ADMIN/ADMIN/SUPPORT/CSM/SALES/FINANCE) | L5 | `POST /platform/admins/invite` |  |
| `P1-M10-004` | Đăng xuất (invalidate session) | L0 + L5 | `/p1/auth/logout` |  |
| `P1-M10-006` | MFA / 2FA bắt buộc cho SUPER_ADMIN | L5 | `/p1/auth/mfa` |  |
| `P1-M10-007` | Session Management (JWT 1h + Refresh 30d) | L5 | `/p1/auth/sessions` |  |
| `P1-M10-008` | Rate Limit Login (5 lần → lock 15 phút) | L0 + L3 | `/p1/auth/login` |  |
| `P1-M10-009` | Force logout all sessions (SUPER_ADMIN) | L5 | `/p1/auth/sessions/force-logout` |  |
| `P1-M13-006` | Enforce MFA cho SUPER_ADMIN | L5 | `/p1/admins/settings/mfa-policy` |  |

**Enterprise (4)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M20-007` | First Login (force change password cho invited user) | L5 | `/p2/auth/first-login` |  |
| `P2-M20-008` | MFA / 2FA optional | L5 | `/p2/auth/mfa` |  |
| `P2-M20-009` | Session Management (JWT + Refresh Token) | L5 | `/p2/auth/sessions` |  |
| `P2-M20-011` | SSO (OAuth Google/Microsoft — Phase 2) | L3 + L5 | `/p2/auth/sso/:provider` |  |

**Studio (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P3-M30-006` | First Login (force change password) | L5 | `/p3/auth/first-login` |  |
| `P3-M30-007` | MFA / 2FA bắt buộc cho Kaori Staff Admin | L5 | `/p3/auth/mfa` |  |
| `P3-M30-008` | Session Management (JWT + Refresh) | L5 | `/p3/auth/sessions` |  |

**Personal (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P4-M40-003` | Đăng ký qua Google / Facebook / Apple (OAuth) | L5 | `/p4/auth/oauth/:provider` |  |
| `P4-M40-008` | MFA / 2FA optional | L5 | `/p4/auth/mfa` |  |
| `P4-M40-009` | Session Management (JWT + Refresh) | L5 | `/p4/auth/sessions` |  |

**Cross-cutting (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `OBS-012` | Structured JSON logging (all services) | L0 + Cross | `(internal observability)` | ⭐ |

### ~~P1-S2~~ ✅ DONE — Multi-tenancy + RLS + Vault setup  
*Batch:* `B1.1 — Foundation Setup`  ·  *Window:* Week 3-4  ·  *Features:* 42

**Platform (25)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-WS-001` | Tạo workspace mới | L4-L5 | `POST /api/v1/platform/workspaces` |  |
| `P1-WS-002` | List + filter workspaces (status, plan, industry) | L4-L5 | `GET /platform/workspaces?status=&plan=&industry=&q=` |  |
| `P1-WS-003` | Activate / Deactivate / Archive workspace | L4-L5 | `PATCH /platform/workspaces/{id}` |  |
| `P1-KEY-001` | Sinh KAORI-XXXX-XXXX-XXXX (reveal once) | L0-L5 (Cross) | `POST /platform/keys` |  |
| `P1-KEY-002` | Revoke key + xem usage history | L0-L5 (Cross) | `DELETE /platform/keys/{id}` |  |
| `P1-MTNT-001` | ⭐ Cross-tenant access attempt monitoring | L0-L2 (Cross) | `GET /platform/security/cross-tenant-attempts` | ⭐ |
| `P1-MTNT-002` | ⭐ Continuous RLS leak testing in CI/CD | L0-L2 (Cross) | `POST /platform/security/run-leak-tests (CI)` | ⭐ |
| `P1-M10-001` | Đăng nhập Platform Admin | L3 + L5 | `/p1/auth/login` |  |
| `P1-M11-001` | Tạo workspace mới | Cross | `/p1/workspaces/new` |  |
| `P1-M11-002` | Sửa thông tin workspace (plan, notes) | Cross | `/p1/workspaces/:id/edit` |  |
| `P1-M11-003` | Xem chi tiết workspace | L5 | `/p1/workspaces/:id` |  |
| `P1-M11-004` | Activate / Deactivate workspace | L5 | `/p1/workspaces/:id/status` |  |
| `P1-M11-005` | Filter workspaces (status, plan) | L5 | `/p1/workspaces` |  |
| `P1-M11-006` | Search workspaces | L5 | `/p1/workspaces` |  |
| `P1-M11-007` | Export danh sách workspace | L5 | `/p1/workspaces/export` |  |
| `P1-M12-001` | Generate key mới (KAORI-XXXX-XXXX-XXXX) | L3 | `/p1/keys/new` |  |
| `P1-M12-002` | Copy key (hiện 1 lần duy nhất) | L5 | `/p1/keys/:id/reveal` |  |
| `P1-M12-003` | Revoke key | L5 | `/p1/keys/:id/revoke` |  |
| `P1-M13-001` | Invite admin qua email | L3 | `/p1/admins/invite` |  |
| `P1-M13-002` | Gán role (SUPER_ADMIN / ADMIN / SUPPORT) | Cross | `/p1/admins/:id/role` |  |
| `P1-M13-003` | Deactivate admin | L5 + Cross | `/p1/admins/:id/deactivate` |  |
| `P1-M13-004` | Reset password admin | L3 | `/p1/admins/:id/reset-password` |  |
| `P1-M13-005` | Force logout admin | L5 | `/p1/admins/:id/force-logout` |  |
| `P1-M16-001` | KPI cards (Workspace, MRR, Customers billed) | L5 | `/p1/health/kpis` |  |
| `P1-M16-004` | Quick link tới workspace vấn đề | L3 + L5 | `/p1/health/workspaces-at-risk` |  |

**Enterprise (4)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M22-001` | Nhập private key | L5 | `/p2/onboarding/key` |  |
| `P2-M22-002` | Auto-format key input | L5 | `/p2/onboarding/key` |  |
| `P2-M22-003` | Validate key hash | L3 | `/p2/onboarding/key/validate` |  |
| `P2-M25-010` | Retention policy per tenant (default 90 ngày) | L1 + L2 | `/p2/data/bronze/retention` |  |

**Studio (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P3-M30-002` | Kích hoạt tài khoản qua email invite (Studio Admin mời) | L3 + L5 | `/p3/auth/activate/:token` |  |

**Cross-cutting (12)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `SH-M52-001` | Middleware extract tenant_id từ JWT | L3 + Cross | `/shared/isolation/middleware` |  |
| `OBS-001` | OpenTelemetry SDK integration (every service) | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-002` | Jaeger UI for trace visualization | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-003` | Tenant_id in every span (mandatory attribute) | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-006` | Prometheus + Grafana stack | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-009` | Custom metrics: tenant_quota_usage | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-013` | Loki log aggregation | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-014` | Trace_id + span_id in every log | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-015` | Tenant_id in every log | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-016` | PagerDuty alerting integration | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-019` | Alert playbooks per alert type | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-022` | Sentry error tracking integration | L0 + Cross | `(internal observability)` | ⭐ |

### ~~P1-S3~~ ✅ DONE — First 3 connectors + Bronze tier  
*Batch:* `B1.2 — Ingestion + Data Plane`  ·  *Window:* Week 5-6  ·  *Features:* 23

**Platform (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-M15-003` | Pipeline view (Prospect → Pilot → ENT) | L3 | `/p1/pilot-conversion/pipeline` |  |

**Enterprise (20)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M21-002` | Upload logo / avatar tổ chức | L1 | `/p2/branding/logo` |  |
| `P2-M22-006` | Upload logo công ty | L1 | `/p2/onboarding/logo` |  |
| `P2-M23-007` | Quick link → Data Pipeline Wizard | L5 | `/p2/dashboard/quick-actions` |  |
| `P2-M25-001` | Ingestion từ file upload (CSV/Excel/JSON/Parquet) | L1 + L2 | `/p2/data/bronze/upload` |  |
| `P2-M25-002` | Ingestion từ data source connect (DB/API/CRM/ERP) | L0 + L1 | `/p2/data/bronze/connectors` |  |
| `P2-M25-003` | Streaming ingestion (webhook/Kafka — Phase 2) | L0 + L1 | `/p2/data/bronze/streaming` |  |
| `P2-M25-006` | Gắn metadata source (source_name, ingested_at, file_name) | L1 + L2 | `/p2/data/bronze/metadata` |  |
| `P2-M25-008` | Xem lịch sử ingestion | L1 + L2 | `/p2/data/bronze/history` |  |
| `P2-M25-009` | Rollback ingestion (restore previous raw snapshot) | L1 + L2 | `/p2/data/bronze/:id/rollback` |  |
| `P2-M26-001` | Upload CSV (max 50MB) | L1 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-002` | Upload Excel (XLSX/XLS) | L1 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-003` | Upload JSON / JSON Lines | L1 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-004` | Upload Parquet — Phase 2 | L1 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-006` | Progress bar upload realtime | L1 + L5 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-009` | Đặt tên pipeline | L5 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M27-001` | Phân tích pattern data từ các pipeline đã chạy | L5 | `/p2/auto-db/analyze` |  |
| `P2-M27-010` | Khi upload data theo template → auto-classify Bronze/Silver/Gold | L1 + L2 | `/p2/auto-db/classify` |  |
| `P2-M210-001` | Input: data analysis result + uploaded documents | L1 + L3 | `/p2/insights/input` |  |
| `P2-M210-012` | Upload tài liệu nội bộ (PDF, Word, TXT, MD) | L1 + L3 | `/p2/insights/knowledge-base/upload` |  |
| `P2-M216-005` | Gửi feedback tới pipeline retrain | L2 + L3 | `/p2/decisions/:id/feedback` |  |

**Personal (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P4-M42-002` | Drag-drop upload | L1 + L3 | `/p4/uploads/new` |  |
| `P4-M49-001` | Avatar upload | L1 | `/p4/customize/avatar` |  |

### ~~P1-S4~~ ✅ DONE — Silver + Gold tiers + data quality  
*Batch:* `B1.2 — Ingestion + Data Plane`  ·  *Window:* Week 7-8  ·  *Features:* 7

**Enterprise (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M25-011` | Data Cleaning (remove duplicates, trim whitespace, null handling) | L1 + L2 | `/p2/data/silver/clean` |  |
| `P2-M25-020` | Data Integration (join nhiều Silver table thành dimension/fact) | L1 + L2 | `/p2/data/gold/integrate` |  |
| `P2-M26-023` | AI suggested cleaning rules list | L3 | `/p2/pipelines/new/step-3-clean/rules` |  |

**Studio (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P3-M33-007` | Tab Datasets (Bronze/Silver/Gold snapshot) | L1 + L2 | `/p3/projects/:id/datasets` |  |
| `P3-M36-003` | Insert chart/analysis từ Gold layer (dùng Chart Library 2.14) | L2 + L3 | `/p3/reports/composer/insert/chart` |  |

**Cross-cutting (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `SH-M57-002` | Silver layer storage (columnar DB) | L2 + L3 | `/shared/medallion/silver-storage` |  |
| `SH-M57-003` | Gold layer storage (views + materialized views) | L2 + L3 | `/shared/medallion/gold-storage` |  |

### ~~P1-S5~~ ✅ DONE — Reasoning Layer + LLM integration  
*Batch:* `B1.3 — AI Brain + Workflow Engine`  ·  *Window:* Week 9-10  ·  *Features:* 39

**Platform (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-LLM-004` | ⭐ LLM Version Pinning (Workflow v2.0 Phần 21) | L3 | `POST /platform/llm/versions/pin` | ⭐ |
| `P1-M10-002` | Quên mật khẩu → email reset | L3 + L5 | `/p1/auth/forgot-password` |  |
| `P1-M14-006` | Tính overage cost tự động | L0 + L3 | `/p1/billing/overage` |  |

**Enterprise (24)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M20-002` | Kích hoạt tài khoản qua email invite | L3 + L5 | `/p2/auth/activate/:token` |  |
| `P2-M20-003` | Quên mật khẩu → email reset | L3 + L5 | `/p2/auth/forgot-password` |  |
| `P2-M21-006` | Custom subdomain (vd: mycompany.kaori.ai) — Phase 2 | L3 | `/p2/branding/subdomain` |  |
| `P2-M21-007` | Custom email template branding (logo trong email invite) | L3 | `/p2/branding/email` |  |
| `P2-M22-007` | Chọn industry (RETAIL, FINANCE, LOGISTICS, F&B, EDUCATION, ...) | L3 + L5 | `/p2/onboarding/industry` |  |
| `P2-M23-004` | Widget AI decisions today | L3 + L5 | `/p2/dashboard/widgets/ai-decisions` |  |
| `P2-M23-010` | Customize widget layout (drag-drop) | L3 + L5 | `/p2/dashboard/customize` |  |
| `P2-M24-002` | Mời member qua email | L3 | `/p2/users/invite` |  |
| `P2-M25-024` | Aggregated Objects (daily/weekly/monthly summary) | L1 + L2 | `/p2/data/gold/aggregates/:period` |  |
| `P2-M26-005` | Drag-drop file | L3 + L5 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-008` | Template catalog — Retail, Finance, Logistics, HR, Marketing, ... | L3 | `/p2/pipelines/new/templates` |  |
| `P2-M26-016` | Drag-drop mapping | L3 | `/p2/pipelines/new/step-2-columns/mapping` |  |
| `P2-M26-031` | Rule: Validate email/phone format | L3 | `/p2/pipelines/new/step-3-clean/rules/format-check` |  |
| `P2-M26-044` | Chọn external AI provider (optional) | L3 | `/p2/pipelines/new/step-4-analyze/provider` |  |
| `P2-M26-051` | Insight panel "Chuyện gì · Tại sao · Nên làm gì" — xem Section 2.10 | L3 | `/p2/pipelines/new/step-5-results/insights` |  |
| `P2-M210-005` | Confidence score cho mỗi insight | L3 | `/p2/insights/:id/confidence` |  |
| `P2-M210-008` | Chọn LLM nội bộ hoặc external AI (nếu không sợ lộ data) | L3 | `/p2/insights/provider` |  |
| `P2-M210-009` | Export insight as PDF report | L3 | `/p2/insights/:id/export` |  |
| `P2-M210-010` | Save insight + track acted/not-acted | L3 | `/p2/insights/:id/track` |  |
| `P2-M210-011` | Feedback loop — user rate insight → improve prompt | L3 | `/p2/insights/:id/feedback` |  |
| `P2-M210-014` | RAG (Retrieval-Augmented Generation) cho insights | L3 | `/p2/insights/knowledge-base/rag` |  |
| `P2-M216-002` | Panel "Tại sao AI quyết định" (top 3 factors) | L3 | `/p2/decisions/:id/explain` |  |
| `P2-M219-001` | Tab Quota — gauge X/Y khách / token LLM | L3 | `/p2/subscription/quota` |  |
| `P2-M219-002` | Dự báo overage | L3 | `/p2/subscription/quota/forecast` |  |

**Studio (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P3-M34-002` | Click → version detail | L3 + L5 | `/p3/models/:id/versions/:ver` |  |
| `P3-M34-005` | Tab Training Log | L3 | `/p3/models/:id/versions/:ver/training-log` |  |

**Personal (5)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P4-M40-002` | Đăng ký tài khoản cá nhân (self-signup email/phone) | L3 + L5 | `/p4/auth/signup` |  |
| `P4-M40-004` | Xác thực email / SMS OTP khi đăng ký | L3 + L5 | `/p4/auth/verify` |  |
| `P4-M41-004` | AI suggestions unread panel | L3 + L5 | `/p4/dashboard/suggestions` |  |
| `P4-M44-003` | Insights cá nhân hóa | L3 | `/p4/pipelines/new/step-5-results/insights` |  |
| `P4-M45-005` | Drag-drop reorder (persist ngay) | L3 | `/p4/goals/tree/reorder` |  |

**Cross-cutting (5)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `SH-M51-001` | Cron daily aggregate | L3 | `/shared/billing-engine/cron` |  |
| `SH-M53-005` | API explainability public | L3 | `/api/v1/explainability` |  |
| `SH-M57-001` | Bronze layer storage (object storage / S3-compatible) | L1 + L3 | `/shared/medallion/bronze-storage` |  |
| `SH-M62-002` | Gửi invoice qua email | L3 | `/billing/invoices/:id/email` |  |
| `OBS-008` | Custom metrics: ai_calls_total + tokens_total | L0 + Cross | `(internal observability)` | ⭐ |

### ~~P1-S6~~ ✅ DONE — Workflow Engine (Temporal) + builder UI  
*Batch:* `B1.3 — AI Brain + Workflow Engine`  ·  *Window:* Week 11-12  ·  *Features:* 27

**Enterprise (4)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M26-045` | Config form auto-generate từ template | L5 | `/p2/pipelines/new/step-4-analyze/config` |  |
| `P2-M26-058` | Save analysis as template | L3 | `/p2/pipelines/new/step-5-results/save-template` |  |
| `P2-M27-006` | Đề xuất quy trình quản lý data (workflow recommendation) | L3 + L4 | `/p2/auto-db/workflow` |  |
| `P2-M27-009` | Save workflow template cho lần sau | L4 | `/p2/auto-db/templates` |  |

**Cross-cutting (23)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `REL-001` | Side-effect classification taxonomy (5 classes) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-002` | Per-node side-effect declaration in YAML | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-003` | Class-aware execution path in Action Runtime | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-004` | Idempotency key generation (deterministic per node + run) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-005` | Postgres idempotency_records table with TTL | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-006` | Distributed lock for write_non_idempotent | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-007` | Provider-side dedup integration (SendGrid, Twilio) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-008` | Retry policy per node (max attempts, backoff) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-009` | Retry-After header respect | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-010` | Per-tenant rate limiting on retries | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-011` | Saga pattern for irreversible workflows | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-012` | Compensation action declarations in YAML | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-013` | Saga orchestrator (Temporal-based) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-015` | Dead Letter Queue (DLQ) for failed workflows | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-016` | DLQ admin UI (review + reprocess + discard) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-017` | DLQ alerting (high volume = systemic issue) | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-018` | Circuit breaker per external service | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-020` | Per-node timeout configuration | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-021` | Heartbeating for long-running activities | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-022` | Per-tenant connection pool isolation | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-023` | Per-tenant thread pool limits | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `OBS-004` | Workflow_run_id correlation across services | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-007` | Custom metrics: workflow_executions_total | L0 + Cross | `(internal observability)` | ⭐ |

### ~~P1-S7~~ ✅ DONE — Process Mining v1 + Adoption + NOV basic  
*Batch:* `B1.4 — Org Intelligence v1 + Launch Prep`  ·  *Window:* Week 13-14  ·  *Features:* 48

**Platform (6)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-BIL-001` | Tổng quan billing theo tháng (MRR + breakdown) | L4-L5 | `GET /platform/billing/overview?month={YYYY-MM}` |  |
| `P1-BIL-002` | Alert khi enterprise >80% quota | L4-L5 | `GET /platform/billing/alerts` |  |
| `P1-BIL-003` | Tính overage cost tự động | L4-L5 | `POST /platform/billing/overage/compute (cron)` |  |
| `P1-PILOT-001` | Pipeline view (Prospect → Pilot → Enterprise) | L4-L5 | `GET /platform/pilot-conversion/pipeline?industry=` |  |
| `P1-PILOT-002` | Auto-trigger D25 reminder + D30 upgrade prompt | L4-L5 | `POST /platform/pilot-conversion/triggers/d25 (cron)` |  |
| `P1-CSM-001` | ⭐ Customer health overview (Adoption + ROI + Renewal Risk) | L4.5 + L5 | `GET /platform/customer-success/{tenant_id}/health` | ⭐ |

**Enterprise (40)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M219-008` | Contact sales (ENT ROI tier) | L4.5 | `/p2/subscription/contact-sales` |  |
| `PM-EVT-001` | Postgres CDC log connector | L1 + L4.5 | `/process-mining/connectors/postgres` | ⭐ |
| `PM-EVT-002` | Excel history connector (Excel revision metadata) | L1 + L4.5 | `/process-mining/connectors/excel` | ⭐ |
| `PM-EVT-003` | Zalo Business API metadata connector | L1 + L4.5 | `/process-mining/connectors/zalo` | ⭐ |
| `PM-PII-009` | Common event log schema normalization | L4.5 + Cross | `/process-mining/sessions/{id}/pii-config` | ⭐ |
| `PM-PII-010` | PII detection (Vietnamese-aware) | L4.5 + Cross | `/process-mining/sessions/{id}/pii-config` | ⭐ |
| `PM-PII-011` | PII redaction (mask names → roles) | L4.5 + Cross | `/process-mining/sessions/{id}/pii-config` | ⭐ |
| `PM-PII-012` | Tenant-id stamping on every event | L4.5 + Cross | `/process-mining/sessions/{id}/pii-config` | ⭐ |
| `PM-ALG-014` | Case inference (group events by case_id) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ALG-015` | Heuristic Miner algorithm (Phase 1) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ALG-018` | Variant analysis (main + alternates) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ALG-019` | Temporal pattern extraction (avg duration per step) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ALG-020` | Frequency analysis (path occurrence counts) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ANM-021` | Bottleneck detection (long wait times) | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `AI-SIG-001` | ⭐ Signal 1: Workflow execution abandonment | L4.5 | `GET /adoption/signals/workflow-execution-abandonment` | ⭐ |
| `AI-SIG-002` | ⭐ Signal 2: AI decision override rate tracking | L4.5 | `GET /adoption/signals/ai-decision-override-rate-trac` | ⭐ |
| `AI-SIG-003` | ⭐ Signal 3: Side-channel detection (Zalo/Excel use post-deploy) | L4.5 | `GET /adoption/signals/side-channel-detection-(zalo/e` | ⭐ |
| `AI-SIG-005` | ⭐ Signal 5: Manager intervention frequency | L4.5 | `GET /adoption/signals/manager-intervention-frequency` | ⭐ |
| `AI-SIG-006` | ⭐ Signal 6: Workflow completion rate per user/dept | L4.5 | `GET /adoption/signals/workflow-completion-rate-per-u` | ⭐ |
| `AI-HSC-010` | Composite adoption health score (0-100) | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |
| `AI-HSC-011` | Per-workflow health score | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |
| `AI-HSC-012` | Per-department adoption rollup | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |
| `AI-HSC-013` | Per-tenant overall adoption score | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |
| `AI-HSC-014` | Health classification (EXCELLENT/HEALTHY/AT_RISK/STRUGGLING/CRITICAL) | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |
| `AI-HSC-015` | Trend analysis (improving/declining/stable) | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |
| `AI-INT-018` | CSM alert generation (escalate to human) | L4.5 + L5 | `POST /adoption/interventions/trigger` | ⭐ |
| `NOV-REV-001` | Pre/Post comparison method | L4.5 | `POST /economics/revenue/estimate` | ⭐ |
| `NOV-REV-003` | Industry benchmark fallback method | L4.5 | `POST /economics/revenue/estimate` | ⭐ |
| `NOV-REV-004` | KPI-to-revenue mapper (per industry) | L4.5 | `POST /economics/revenue/estimate` | ⭐ |
| `NOV-REV-005` | Confidence scoring on revenue estimates | L4.5 | `POST /economics/revenue/estimate` | ⭐ |
| `NOV-CST-007` | People cost estimator (time saved × rate) | L4.5 | `POST /economics/cost/compute` | ⭐ |
| `NOV-CST-008` | Infrastructure cost calculator (per-tenant compute + storage) | L4.5 | `POST /economics/cost/compute` | ⭐ |
| `NOV-CST-009` | AI call cost tracking (token-based) | L4.5 | `POST /economics/cost/compute` | ⭐ |
| `NOV-CST-010` | Integration cost (3rd party API calls) | L4.5 | `POST /economics/cost/compute` | ⭐ |
| `NOV-CORE-013` | NOV monthly computation (revenue - cost) | L4.5 | `GET /economics/nov/{workflow_id}/monthly` | ⭐ |
| `NOV-CORE-014` | Time-to-payback projection | L4.5 | `GET /economics/nov/{workflow_id}/monthly` | ⭐ |
| `NOV-CORE-015` | Cumulative NOV tracking | L4.5 | `GET /economics/nov/{workflow_id}/monthly` | ⭐ |
| `NOV-CORE-016` | Negative NOV alerts | L4.5 | `GET /economics/nov/{workflow_id}/monthly` | ⭐ |
| `NOV-CORE-017` | Per-department NOV rollup | L4.5 | `GET /economics/nov/{workflow_id}/monthly` | ⭐ |
| `NOV-CORE-018` | Per-tenant total NOV | L4.5 | `GET /economics/nov/{workflow_id}/monthly` | ⭐ |

**Cross-cutting (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `OBS-010` | Custom metrics: nov_per_workflow | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-011` | Custom metrics: adoption_score_per_workflow | L0 + Cross | `(internal observability)` | ⭐ |

### ~~P1-S8~~ ✅ DONE — Telegram Bot (pluggable adapter ADR-0018) + final polish + Phase 1 v4 closeout  
*Batch:* `B1.4 — Org Intelligence v1 + Launch Prep`  ·  *Window:* Week 15-16  ·  *Features:* 296

**Platform (28)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-HEALTH-001` | KPI cards (Workspaces, MRR, Customers billed, Workflows running) | L5 | `GET /platform/health/kpis` |  |
| `P1-PLAN-001` | CRUD plans với soft-update versioning (AP-8) | L4 | `POST /platform/plans, PATCH /platform/plans/{id}` |  |
| `P1-CSM-002` | ⭐ Customer cohort health portfolio | L4.5 + L5 | `GET /platform/customer-success/portfolio` | ⭐ |
| `P1-M10-003` | Reset mật khẩu (link 1h) | L5 | `/p1/auth/reset-password/:token` |  |
| `P1-M10-005` | Đổi mật khẩu | L5 | `/p1/auth/change-password` |  |
| `P1-M10-010` | IP Whitelist (tùy chọn) | L5 | `/p1/auth/ip-whitelist` |  |
| `P1-M12-004` | Xem lịch sử sử dụng (used_at, used_by_ip) | L5 | `/p1/keys/:id/usage` |  |
| `P1-M12-005` | Hash SHA-256 lưu DB (AP-6) | L3 | `/p1/keys` |  |
| `P1-M14-001` | Xem tổng quan billing theo tháng | L0 | `/p1/billing/overview` |  |
| `P1-M14-002` | Drill-down theo enterprise | L0 | `/p1/billing/enterprises/:id` |  |
| `P1-M14-003` | Xem quota usage % | L0 + L5 | `/p1/billing/quota` |  |
| `P1-M14-004` | Aggregate DISTINCT customer_external_id | L0 | `/p1/billing/unique-customers` |  |
| `P1-M14-005` | Alert khi enterprise >80% quota | L0 | `/p1/billing/alerts` |  |
| `P1-M14-007` | Export báo cáo billing | L0 | `/p1/billing/export` |  |
| `P1-M15-001` | Xem conversion rate tổng | L5 | `/p1/pilot-conversion/overview` |  |
| `P1-M15-002` | Drill-down theo tháng | L5 | `/p1/pilot-conversion/monthly` |  |
| `P1-M15-004` | Filter theo ngành | L3 | `/p1/pilot-conversion` |  |
| `P1-M15-005` | Auto-trigger reminder D25 | L3 | `/p1/pilot-conversion/triggers/d25` |  |
| `P1-M15-006` | Auto-trigger upgrade prompt D30 | L3 | `/p1/pilot-conversion/triggers/d30` |  |
| `P1-M15-007` | 1-click upgrade flow | L5 | `/p1/pilot-conversion/:id/upgrade` |  |
| `P1-M16-002` | Chart 30 ngày (trend) | L5 | `/p1/health/trend` |  |
| `P1-M16-003` | Alert widget real-time | L5 | `/p1/health/alerts` |  |
| `P1-M16-005` | Auto-refresh 5 phút | L5 | `/p1/health` |  |
| `P1-M17-001` | Xem danh sách plans | L5 | `/p1/plans` |  |
| `P1-M17-002` | Sửa giá plan (AP-8 soft update) | L5 | `/p1/plans/:id/edit` |  |
| `P1-M17-003` | Sửa quota (customers_per_month) | L5 | `/p1/plans/:id/quota` |  |
| `P1-M17-004` | Deactivate plan cũ (soft) | L5 | `/p1/plans/:id/deactivate` |  |
| `P1-M17-005` | Tạo plan mới | L5 | `/p1/plans/new` |  |

**Enterprise (134)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M20-001` | Đăng nhập Enterprise User | L3 + L5 | `/p2/auth/login` |  |
| `P2-M20-004` | Reset mật khẩu (link 1h) | L5 | `/p2/auth/reset-password/:token` |  |
| `P2-M20-005` | Đăng xuất | L5 | `/p2/auth/logout` |  |
| `P2-M20-006` | Đổi mật khẩu | L5 | `/p2/auth/change-password` |  |
| `P2-M20-010` | Rate Limit (5 lần → lock 15 phút) | L3 + L5 | `/p2/auth/login` |  |
| `P2-M21-001` | Đặt tên tổ chức | L5 | `/p2/branding/identity` |  |
| `P2-M21-003` | Chọn màu sắc thương hiệu (primary / secondary / accent) | L5 | `/p2/branding/colors` |  |
| `P2-M21-004` | Chọn theme sáng/tối | L5 | `/p2/branding/theme` |  |
| `P2-M21-005` | Preview trước khi áp dụng | L5 | `/p2/branding/preview` |  |
| `P2-M21-008` | Custom PDF report header branding | L5 | `/p2/branding/pdf` |  |
| `P2-M22-004` | Rate limit 5 lần thử/phút | L0 + Cross | `/p2/onboarding/key` |  |
| `P2-M22-005` | Điền thông tin công ty (tên, industry, timezone) | L5 | `/p2/onboarding/company` |  |
| `P2-M22-008` | Mời thành viên đầu tiên | L3 | `/p2/onboarding/invite` |  |
| `P2-M22-009` | Skip invite step | L4 | `/p2/onboarding/invite` |  |
| `P2-M22-010` | Pilot countdown D25 notification | L3 | `/p2/onboarding/pilot/d25` |  |
| `P2-M22-011` | Pilot countdown D30 upgrade prompt | L3 | `/p2/onboarding/pilot/d30` |  |
| `P2-M22-012` | 1-click upgrade với data migrate seamless | L5 | `/p2/onboarding/pilot/upgrade` |  |
| `P2-M23-001` | Widget KPI chính theo ngành (tùy chỉnh) | L5 | `/p2/dashboard/widgets/kpi` |  |
| `P2-M23-002` | Widget "Doanh thu đang được bảo vệ" | L3 + L5 | `/p2/dashboard/widgets/revenue-at-risk` |  |
| `P2-M23-003` | Widget HIGH risk count | L5 | `/p2/dashboard/widgets/high-risk` |  |
| `P2-M23-005` | Quota gauge "X/Y khách được phát hiện" | L5 | `/p2/dashboard/widgets/quota` |  |
| `P2-M23-006` | Alert list real-time | L5 | `/p2/dashboard/widgets/alerts` |  |
| `P2-M23-008` | Auto-refresh 60s | L5 | `/p2/dashboard` |  |
| `P2-M23-009` | Mobile responsive (tablet) | L5 | `/p2/dashboard` |  |
| `P2-M24-001` | Danh sách members | L5 | `/p2/users` |  |
| `P2-M24-003` | Multi-role per user (AP-5 compound PK) | L5 | `/p2/users/:id/roles` |  |
| `P2-M24-004` | Gán role MANAGER / OPERATOR / ANALYST / VIEWER | L5 | `/p2/users/:id/roles/assign` |  |
| `P2-M24-005` | Deactivate member | L5 | `/p2/users/:id/deactivate` |  |
| `P2-M24-006` | Resend invite | L3 | `/p2/users/:id/resend-invite` |  |
| `P2-M24-007` | Đổi role | Cross | `/p2/users/:id/roles/change` |  |
| `P2-M24-008` | Enforce ≥1 MANAGER active | L5 | `/p2/users/:id/deactivate` |  |
| `P2-M25-004` | Lưu raw data as-is (không transformation) | L1 + L2 | `/p2/data/bronze/store` |  |
| `P2-M25-005` | Truncate & Insert load method | L1 + L2 | `/p2/data/bronze/load` |  |
| `P2-M25-007` | Data lineage tracking | L1 + L2 | `/p2/data/bronze/lineage` |  |
| `P2-M25-012` | Data Standardization (date format, case, encoding) | L1 + L2 | `/p2/data/silver/standardize` |  |
| `P2-M25-013` | Data Normalization (unit conversion, category mapping) | L1 + L2 | `/p2/data/silver/normalize` |  |
| `P2-M25-014` | Derived Columns (tuổi từ DOB, full_name từ first+last, ...) | L1 + L2 | `/p2/data/silver/derived` |  |
| `P2-M25-015` | Data Enrichment (thêm thông tin từ external source / reference table) | L1 + L2 | `/p2/data/silver/enrich` |  |
| `P2-M25-016` | Schema validation (type, format, required fields) | L1 + L2 | `/p2/data/silver/validate` |  |
| `P2-M25-017` | Xem Before/After mỗi transformation | L1 + L2 | `/p2/data/silver/diff` |  |
| `P2-M25-018` | Log chi tiết transformation (step_log append-only) | L1 + L2 | `/p2/data/silver/step-log` |  |
| `P2-M25-019` | Quality score NUMERIC(5,4) | L1 + L2 | `/p2/data/silver/quality-score` |  |
| `P2-M25-021` | Data Aggregation (SUM/AVG/COUNT theo time/category) | L1 + L2 | `/p2/data/gold/aggregate` |  |
| `P2-M25-022` | Business Logic & Rules (custom KPI, formula) | L1 + L2 | `/p2/data/gold/business-rules` |  |
| `P2-M25-023` | Star Schema modeling (dimensions + facts) | L1 + L2 | `/p2/data/gold/star-schema` |  |
| `P2-M25-025` | Flat Tables (denormalized cho reporting nhanh) | L1 + L2 | `/p2/data/gold/flat-tables` |  |
| `P2-M25-026` | Materialized Views (cache kết quả nặng) | L1 + L2 | `/p2/data/gold/materialized-views` |  |
| `P2-M25-027` | Version hóa business rules (audit change) | L1 + L2 | `/p2/data/gold/rules/versions` |  |
| `P2-M26-007` | Connect từ data source đã có (CRM/ERP/DB) | L1 | `/p2/pipelines/new/step-1-upload` |  |
| `P2-M26-010` | Preview 10 dòng đầu | L5 | `/p2/pipelines/new/step-1-upload/preview` |  |
| `P2-M26-011` | Step indicator 1●○○○○ | L5 | `/p2/pipelines/new` |  |
| `P2-M26-012` | Auto phân tích schema | L5 | `/p2/pipelines/new/step-2-columns/autodetect` |  |
| `P2-M26-013` | Phát hiện cột + data type + null_rate | L5 | `/p2/pipelines/new/step-2-columns` |  |
| `P2-M26-014` | Hiển thị sample values | L5 | `/p2/pipelines/new/step-2-columns/samples` |  |
| `P2-M26-015` | Bảng so sánh "Cột của bạn" vs "Cột cần thiết" | L5 | `/p2/pipelines/new/step-2-columns/mapping` |  |
| `P2-M26-017` | Quality gauge (NUMERIC 5,4) | L5 | `/p2/pipelines/new/step-2-columns/quality` |  |
| `P2-M26-018` | Warning null_rate > 30% | L5 | `/p2/pipelines/new/step-2-columns/warnings` |  |
| `P2-M26-019` | Warning quality_score < 0.6 | L5 | `/p2/pipelines/new/step-2-columns/warnings` |  |
| `P2-M26-020` | Validate required columns 100% | L5 | `/p2/pipelines/new/step-2-columns/validate` |  |
| `P2-M26-021` | Bỏ qua cột thừa | L5 | `/p2/pipelines/new/step-2-columns/skip-columns` |  |
| `P2-M26-022` | Đề xuất type conversion (text → date/number) | L3 | `/p2/pipelines/new/step-2-columns/type-suggestion` |  |
| `P2-M26-024` | Toggle on/off từng rule | L5 | `/p2/pipelines/new/step-3-clean/rules/toggle` |  |
| `P2-M26-025` | Rule: Remove duplicates | L5 | `/p2/pipelines/new/step-3-clean/rules/dedup` |  |
| `P2-M26-026` | Rule: Fill missing values | L5 | `/p2/pipelines/new/step-3-clean/rules/fillna` |  |
| `P2-M26-027` | Rule: Trim whitespace | L5 | `/p2/pipelines/new/step-3-clean/rules/trim` |  |
| `P2-M26-028` | Rule: Standardize date format | L5 | `/p2/pipelines/new/step-3-clean/rules/date-format` |  |
| `P2-M26-029` | Rule: Normalize case | L5 | `/p2/pipelines/new/step-3-clean/rules/case` |  |
| `P2-M26-030` | Rule: Remove outliers (IQR/Z-score) | L5 | `/p2/pipelines/new/step-3-clean/rules/outliers` |  |
| `P2-M26-032` | Rule: Derive columns (age from DOB, etc.) | L5 | `/p2/pipelines/new/step-3-clean/rules/derive` |  |
| `P2-M26-033` | Rule: Enrich từ reference table | L5 | `/p2/pipelines/new/step-3-clean/rules/enrich` |  |
| `P2-M26-034` | Hiển thị rows affected per rule | L5 | `/p2/pipelines/new/step-3-clean/rules/stats` |  |
| `P2-M26-035` | Hiển thị quality_delta per rule | L5 | `/p2/pipelines/new/step-3-clean/rules/delta` |  |
| `P2-M26-036` | Preview Before/After 20 dòng sample | L5 | `/p2/pipelines/new/step-3-clean/preview` |  |
| `P2-M26-037` | Button "Giải thích quyết định" per rule | L3 | `/p2/pipelines/new/step-3-clean/rules/:id/explain` |  |
| `P2-M26-038` | Apply all rules | L5 | `/p2/pipelines/new/step-3-clean/apply-all` |  |
| `P2-M26-039` | Undo toàn bộ / Undo từng bước | L5 | `/p2/pipelines/new/step-3-clean/undo` |  |
| `P2-M26-040` | Final quality_score card | L5 | `/p2/pipelines/new/step-3-clean/quality-final` |  |
| `P2-M26-041` | Step_log append-only (immutable) | Cross | `/p2/pipelines/new/step-3-clean/step-log` |  |
| `P2-M26-042` | Chọn loại phân tích (Basic / Intermediate / Advanced) — xem Section 2.8 | L5 | `/p2/pipelines/new/step-4-analyze/tier` |  |
| `P2-M26-043` | Chọn analysis framework (SWOT/6W2H/Fishbone/MoM) — xem Section 2.9 | L3 | `/p2/pipelines/new/step-4-analyze/framework` |  |
| `P2-M26-046` | Run analysis | L3 | `/p2/pipelines/new/step-4-analyze/run` |  |
| `P2-M26-047` | Realtime progress bar | L5 | `/p2/pipelines/new/step-4-analyze/progress` |  |
| `P2-M26-048` | Summary stats card sau khi xong | L5 | `/p2/pipelines/new/step-4-analyze/summary` |  |
| `P2-M26-049` | Dashboard 4-panel charts (chọn từ Chart Library — xem Section 2.14) | L5 | `/p2/pipelines/new/step-5-results/charts` |  |
| `P2-M26-050` | Widget KPI theo loại phân tích | L5 | `/p2/pipelines/new/step-5-results/kpi` |  |
| `P2-M26-052` | Recommended actions list | L3 + L4 | `/p2/pipelines/new/step-5-results/actions` |  |
| `P2-M26-053` | Filter / search result | L5 | `/p2/pipelines/new/step-5-results` |  |
| `P2-M26-054` | Export PDF report có branding tổ chức | L5 | `/p2/pipelines/new/step-5-results/export/pdf` |  |
| `P2-M26-055` | Export CSV / Excel | L5 | `/p2/pipelines/new/step-5-results/export/tabular` |  |
| `P2-M26-056` | Export chart PNG/SVG | L5 | `/p2/pipelines/new/step-5-results/export/image` |  |
| `P2-M26-057` | Share link (có quyền) | L5 | `/p2/pipelines/new/step-5-results/share` |  |
| `P2-M27-002` | Đề xuất schema tối ưu (chuẩn hóa 3NF hoặc star schema) | L3 | `/p2/auto-db/schema-suggestion` |  |
| `P2-M27-003` | Auto-generate CREATE TABLE scripts | L0 | `/p2/auto-db/ddl` |  |
| `P2-M27-004` | Auto-generate index đề xuất | L5 | `/p2/auto-db/indexes` |  |
| `P2-M27-005` | Auto-generate ERD (Entity Relationship Diagram) | L3 | `/p2/auto-db/erd` |  |
| `P2-M27-007` | Đề xuất quy trình nhập liệu (form structure, validation rules) | L5 | `/p2/auto-db/forms` |  |
| `P2-M27-008` | Tạo data entry form tự động từ schema | L5 | `/p2/auto-db/forms/generate` |  |
| `P2-M27-011` | Đánh giá data quality improvement qua thời gian | L2 | `/p2/auto-db/quality-trend` |  |
| `P2-M27-012` | Version control schema (migration scripts) | L5 | `/p2/auto-db/migrations` |  |
| `P2-M210-002` | "Chuyện gì đang xảy ra?" — What is happening (factual description) | L3 | `/p2/insights/what` |  |
| `P2-M210-003` | "Tại sao xảy ra?" — Why (causal analysis từ correlation + context) | L3 | `/p2/insights/why` |  |
| `P2-M210-004` | "Nên làm gì?" — Recommended actions (action plan từ best practices) | L3 + L4 | `/p2/insights/what-to-do` |  |
| `P2-M210-006` | Dẫn chứng từ data (data citation) | L3 | `/p2/insights/:id/citations/data` |  |
| `P2-M210-007` | Dẫn chứng từ tài liệu user (document citation) | L3 | `/p2/insights/:id/citations/documents` |  |
| `P2-M210-013` | Vector embedding + index | L3 | `/p2/insights/knowledge-base/embed` |  |
| `P2-M210-015` | Quản lý phiên bản tài liệu | L3 | `/p2/insights/knowledge-base/versions` |  |
| `P2-M210-016` | Kiểm soát quyền truy cập tài liệu (role-based) | L3 | `/p2/insights/knowledge-base/access` |  |
| `P2-M215-001` | List decisions (pagination 50/page) | L3 + L5 | `/p2/decisions` |  |
| `P2-M215-002` | Filter date range / type / confidence | L3 | `/p2/decisions` |  |
| `P2-M215-003` | Filter has_override | L3 | `/p2/decisions` |  |
| `P2-M215-004` | Full-text search (GIN trigram AP-12) | L3 | `/p2/decisions/search` |  |
| `P2-M215-005` | Sort columns | L3 | `/p2/decisions` |  |
| `P2-M215-006` | Export CSV (max 10,000 records) | L3 | `/p2/decisions/export` |  |
| `P2-M215-007` | Immutable UI (no edit/delete) | L3 + L5 | `/p2/decisions/:id` |  |
| `P2-M216-001` | Xem features JSONB + output NUMERIC + confidence | L3 | `/p2/decisions/:id/features` |  |
| `P2-M216-003` | Override form (Operator+) | L3 | `/p2/decisions/:id/override` |  |
| `P2-M216-004` | Nhập lý do override | L3 | `/p2/decisions/:id/override/reason` |  |
| `P2-M216-006` | Decision gốc immutable | L3 | `/p2/decisions/:id` |  |
| `P2-M219-003` | Warning khi quota >80% | L5 | `/p2/subscription/quota/alerts` |  |
| `P2-M219-004` | Critical khi quota >95% | L5 | `/p2/subscription/quota/alerts` |  |
| `P2-M219-005` | Tab Gói — tên, giá VND+USD | L5 | `/p2/subscription/plan` |  |
| `P2-M219-006` | Tab Upgrade — comparison 4 gói | L5 | `/p2/subscription/upgrade` |  |
| `P2-M219-007` | 1-click upgrade | L5 | `/p2/subscription/upgrade/:plan` |  |
| `PM-PII-013` | Mining session approval gates (consent flow) | L4.5 + Cross | `/process-mining/sessions/{id}/pii-config` | ⭐ |
| `PM-ANM-022` | Shadow process detection (off-system steps) | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `PM-OUT-028` | Findings report generation (human-readable) | L4 + L4.5 | `POST /process-mining/sessions/{id}/translate-to-builder` | ⭐ |
| `PM-OUT-029` | Workflow YAML auto-generation | L4 + L4.5 | `POST /process-mining/sessions/{id}/translate-to-builder` | ⭐ |
| `PM-OUT-030` | Off-system steps tagging in YAML | L4 + L4.5 | `POST /process-mining/sessions/{id}/translate-to-builder` | ⭐ |
| `PM-OUT-031` | Bottleneck flagging in builder | L4 + L4.5 | `POST /process-mining/sessions/{id}/translate-to-builder` | ⭐ |
| `PM-OUT-032` | User decision UI on findings | L4 + L4.5 | `POST /process-mining/sessions/{id}/translate-to-builder` | ⭐ |
| `PM-OUT-033` | Workflow draft creation from mining | L4 + L4.5 | `POST /process-mining/sessions/{id}/translate-to-builder` | ⭐ |
| `NOV-RPT-019` | Manager email digest (monthly) | L4.5 + L5 | `GET /economics/reports/manager-digest` | ⭐ |
| `NOV-RPT-021` | ROI Dashboard (real-time) | L4.5 + L5 | `GET /economics/reports/manager-digest` | ⭐ |
| `NOV-RPT-022` | Workflow ROI ranking (top performers) | L4.5 + L5 | `GET /economics/reports/manager-digest` | ⭐ |

**Studio (43)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P3-M30-001` | Đăng nhập Studio User (Kaori Staff / Enterprise Analyst) | L3 + L5 | `/p3/auth/login` |  |
| `P3-M30-003` | Quên / Reset mật khẩu | L3 + L5 | `/p3/auth/forgot-password` |  |
| `P3-M30-004` | Đăng xuất | L5 | `/p3/auth/logout` |  |
| `P3-M30-005` | Đổi mật khẩu | L5 | `/p3/auth/change-password` |  |
| `P3-M30-009` | Rate Limit (5 lần → lock 15 phút) | L5 + Cross | `/p3/auth/login` |  |
| `P3-M31-001` | Xem projects được assign | L5 | `/p3/home/projects` |  |
| `P3-M31-002` | Activity feed (50 records) | L4 | `/p3/home/activity` |  |
| `P3-M31-003` | Shortcut tạo project | L5 | `/p3/home/create-project` |  |
| `P3-M31-004` | Shortcut compose report | L5 | `/p3/home/compose-report` |  |
| `P3-M31-005` | Role badge hiển thị | L5 | `/p3/home/profile-badge` |  |
| `P3-M31-006` | Isolation: Analyst chỉ thấy enterprise mình | L5 | `/p3/home` |  |
| `P3-M32-001` | List projects table | L5 | `/p3/projects` |  |
| `P3-M32-002` | Filter theo enterprise (Kaori Staff) | L5 | `/p3/projects` |  |
| `P3-M32-003` | Filter theo status (ACTIVE/ARCHIVED/DRAFT) | L5 | `/p3/projects` |  |
| `P3-M32-004` | Tạo project mới | L5 | `/p3/projects/new` |  |
| `P3-M32-005` | Archive project | L5 | `/p3/projects/:id/archive` |  |
| `P3-M32-006` | Auto-assign creator as lead | L5 | `/p3/projects/new` |  |
| `P3-M33-001` | Xem info project | L3 | `/p3/projects/:id` |  |
| `P3-M33-002` | Tab Members (junction AP-1) | L3 | `/p3/projects/:id/members` |  |
| `P3-M33-003` | Add/remove members | L3 | `/p3/projects/:id/members/manage` |  |
| `P3-M33-004` | Assign role (LEAD/MEMBER/REVIEWER) | L3 | `/p3/projects/:id/members/:uid/role` |  |
| `P3-M33-005` | Tab Models | L3 | `/p3/projects/:id/models` |  |
| `P3-M33-006` | Tab Reports | L3 | `/p3/projects/:id/reports` |  |
| `P3-M33-008` | Edit (chỉ lead) | L3 | `/p3/projects/:id/edit` |  |
| `P3-M34-001` | List models | L5 | `/p3/models` |  |
| `P3-M34-003` | Xem checksum CHAR(64) AP-6 | L5 | `/p3/models/:id/versions/:ver/checksum` |  |
| `P3-M34-004` | Xem metrics NUMERIC(5,4) AP-7 | L5 | `/p3/models/:id/versions/:ver/metrics` |  |
| `P3-M34-006` | State machine DRAFT → STAGING → DEPLOYED → ARCHIVED | L4 | `/p3/models/:id/versions/:ver/state` |  |
| `P3-M34-007` | Promote DEPLOYED (yêu cầu +2% accuracy) | L5 | `/p3/models/:id/versions/:ver/promote` |  |
| `P3-M34-008` | Rollback version | L5 | `/p3/models/:id/versions/:ver/rollback` |  |
| `P3-M35-001` | Chart loss/accuracy by epoch | L3 | `/p3/training-log/:runId/chart` |  |
| `P3-M35-002` | Compare epochs | L3 | `/p3/training-log/:runId/compare` |  |
| `P3-M35-003` | Xem hyperparameters | L3 | `/p3/training-log/:runId/hyperparams` |  |
| `P3-M35-004` | Xem dataset info | L2 + L3 | `/p3/training-log/:runId/dataset` |  |
| `P3-M35-005` | Readonly (immutable) | L3 + L5 | `/p3/training-log/:runId` |  |
| `P3-M36-001` | Rich text editor | L5 | `/p3/reports/composer/editor` |  |
| `P3-M36-002` | Attach files | L5 | `/p3/reports/composer/attachments` |  |
| `P3-M36-004` | Chọn enterprise nhận | L5 | `/p3/reports/composer/recipients` |  |
| `P3-M36-005` | Draft autosave 30s | L5 | `/p3/reports/composer/autosave` |  |
| `P3-M36-006` | Send report | L4 | `/p3/reports/composer/send` |  |
| `P3-M36-007` | Fan-out delivery | L5 | `/p3/reports/composer/send/fan-out` |  |
| `P3-M36-008` | Preview trước khi gửi | L5 | `/p3/reports/composer/preview` |  |
| `P3-M36-009` | Isolation: Analyst chỉ enterprise mình | L5 | `/p3/reports/composer` |  |

**Personal (48)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P4-M40-001` | Đăng nhập Personal User | L3 + L5 | `/p4/auth/login` |  |
| `P4-M40-005` | Quên / Reset mật khẩu | L5 | `/p4/auth/forgot-password` |  |
| `P4-M40-006` | Đăng xuất | L5 | `/p4/auth/logout` |  |
| `P4-M40-007` | Đổi mật khẩu | L5 | `/p4/auth/change-password` |  |
| `P4-M40-010` | Rate Limit (5 lần → lock 15 phút) | L5 + Cross | `/p4/auth/login` |  |
| `P4-M40-011` | Xóa tài khoản (GDPR-style data erasure) | L5 | `/p4/auth/delete-account` |  |
| `P4-M41-001` | KPI goals active | L5 | `/p4/dashboard/goals` |  |
| `P4-M41-002` | Streak badge (consecutive days) | L5 | `/p4/dashboard/streak` |  |
| `P4-M41-003` | Stats hôm nay NUMERIC(12,4) | L5 | `/p4/dashboard/today` |  |
| `P4-M41-005` | Chart 7 ngày (dùng Chart Library 2.14) | L5 | `/p4/dashboard/chart-7d` |  |
| `P4-M41-006` | Progress overview | L5 | `/p4/dashboard/progress` |  |
| `P4-M42-001` | Chọn type HEALTH / FINANCE / PRODUCTIVITY / GENERIC | L1 | `/p4/uploads/new` |  |
| `P4-M42-003` | Progress bar realtime | L1 + L5 | `/p4/uploads/new/progress` |  |
| `P4-M42-004` | Checksum SHA-256 (AP-6) | L1 | `/p4/uploads/checksum` |  |
| `P4-M42-005` | Virus scan | L1 | `/p4/uploads/virus-scan` |  |
| `P4-M42-006` | Status lifecycle PENDING → PROCESSING → READY/ERROR | L1 + L4 | `/p4/uploads/:id/status` |  |
| `P4-M43-001` | List files | L1 | `/p4/library` |  |
| `P4-M43-002` | Filter type / status | L5 | `/p4/library` |  |
| `P4-M43-003` | Preview 10 dòng | L5 | `/p4/library/:id/preview` |  |
| `P4-M43-004` | Soft-delete (giữ 30 ngày) + Restore | L5 | `/p4/library/:id/restore` |  |
| `P4-M44-001` | Wizard 5 bước (Tải → Nhận diện → Làm sạch → Phân tích → Kết quả) | L5 | `/p4/pipelines/new` |  |
| `P4-M44-002` | Basic analysis only (nâng cấp để unlock Intermediate/Advanced) | L3 | `/p4/pipelines/new/step-4-analyze` |  |
| `P4-M45-001` | Tree view Goal → Plan → Strategy | L5 | `/p4/goals/tree` |  |
| `P4-M45-002` | Tạo Goal (target_value NUMERIC(12,4)) | L5 | `/p4/goals/new` |  |
| `P4-M45-003` | Add Plan dưới Goal | L5 | `/p4/goals/:id/plans/new` |  |
| `P4-M45-004` | Add Strategy dưới Plan | L5 | `/p4/goals/:id/plans/:pid/strategies/new` |  |
| `P4-M45-006` | Edit inline | L5 | `/p4/goals/:id/edit` |  |
| `P4-M45-007` | Progress circle auto-compute | L5 | `/p4/goals/:id/progress` |  |
| `P4-M45-008` | Max 10 goals active per user | L5 | `/p4/goals` |  |
| `P4-M46-001` | Target vs progress chart | L3 | `/p4/goals/:id/chart` |  |
| `P4-M46-002` | Plans accordion | L3 | `/p4/goals/:id/plans` |  |
| `P4-M46-003` | Strategy checklist | L3 | `/p4/goals/:id/strategies` |  |
| `P4-M46-004` | Edit inline | L3 | `/p4/goals/:id/edit` |  |
| `P4-M46-005` | Archive goal | L3 | `/p4/goals/:id/archive` |  |
| `P4-M47-001` | Quick-log value + note | L5 | `/p4/tracking/quick-log` |  |
| `P4-M47-002` | measured_value NUMERIC(12,4) | L5 | `/p4/tracking/quick-log/value` |  |
| `P4-M47-003` | 1 log/goal/day (update nếu đã có) | L5 | `/p4/tracking/quick-log/constraint` |  |
| `P4-M47-004` | Line chart target vs actual | L5 | `/p4/tracking/chart` |  |
| `P4-M47-005` | Calendar heatmap | L5 | `/p4/tracking/calendar` |  |
| `P4-M47-006` | Partition by (user, month) | L5 | `/p4/tracking/partitioning` |  |
| `P4-M48-001` | List suggestions sort relevance DESC | L3 | `/p4/suggestions` |  |
| `P4-M48-002` | relevance_score NUMERIC(5,4) AP-7 | L3 | `/p4/suggestions/:id/score` |  |
| `P4-M48-003` | Action Accept / Dismiss / Later | L3 + L4 | `/p4/suggestions/:id/action` |  |
| `P4-M48-004` | Filter by type | L3 | `/p4/suggestions` |  |
| `P4-M48-005` | Unread badge | L3 | `/p4/suggestions/badge` |  |
| `P4-M49-002` | Theme sáng/tối | L5 | `/p4/customize/theme` |  |
| `P4-M49-003` | Chọn màu accent yêu thích | L5 | `/p4/customize/accent-color` |  |
| `P4-M49-004` | Ngôn ngữ (VN/EN) | L5 | `/p4/customize/language` |  |

**Cross-cutting (43)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `SH-M51-002` | COUNT(DISTINCT customer_external_id) per month | L5 | `/shared/billing-engine/unique-count` |  |
| `SH-M51-003` | Lưu vào enterprise_monthly_billing | L5 | `/shared/billing-engine/store` |  |
| `SH-M51-004` | Trigger alert khi >80% quota | L5 | `/shared/billing-engine/alerts` |  |
| `SH-M51-005` | Partition by billing_month | L5 | `/shared/billing-engine/partitioning` |  |
| `SH-M51-006` | Chống gaming split-batch | L5 | `/shared/billing-engine/anti-gaming` |  |
| `SH-M52-002` | Inject WHERE enterprise_id = X | Cross | `/shared/isolation/query-guard` |  |
| `SH-M52-003` | Deny 403 nếu mismatch | Cross | `/shared/isolation/deny` |  |
| `SH-M52-004` | Audit log mọi access denied | Cross | `/shared/isolation/audit` |  |
| `SH-M52-005` | Row-level isolation tại API layer | Cross | `/shared/isolation/row-level` |  |
| `SH-M53-001` | Compute SHAP values tại inference | L3 | `/shared/explainability/shap` |  |
| `SH-M53-002` | Translate thành top 3 factors tiếng Việt | L3 | `/shared/explainability/top-factors` |  |
| `SH-M53-003` | Business language (không số kỹ thuật) | L3 | `/shared/explainability/business-language` |  |
| `SH-M53-004` | Lưu top_factors JSONB | L3 | `/shared/explainability/store` |  |
| `SH-M54-001` | Async write audit_logs | L0 + Cross | `/shared/audit/writer` |  |
| `SH-M54-002` | Include actor_id, action, resource, timestamp, IP | L4 + Cross | `/shared/audit/schema` |  |
| `SH-M54-003` | Immutable (no edit/delete) | Cross | `/shared/audit/immutable` |  |
| `SH-M54-004` | Partition monthly + Retention 2 năm | Cross | `/shared/audit/partitioning` |  |
| `SH-M54-005` | Query indexed | Cross | `/shared/audit/search` |  |
| `SH-M57-004` | Data lineage graph | L5 | `/shared/medallion/lineage` |  |
| `SH-M57-005` | Incremental load support (Phase 2) | L1 | `/shared/medallion/incremental` |  |
| `SH-M57-006` | Time travel (query snapshot cũ) — Phase 2 | L5 | `/shared/medallion/time-travel` |  |
| `SH-M58-001` | Backend chart rendering (server-side cho PDF/PPT export) | L5 | `/shared/chart-engine/render` |  |
| `SH-M58-002` | Chart spec JSON schema (chuẩn hóa) — base cho Section 2.14 | L5 | `/shared/chart-engine/spec` |  |
| `SH-M58-003` | Theme engine (brand colors auto-apply) | L5 | `/shared/chart-engine/theme` |  |
| `SH-M58-004` | Cache chart render | L5 | `/shared/chart-engine/cache` |  |
| `SH-M58-005` | Library: Recharts / ECharts / D3 integration | L5 | `/shared/chart-engine/libraries` |  |
| `SH-M61-001` | Thêm thẻ tín dụng / ghi nợ (Visa/Master/JCB) | L5 | `/billing/methods/card/new` |  |
| `SH-M61-002` | Chuyển khoản ngân hàng (VietQR / MBQR) | L5 | `/billing/methods/bank-transfer` |  |
| `SH-M61-003` | Ví điện tử (Momo / VNPay / ZaloPay) | L5 | `/billing/methods/e-wallet` |  |
| `SH-M61-004` | Xem phương thức hiện tại | L5 | `/billing/methods` |  |
| `SH-M61-005` | Xóa phương thức | L5 | `/billing/methods/:id/delete` |  |
| `SH-M61-006` | Đặt mặc định | L5 | `/billing/methods/:id/default` |  |
| `SH-M62-001` | Tự động sinh invoice PDF hàng tháng | L5 | `/billing/invoices/auto` |  |
| `SH-M62-003` | Xem lịch sử hóa đơn | L5 | `/billing/invoices` |  |
| `SH-M62-004` | Thanh toán invoice | L4 | `/billing/invoices/:id/pay` |  |
| `SH-M62-005` | Xuất báo cáo thuế | L5 | `/billing/invoices/tax-report` |  |
| `SH-M62-006` | Hỗ trợ xuất hóa đơn điện tử Việt Nam (theo Nghị định 123) | L5 | `/billing/invoices/e-invoice-vn` |  |
| `SH-M63-001` | Auto-renewal monthly | L5 | `/billing/subscription/auto-renewal` |  |
| `SH-M63-002` | Upgrade plan (1-click, data migrate) | L5 | `/billing/subscription/upgrade` |  |
| `SH-M63-003` | Downgrade plan | L5 | `/billing/subscription/downgrade` |  |
| `SH-M63-004` | Pause subscription | L5 | `/billing/subscription/pause` |  |
| `SH-M63-005` | Cancel subscription | L5 | `/billing/subscription/cancel` |  |
| `SH-M63-006` | Refund process | L4 | `/billing/subscription/refund` |  |

---

## Phase 1.5 (M5-M6)

### ~~P15-S9~~ ✅ DONE — 90-day testing infra + Adoption full (8/10 D-pieces; D2/D4a/D4c/D8/K8s/Temporal-worker defer P2)  
*Batch:* `B1.5.1 — Stabilization & Critical Gaps`  ·  *Window:* Week 17-18  ·  *Features:* 12

> **Sprint status (2026-05-17):** ✅ 8/10 D-pieces shipped + pushed origin 2026-05-12 (`feat/p15-s9-d1`). PR #179 OPEN, CI red (June budget reset). Closed-sprint plan + review + CI backlog + PR body archived at `docs/archive/sprint/p15-s9/`. Deferred to P2 (NOT P1.5 blockers): D2 Java VaultClient + D4a Postgres CDC real + D4c Zalo metadata real + D8 dual-write cutover + K8s FPT Cloud + Temporal worker live cutover.

**Platform (2)**  

| Code | Feature | Layer | API | NEW | Status |
|---|---|---|---|---|---|
| `P1-LLM-005` | ⭐ LLM Drift Detection (compare output baselines) | L3 | `GET /platform/llm/versions/drift-report` | ⭐ | ⏳ deferred P15-S10 |
| `P1-CSM-003` | ⭐ 7 Proactive engagement triggers | L4.5 + L5 | `GET /platform/customer-success/engagement-triggers` | ⭐ | ⏳ deferred P15-S10 |

**Enterprise (7)**  

| Code | Feature | Layer | API | NEW | Status |
|---|---|---|---|---|---|
| `AI-SIG-004` | ⭐ Signal 4: Workaround file creation (parallel Excel files) | L4.5 | `GET /adoption/signals/workaround-file-creation-(para` | ⭐ | ✅ `70f0d7f` D6 (signal extractor pure-fn; data plumbing P15-S10+) |
| `AI-SIG-007` | ⭐ Signal 7: Negative sentiment in comments/feedback | L4.5 | `GET /adoption/signals/negative-sentiment-in-comments` | ⭐ | ✅ `70f0d7f` D6 (extractor; sentiment NLP route P15-S10+) |
| `AI-SIG-008` | ⭐ Signal 8: Time-on-task variance (vs baseline) | L4.5 | `GET /adoption/signals/time-on-task-variance-(vs-base` | ⭐ | ✅ `70f0d7f` D6 |
| `AI-SIG-009` | ⭐ Signal 9: Feature usage decline trend | L4.5 | `GET /adoption/signals/feature-usage-decline-trend` | ⭐ | ✅ `70f0d7f` D6 |
| `AI-INT-017` | Auto in-product nudges (training tips, walkthrough offers) | L4.5 + L5 | `POST /adoption/interventions/trigger` | ⭐ | ⏳ deferred P15-S10 |
| `AI-INT-019` | Intervention playbook (per signal type) | L4.5 + L5 | `POST /adoption/interventions/trigger` | ⭐ | ⏳ deferred P15-S10 |
| `AI-INT-020` | Intervention assignment to CSM | L4.5 + L5 | `POST /adoption/interventions/trigger` | ⭐ | ⏳ deferred P15-S10 |

**Cross-cutting (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `REL-014` | Partial rollback support | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-019` | Circuit breaker dashboard | L4 + Cross | `(internal — workflow engine)` | ⭐ |
| `REL-024` | Outbox pattern for reliable event publishing | L4 + Cross | `(internal — workflow engine)` | ⭐ |

### ~~P15-S10~~ ✅ DONE — NOV A/B + Process Mining email/calendar + RAG Router + PageIndex (stub-only)  
*Batch:* `B1.5.1 — Stabilization & Critical Gaps`  ·  *Window:* Week 19-20  ·  *Features:* 5 + 3 (RAG addendum)

> **Sprint status (2026-05-17):** ✅ all 8 D-pieces shipped + HTTP layer wired 2026-05-12. 5 endpoints exposed: `/rag/answer`, `/adoption/interventions/trigger`, `/process-mining/connectors/{gmail-outlook,calendar}`, `/economics/revenue/estimate`. PageIndex PyPI wrap stub-only (P2). Closed-sprint plan + review archived at `docs/archive/sprint/p15-s10/`.
>
> **PageIndex PyPI wrap re-decision 2026-05-18:** vendor lib `pageindex==0.2.8` exists but ships hardcoded `openai>=1.70.0` + LiteLLM bridging to other LLMs. Bridging LiteLLM → Kaori's `llm-gateway` (K-3 + K-4 Qwen-first) adds ~50 MB dep + complex routing for marginal value over the existing stub. **Decision:** keep stub implementation, classify PageIndex as "pattern borrowed not lib wrapped" per ADR-0024 (same model as mem0). The stub builder + retriever (`reasoning/rag/pageindex/`) covers the contract; future swap to a real impl will be a native Kaori implementation calling `llm-gateway` directly, not a LiteLLM bridge.

**Enterprise (5)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `PM-EVT-004` | Gmail/Outlook metadata connector (subject + thread + actors) | L1 + L4.5 | `/process-mining/connectors/gmail-outlook` | ⭐ |
| `PM-EVT-005` | Calendar metadata connector (events, attendees, recurrence) | L1 + L4.5 | `/process-mining/connectors/calendar` | ⭐ |
| `AI-INT-021` | Intervention effectiveness tracking | L4.5 + L5 | `POST /adoption/interventions/trigger` | ⭐ |
| `AI-INT-022` | Vietnamese context adaptation (Zalo, hierarchical decision) | L4.5 + L5 | `POST /adoption/interventions/trigger` | ⭐ |
| `NOV-REV-002` | A/B attribution method | L4.5 | `POST /economics/revenue/estimate` | ⭐ |

**RAG addendum 2026-05 — added to Phase 1.5 (3)**  

Added per ADR-0019 + spec `docs/specs/RAG_VECTORLESS_AND_STRUCTURED.md` after PageIndex / DocSage publication Q1 2026.

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `RAG-ROUTER-001` | RAG Router — 3-engine pluggable dispatch (pgvector / pageindex / docsage) per query characteristics | L3 | `POST /rag/answer` | ⭐ |
| `RAG-PAGEINDEX-001` | PageIndex tree builder — async build hierarchical Table-of-Contents tree from PDF/Markdown on upload | L3 | `(triggered by kaori.pipeline.events doc.uploaded)` | ⭐ |
| `RAG-PAGEINDEX-002` | PageIndex retrieval — LLM-traverse tree, return RAGAnswer with page-range citations | L3 | `POST /rag/answer` (engine=pageindex) | ⭐ |

### ~~P15-S11~~ ✅ DONE — DocSage + Stage 5/7/12 + Memory storage adapters + perf  
*Batch:* `B1.5.2 — Performance + Templates`  ·  *Window:* Week 21-22  ·  *Features:* 6 + 3 (RAG addendum)

> **Sprint status (2026-05-17):** ✅ shipped. DocSage D1→D6 (`7a47b17`..`c6e47c5`) — schema discovery + structured extraction + SQL reasoning + engine assembly + Stage 2B LLM fallback + pgvector real BGE-M3. Stage 5 Ontology 7-Primitives (`7c02538`). Stage 7 Memory 4-tier (`2ed08e4`). Stage 12 Loop A/B + Promotion (`1e0e620`). Phase 2 storage adapters Postgres+pgvector / Redis / Neo4j / Temporal (`d4ab620`..`09cbe7a`). NOV-REV-006 variance + NOV-CST-012 cost amort (`a37f215`). OBS-005 head-based sampling (`b503259`). Plan archived at `docs/sprint/P15-S11_DOCSAGE_PLAN.md`. Test delta ai-orch 623→1144 (+521).

**Enterprise (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `NOV-REV-006` | Variance analysis (predicted vs actual) | L4.5 | `POST /economics/revenue/estimate` | ⭐ |
| `NOV-CST-012` | Setup cost amortization | L4.5 | `POST /economics/cost/compute` | ⭐ |

**Cross-cutting (2)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `OBS-005` | Sampling policy (head-based) | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-020` | SLI/SLO dashboards (Grafana) | L0 + Cross | `(internal observability)` | ⭐ |

**RAG addendum 2026-05 — added to Phase 1.5 (3)**  

Added per ADR-0019. DocSage 3-module pipeline for multi-entity cross-doc QA (89.2% MEBench accuracy vs GPT-4o + RAG 62%).

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `RAG-DOCSAGE-001` | DocSage Schema Discovery — LLM derives minimal joinable schema from question + corpus sample | L3 | `(internal — RAG router subcall)` | ⭐ |
| `RAG-DOCSAGE-002` | DocSage Structured Extraction — LLM transforms unstructured docs into relational rows; cached per (schema, doc) | L3 | `(internal — RAG router subcall)` | ⭐ |
| `RAG-DOCSAGE-003` | DocSage SQL Reasoning — composes + executes SQL JOIN over Postgres temp/CTE, formats result with citations | L3 | `POST /rag/answer` (engine=docsage) | ⭐ |

### ~~P15-S12~~ ✅ DONE — CFO report + SLO alerting  
*Batch:* `B1.5.2 — Performance + Templates`  ·  *Window:* Week 23-24  ·  *Features:* 2

> **Sprint status (2026-05-17):** ✅ shipped. NOV-RPT-020 CFO quarterly digest endpoint (`66d2d31`) + OBS-017 SLO burn-rate alerts + OBS-020 SLI/SLO Grafana dashboards (`ddda88b`). Phase 1.5 sprint backlog fully closed.

**Enterprise (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `NOV-RPT-020` | CFO summary report (quarterly) | L4.5 + L5 | `GET /economics/reports/manager-digest` | ⭐ |

**Cross-cutting (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `OBS-017` | SLO-based alerting (error budget burn) | L0 + Cross | `(internal observability)` | ⭐ |

---

## Phase 2 (M7-M12)

### ~~P2-S13~~ ✅ DONE — All 8 PM sources operational  
*Batch:* `B2.1 — Process Mining Full`  ·  *Window:* Week 25-26  ·  *Features:* 3

> **Sprint status (2026-05-17):** ✅ shipped (`a299bf5`). 3 connectors: Slack/Teams audit API + Microsoft SharePoint file change + Generic webhook event log. All written contract-first (extract_events → bronze) per K-5 PII redaction.

**Enterprise (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `PM-EVT-006` | Slack/Teams audit API connector | L1 + L4.5 | `/process-mining/connectors/slack-teams` | ⭐ |
| `PM-EVT-007` | Microsoft SharePoint file change connector | L1 + L4.5 | `/process-mining/connectors/microsoft` | ⭐ |
| `PM-EVT-008` | Generic webhook event log connector | L1 + L4.5 | `/process-mining/connectors/generic` | ⭐ |

### ~~P2-S14~~ ✅ DONE — PM advanced algos + bypass detection + cohort  
*Batch:* `B2.1 — Process Mining Full`  ·  *Window:* Week 27-28  ·  *Features:* 9

> **Sprint status (2026-05-17):** ✅ shipped (`c83fb84`). 5 anomaly detectors (PM-ANM-023..027): approval bypass + rework loop + bypass risk score + conformance + token replay. Inductive Miner + Fuzzy Miner (PM-ALG-016/017). AI-HSC-016 cohort comparison. Test methodology "chuẩn chỉ + hiệu năng + phi chức năng" template established at `tests/test_p2_s14_pm_algorithms.py` (8-section).

**Enterprise (8)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `PM-ALG-016` | Inductive Miner algorithm (Phase 2) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ALG-017` | Fuzzy Miner algorithm (Phase 2) | L4.5 | `POST /process-mining/sessions/{id}/run-algorithm` | ⭐ |
| `PM-ANM-023` | Approval bypass detection | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `PM-ANM-024` | Rework loop detection | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `PM-ANM-025` | Bypass risk scoring (high-value bypass = high risk) | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `PM-ANM-026` | Conformance analysis (actual vs designed workflow) | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `PM-ANM-027` | Token replay analysis (Phase 2) | L4.5 | `GET /process-mining/sessions/{id}/anomalies` | ⭐ |
| `AI-HSC-016` | Cohort comparison (similar tenants) | L4.5 | `GET /adoption/health/{workflow_id}` | ⭐ |

### ~~P2-S15~~ ✅ DONE — All 45 nodes + 25 templates + agent palette  
*Batch:* `B2.2 — Workflow Maturity`  ·  *Window:* Week 29-30  ·  *Features:* 1

> **Sprint status (2026-05-17):** 🟢 in progress. Workflow builder BE + FE foundation shipped Tuần 8 (`b757082` + `ef42989`): mig 053 (workflows/nodes/edges/step_documents/templates) + mig 054 (18 templates auto-gen) + mig 058 (decision_nodes + folder attachments) + mig 060 (6 enterprise node types: step/decision_if_else/decision_switch/approval_gate/wait/external). 13 CRUD endpoints in `services/ai-orchestrator/routers/workflow_builder.py`. FE: `/p2/workflows` hub + builder + tree viewer. Resume plan: `docs/sprint/P2_S15_RESUME_CHECKLIST.md`. Remaining: 45 node taxonomy fully wired + 25 templates pre-canned.

**Cross-cutting (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `SH-M56b-026` | Visual agent workflow builder | L3 + L4 | `/shared/agents/studio/builder` |  |

### ~~P2-S16~~ ✅ DONE — Multi-user collab + Workflow as Code (YAML)  
*Batch:* `B2.2 — Workflow Maturity`  ·  *Window:* Week 31-32  ·  *Features:* 0

> **Sprint status (2026-05-17):** ✅ shipped early. **Workflow as Code** = mig 069 templates + `POST /workflows/import` + `GET /workflows/{id}/export.yaml` + mig 068 catalog validation (commit `e438482`). **Multi-user collab** = mig 072 (workflow_editors / workflow_comments / workflow_locks) + 10 endpoints under `/workflows/{id}/{editors,comments,lock}` with optimistic K-13 anti-IDOR pattern (this commit). +28 tests collab + 15 YAML = 43.

### P2-S17 🔴 SKIPPED — Mobile app (read + approve) — Features:0 in BACKLOG, no scope  
*Batch:* `B2.3 — Mobile + SSO + Security`  ·  *Window:* Week 33-34  ·  *Features:* 0

### ~~P2-S18~~ ✅ DONE — Observability deep-dive (anomaly + capacity + session replay)  
*Batch:* `B2.3 — Mobile + SSO + Security`  ·  *Window:* Week 35-36  ·  *Features:* 3

> **Row renamed 2026-05-17.** Original title "SSO + MFA + field-level encryption" did not match the 3 OBS-* features listed below; em rename to reflect actual scope. **Security features (SSO/MFA/field-encryption) carved out to NEW row P2-S25** below.

> **Sprint status (2026-05-17):** ✅ shipped (`1886ca8`). 3 features: OBS-018 anomaly detection (z-score + EWMA) + OBS-021 capacity planning (linear regression forecast) + OBS-023 session replay (opt-in + PII redaction, mig 073). 36 tests, 5 endpoints under `/platform/observability/*`.

**Cross-cutting (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `OBS-018` | Anomaly detection on metrics | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-021` | Capacity planning dashboard | L0 + Cross | `(internal observability)` | ⭐ |
| `OBS-023` | User session replay (opt-in) | L0 + Cross | `(internal observability)` | ⭐ |

### P2-S19 ⏭ DEFERRED Phase 3 — Extract Workflow Engine to service  
*Batch:* `B2.4 — Microservices Extraction`  ·  *Original window:* Week 37-38  ·  *Features:* 0

> **Decision 2026-05-18 (anh):** Defer to Phase 3. Rationale: Phase 2 target = 100 customers, modular monolith provides sufficient throughput. Internal split (Phase B-2) already established clean boundaries inside `services/ai-orchestrator/workflow_runtime/` so the eventual Phase 3 extraction will be a file move, not a logic rewrite. Extracting now adds K8s + service mesh complexity for no acceptance-criteria benefit. Revisit when multi-region deployment lands (Phase 3 P3-S26+).

### P2-S20 ⏭ DEFERRED Phase 3 — Extract Process Mining + service mesh  
*Batch:* `B2.4 — Microservices Extraction`  ·  *Original window:* Week 39-40  ·  *Features:* 1

> **Decision 2026-05-18 (anh):** Defer to Phase 3 alongside P2-S19. Same rationale: `org_intel/process_mining/` boundary already clean in monolith; service mesh infrastructure (Istio/Linkerd) only pays off at multi-region scale; chaos engineering (REL-025) is more valuable when there ARE distributed services to break.

**Cross-cutting (1 — deferred to Phase 3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `REL-025` | Chaos engineering test suite (Phase 2 → Phase 3) | L4 + Cross | `(internal — workflow engine)` | ⭐ |

### ~~P2-S21~~ ✅ DONE — T-Cube reasoning + OKR + NOV-RPT-023/024  
*Batch:* `B2.5 — AI Advanced + Ontology`  ·  *Window:* Week 41-42  ·  *Features:* 3

> **Sprint status (2026-05-17):** ✅ shipped early — **T-Cube trace-augmented reasoning** (D1-D4 + cron wiring + real llm-gateway adapter) AND **all 3 original sprint features**: P2-M212-001 OKR framework (mig 071 + 9 endpoints under `/p2/strategy/okr`) + NOV-RPT-023 negative-NOV workflow recommendations (`/economics/reports/manager-digest/recommendations`) + NOV-RPT-024 simulation (`/economics/reports/manager-digest/simulate`). ai-orchestrator 1261 → 1411 (+150 tests session). Mig 067-071 all ship. Defer: L4b shared cross-tenant trace memory (legal review).

**Enterprise (3)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M212-001` | Khung OKR (Objectives + Key Results) | L5 | `/p2/strategy/okr` |  |
| `NOV-RPT-023` | Negative NOV workflow recommendations | L4.5 + L5 | `GET /economics/reports/manager-digest` | ⭐ |
| `NOV-RPT-024` | NOV simulation (what-if scenarios) | L4.5 + L5 | `GET /economics/reports/manager-digest` | ⭐ |

### ~~P2-S22~~ ✅ DONE — LLM ops (P1-LLM-001/002/003/006) + NOV-CST-011 opportunity cost  
*Batch:* `B2.5 — AI Advanced + Ontology`  ·  *Window:* Week 43-44  ·  *Features:* 5

> **Sprint status (2026-05-17):** ✅ shipped — all 5 features. Mig 075 (llm_providers + tenant_llm_api_keys + llm_token_usage_daily + llm_upgrade_tests). `/platform/llm/*` 8 endpoints (catalog + api-keys CRUD + tokens breakdown + upgrade tests start/list/promote/reject). NOV-CST-011 opportunity cost in `org_intel/economics/cost.py`. Tenant API keys dogfood `shared/crypto.py` P2-ENC-001 encryption. 30 tests pass.

**Platform (4)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-LLM-001` | LLM providers catalog (Anthropic / OpenAI / Self-hosted Qwen) | L0 + L3 | `GET /platform/llm/catalog/providers` | ⭐ |
| `P1-LLM-002` | External AI API key management (AES-GCM encrypted) | L0 + L3 | `POST /platform/llm/api-keys/{provider}/new` | ⭐ |
| `P1-LLM-003` | Token quota + cost monitoring per enterprise | L3 | `GET /platform/llm/tokens/breakdown` |  |
| `P1-LLM-006` | ⭐ Controlled LLM Upgrade Process (90-day testing) | L3 | `POST /platform/llm/versions/upgrade-test` | ⭐ |

**Enterprise (1)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `NOV-CST-011` | Opportunity cost modeling | L4.5 | `POST /economics/cost/compute` | ⭐ |

### P2-S23 ⏭ GATED-ON-FE — English UI + first non-VN customer (324 features FE-heavy; FE paused per CLAUDE.md §2)  
*Batch:* `B2.6 — Internationalization + Phase 2 Wrap`  ·  *Window:* Week 45-46  ·  *Features:* 324

> **Decision 2026-05-24 (anh): Phase 2 closes here.** S22 ✅ + S24 ✅ (retro) shipped; S23 is the **only** remaining Phase 2 sprint and it is **324 features FE-heavy** (English UI + i18n catalog) — unbuildable while FE is paused (CLAUDE.md §2). Not abandoned: it is **gated on the FE restructure** (the i18n layer rides on the same wiring the restructure introduces — see the P2-03 reference pattern). Unblocks automatically when the FE restructure delivers the route/component shell + the validation/message fixtures already prepared. Until then Phase 2 is **BE-complete**; do not start S23 BE in isolation (no customer value without the FE).

**Platform (30)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P1-M18-001` | llm_providers lookup (AP-8): KAORI_VLLM_QWEN/OPENAI/ANTHROPIC/GEMINI/AZURE | L3 | `/p1/llm/catalog/providers` |  |
| `P1-M18-002` | llm_models catalog: Qwen 7B/14B/32B/72B + external models | L3 | `/p1/llm/catalog/models` |  |
| `P1-M18-003` | Model pricing config (USD + VND auto-convert) | L3 | `/p1/llm/catalog/pricing` |  |
| `P1-M18-004` | Model status machine (AVAILABLE/DEPRECATED/MAINTENANCE) | L3 + L4 | `/p1/llm/catalog/models/:id/status` |  |
| `P1-M18-005` | Deploy new model version qua config | L3 | `/p1/llm/catalog/deploy` |  |
| `P1-M18-006` | Model checksum AP-6 (verify weights integrity) | L3 | `/p1/llm/catalog/models/:id/checksum` |  |
| `P1-M18-007` | Thêm OpenAI API key (AES-GCM encrypted) | L3 | `/p1/llm/api-keys/openai/new` |  |
| `P1-M18-008` | Thêm Anthropic API key | L3 | `/p1/llm/api-keys/anthropic/new` |  |
| `P1-M18-009` | Thêm Google Gemini API key | L3 | `/p1/llm/api-keys/gemini/new` |  |
| `P1-M18-010` | Thêm Azure OpenAI endpoint + key | L3 | `/p1/llm/api-keys/azure/new` |  |
| `P1-M18-011` | API key rotation (quarterly) | L3 | `/p1/llm/api-keys/rotation` |  |
| `P1-M18-012` | Test connection trước khi enable | L3 | `/p1/llm/api-keys/:id/test` |  |
| `P1-M18-013` | Per-enterprise key override (họ dùng API key của họ) | L1 + L3 | `/p1/llm/api-keys/override` |  |
| `P1-M18-014` | Token quota per plan (max_llm_tokens_per_month) | L3 | `/p1/llm/tokens/quota` |  |
| `P1-M18-015` | Cost tracking real-time (Prometheus + Grafana) | L3 + L5 | `/p1/llm/tokens/cost-live` |  |
| `P1-M18-016` | Daily aggregation → token_usage_daily | L3 | `/p1/llm/tokens/daily` |  |
| `P1-M18-017` | Alert khi enterprise >80% token quota | L3 | `/p1/llm/tokens/alerts` |  |
| `P1-M18-018` | Cost breakdown dashboard: provider × model × enterprise | L3 + L5 | `/p1/llm/tokens/breakdown` |  |
| `P1-M18-019` | Monthly cost feed vào enterprise_monthly_billing.llm_tokens_used | L3 | `/p1/llm/tokens/billing-feed` |  |
| `P1-M18-020` | Default INTERNAL_ONLY cho all new enterprises | L3 | `/p1/llm/privacy/defaults` |  |
| `P1-M18-021` | Platform Admin toggle default mode (INTERNAL/HYBRID/EXTERNAL) | L3 | `/p1/llm/privacy/defaults/edit` |  |
| `P1-M18-022` | Enterprise Manager override per-analysis | L3 | `/p1/llm/privacy/override` |  |
| `P1-M18-023` | User-level force INTERNAL_ONLY (trumps enterprise config) | L3 | `/p1/llm/privacy/user-force` |  |
| `P1-M18-024` | Audit log mọi privacy decision | L3 + Cross | `/p1/llm/privacy/audit` |  |
| `P1-M18-025` | prompt_templates catalog (global + per-enterprise) | L3 | `/p1/llm/prompts/catalog` |  |
| `P1-M18-026` | Versioned prompts (append-only versions) | L3 | `/p1/llm/prompts/:id/versions` |  |
| `P1-M18-027` | Rollback to previous version | L3 | `/p1/llm/prompts/:id/versions/:ver/rollback` |  |
| `P1-M18-028` | Similarity search (pgvector) — tìm prompt tương tự | L3 | `/p1/llm/prompts/search` |  |
| `P1-M18-029` | Phase 2: Visual prompt editor UI | L3 + L5 | `/p1/llm/prompts/editor` |  |
| `P1-M18-030` | Phase 2: A/B testing prompts (prompt_ab_experiments) | L3 | `/p1/llm/prompts/ab` |  |

**Enterprise (181)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M20a-001` | Catalog permissions (~80 atomic permissions: resource:action) | L4 + L5 | `/p2/authz/rbac/permissions` |  |
| `P2-M20a-002` | SYSTEM roles cố định (10 roles cross-portal) | L5 + Cross | `/p2/authz/rbac/roles` |  |
| `P2-M20a-003` | role_permissions junction (AP-1) | L5 + Cross | `/p2/authz/rbac/roles/:id/permissions` |  |
| `P2-M20a-004` | user_role_assignments junction (AP-1) cross-portal | L5 + Cross | `/p2/authz/rbac/users/:id/roles` |  |
| `P2-M20a-005` | Assign role cho user (by Manager/Admin) | L5 + Cross | `/p2/authz/rbac/assign` |  |
| `P2-M20a-006` | Revoke role | L0 + L5 | `/p2/authz/rbac/revoke` |  |
| `P2-M20a-007` | Multi-role per user (MANAGER + ANALYST cùng lúc) | L5 + Cross | `/p2/authz/rbac/users/:id/roles` |  |
| `P2-M20a-008` | Role expiry (temporary role — TTL) | L3 + L5 | `/p2/authz/rbac/assignments/:id/expiry` |  |
| `P2-M20a-009` | Min 1 MANAGER active per enterprise | L5 + Cross | `/p2/authz/rbac/guardrails/manager-min` |  |
| `P2-M20a-010` | Permission check middleware (Java + Python) | L5 + Cross | `/p2/authz/rbac/middleware` |  |
| `P2-M20a-011` | Redis cache role-permission TTL 15 phút | L0 + L5 | `/p2/authz/rbac/cache` |  |
| `P2-M20a-012` | Invalidate cache qua Kafka event khi role update | L0 + L5 | `/p2/authz/rbac/cache/invalidate` |  |
| `P2-M20a-013` | Enterprise Manager tự tạo custom role | L5 + Cross | `/p2/authz/rbac/custom-roles/new` |  |
| `P2-M20a-014` | Pick permissions từ catalog | L5 + Cross | `/p2/authz/rbac/custom-roles/new` |  |
| `P2-M20a-015` | Clone existing role làm starting point | L5 + Cross | `/p2/authz/rbac/custom-roles/new` |  |
| `P2-M20a-016` | Max 20 custom roles/enterprise (ENT BASIC), unlimited ENT MAX | L5 + Cross | `/p2/authz/rbac/custom-roles` |  |
| `P2-M20a-017` | Warning khi role over-privileged (> 50 permissions) | L5 + Cross | `/p2/authz/rbac/custom-roles/:id/warnings` |  |
| `P2-M20a-018` | abac_policies table với condition DSL + compiled JSON AST | L5 + Cross | `/p2/authz/abac/policies` |  |
| `P2-M20a-019` | Policy effect: ALLOW / DENY | L5 + Cross | `/p2/authz/abac/policies/:id` |  |
| `P2-M20a-020` | Combining algorithm: DENY_OVERRIDES (default), PERMIT_OVERRIDES, FIRST_APPLICABLE | L5 + Cross | `/p2/authz/abac/combining` |  |
| `P2-M20a-021` | Attribute sources: SUBJECT (user) / RESOURCE / ACTION / ENVIRONMENT | L4 + L5 | `/p2/authz/abac/attributes` |  |
| `P2-M20a-022` | Subject attributes: role, department, region, clearance_level, custom | L5 + Cross | `/p2/authz/abac/attributes/subject` |  |
| `P2-M20a-023` | Resource attributes: owner_id, confidentiality, team, tags (JSONB) | L5 + Cross | `/p2/authz/abac/attributes/resource` |  |
| `P2-M20a-024` | Environment attributes: current_time, ip_address, device_type, day_of_week | L5 + Cross | `/p2/authz/abac/attributes/environment` |  |
| `P2-M20a-025` | Operators: EQ, NEQ, IN, NOT_IN, GT, LT, CONTAINS, MATCHES_REGEX | L3 + L5 | `/p2/authz/abac/operators` |  |
| `P2-M20a-026` | Built-in policy: "Deny cross-tenant access" priority 1000 | L5 + Cross | `/p2/authz/abac/policies/builtin/cross-tenant` |  |
| `P2-M20a-027` | Built-in policy: "Pilot expiry block" | L3 + L5 | `/p2/authz/abac/policies/builtin/pilot-expiry` |  |
| `P2-M20a-028` | Built-in policy: "PII masking External AI" | L3 + L5 | `/p2/authz/abac/policies/builtin/pii-mask` |  |
| `P2-M20a-029` | Built-in policy: "Business-hours decision override" | L3 + L5 | `/p2/authz/abac/policies/builtin/business-hours` |  |
| `P2-M20a-030` | PDP service (Java Spring Boot bean) | L5 + Cross | `/p2/authz/pdp/service` |  |
| `P2-M20a-031` | Step 1: RBAC gate check (~1ms với Redis cache) | L0 + L3 | `/p2/authz/pdp/rbac-gate` |  |
| `P2-M20a-032` | Step 2: ABAC evaluation (policies fetch + AST eval) | L5 + Cross | `/p2/authz/pdp/abac-eval` |  |
| `P2-M20a-033` | Attribute resolver (fetch từ user/resource/env context) | L5 + Cross | `/p2/authz/pdp/attribute-resolver` |  |
| `P2-M20a-034` | Combining algorithm implementation | L3 + L5 | `/p2/authz/pdp/combining` |  |
| `P2-M20a-035` | Fail-secure default: DENY khi PDP timeout/error | L3 + L5 | `/p2/authz/pdp/fail-secure` |  |
| `P2-M20a-036` | p99 < 5ms RBAC-only | L0 + L5 | `/p2/authz/pdp/slo` |  |
| `P2-M20a-037` | p99 < 20ms Hybrid (≤3 policies) | L5 + Cross | `/p2/authz/pdp/slo` |  |
| `P2-M20a-038` | p99 < 50ms Hybrid (>3 policies) — alert nếu vượt | L5 + Cross | `/p2/authz/pdp/slo/alerts` |  |
| `P2-M20a-039` | Async decision log qua Kafka | L0 + L5 | `/p2/authz/pdp/decision-log` |  |
| `P2-M20a-040` | Visual rule builder (drag-drop conditions) | L3 + L5 | `/p2/authz/abac/builder/visual` |  |
| `P2-M20a-041` | DSL editor với syntax highlighting | L5 + Cross | `/p2/authz/abac/builder/dsl` |  |
| `P2-M20a-042` | Policy simulation (test với sample subject/resource) | L5 + Cross | `/p2/authz/abac/builder/simulate` |  |
| `P2-M20a-043` | Policy version history + rollback | L5 + Cross | `/p2/authz/abac/policies/:id/versions` |  |
| `P2-M20a-044` | Policy impact analysis (xem có bao nhiêu user/resource affected) | L3 + L5 | `/p2/authz/abac/policies/:id/impact` |  |
| `P2-M20a-045` | Template policies (10 pre-built: tenant isolation, PII, time-based, ...) | L5 + Cross | `/p2/authz/abac/templates` |  |
| `P2-M20a-046` | User A ủy quyền user B hành động tạm thời | L5 + Cross | `/p2/authz/delegation/new` |  |
| `P2-M20a-047` | Max 30 ngày TTL | L5 + Cross | `/p2/authz/delegation/policy` |  |
| `P2-M20a-048` | Không recursive (B không delegate tiếp) | L3 + L5 | `/p2/authz/delegation/policy` |  |
| `P2-M20a-049` | Reason bắt buộc | L5 + Cross | `/p2/authz/delegation/new` |  |
| `P2-M20a-050` | Revoke anytime | L5 + Cross | `/p2/authz/delegation/:id/revoke` |  |
| `P2-M20a-051` | Audit log đầy đủ | L4 + L5 | `/p2/authz/delegation/audit` |  |
| `P2-M20a-052` | authorization_decisions PARTITIONED monthly | L5 + Cross | `/p2/authz/audit/decisions` |  |
| `P2-M20a-053` | Log mọi ALLOW/DENY với reason + attributes snapshot | L5 + Cross | `/p2/authz/audit/decisions/:id` |  |
| `P2-M20a-054` | Retention 90 ngày | L5 + Cross | `/p2/authz/audit/retention` |  |
| `P2-M20a-055` | DENY dashboard (monitor denied access patterns) | L0 + L5 | `/p2/authz/audit/denies` |  |
| `P2-M20a-056` | Explainability: "Why was I denied?" cho user view own | L3 + L5 | `/p2/authz/audit/why-denied` |  |
| `P2-M20a-057` | Sampled logging khi volume cao (10% ALLOW + 100% DENY) | L5 + Cross | `/p2/authz/audit/sampling` |  |
| `P2-M20a-058` | Role matrix report (ai có quyền gì) | L3 + L5 | `/p2/authz/compliance/role-matrix` |  |
| `P2-M20a-059` | Permission drift detection (role bị thay đổi bất thường) | L5 + Cross | `/p2/authz/compliance/drift` |  |
| `P2-M20a-060` | Privilege creep analysis (user tích lũy nhiều roles theo thời gian) | L3 + L5 | `/p2/authz/compliance/creep` |  |
| `P2-M20a-061` | Export permission audit (PDF cho SOC 2) | L5 + Cross | `/p2/authz/compliance/export` |  |
| `P2-M20a-062` | Policy coverage report (resource nào chưa có policy) | L3 + L5 | `/p2/authz/compliance/coverage` |  |
| `P2-M211-001` | Risk radar dashboard (heat map xác suất × impact) | L5 | `/p2/risks/radar` |  |
| `P2-M211-002` | Auto-detect rủi ro từ data (anomaly, trend negative, threshold breach) | L3 | `/p2/risks/auto-detect` |  |
| `P2-M211-003` | Thêm rủi ro thủ công | L5 | `/p2/risks/new` |  |
| `P2-M211-004` | Phân loại rủi ro (Financial / Operational / Compliance / Reputation / Strategic) | L5 | `/p2/risks/categories` |  |
| `P2-M211-005` | Tính risk score = probability × impact | L5 | `/p2/risks/:id/score` |  |
| `P2-M211-006` | Đề xuất mitigation từ AI | L3 | `/p2/risks/:id/ai-mitigation` |  |
| `P2-M211-007` | Gán owner cho rủi ro | L5 | `/p2/risks/:id/owner` |  |
| `P2-M211-008` | Theo dõi trạng thái (OPEN / MITIGATING / CLOSED / ACCEPTED) | L4 | `/p2/risks/:id/status` |  |
| `P2-M211-009` | Alert khi rủi ro escalate (risk score tăng) | L5 | `/p2/risks/:id/alerts` |  |
| `P2-M211-010` | Export risk register | L5 | `/p2/risks/export` |  |
| `P2-M212-002` | Khung OGSM (Objective/Goal/Strategy/Measure) | L5 | `/p2/strategy/ogsm` |  |
| `P2-M212-003` | AI đề xuất strategy từ insights + benchmark | L3 + L5 | `/p2/strategy/ai-suggest` |  |
| `P2-M212-004` | Link strategy → risks cần mitigate | L5 | `/p2/strategy/:id/risks` |  |
| `P2-M212-005` | Link strategy → actions từ insights | L3 + L4 | `/p2/strategy/:id/actions` |  |
| `P2-M212-006` | Timeline roadmap (Gantt chart) | L5 | `/p2/strategy/:id/timeline` |  |
| `P2-M212-007` | Assign responsible team/person | L5 | `/p2/strategy/:id/assignments` |  |
| `P2-M212-008` | Track progress theo KR/Measure | L5 | `/p2/strategy/:id/progress` |  |
| `P2-M212-009` | Review meeting template (auto-generate agenda) | L5 | `/p2/strategy/:id/review-meetings` |  |
| `P2-M212-010` | Export strategy PDF/PPT | L5 | `/p2/strategy/:id/export` |  |
| `P2-M217-001` | Drag-drop canvas | L3 + L4 | `/p2/workflows/builder` |  |
| `P2-M217-002` | Config panel per step | L4 + L5 | `/p2/workflows/builder/:step/config` |  |
| `P2-M217-003` | Auto-versioning | L4 + L5 | `/p2/workflows/:id/versions` |  |
| `P2-M217-004` | Rollback version (30 ngày) | L4 + L5 | `/p2/workflows/:id/versions/:v/rollback` |  |
| `P2-M217-005` | Publish → ACTIVE | L4 + L5 | `/p2/workflows/:id/publish` |  |
| `P2-M217-006` | Trigger: manual / schedule / AI decision / risk escalate | L3 + L4 | `/p2/workflows/:id/triggers` |  |
| `P2-M217-007` | Test mode với historical data | L4 + L5 | `/p2/workflows/:id/test` |  |
| `P2-M217-008` | Action library (email/webhook/CRM/Slack/SMS) | L1 + L3 | `/p2/workflows/actions` |  |
| `P2-M218-001` | Tạo rule (tên, condition, threshold) | L5 | `/p2/alerts/new` |  |
| `P2-M218-002` | Add channels EMAIL / SLACK / WEBHOOK / SMS (AP-1) | L1 + L3 | `/p2/alerts/:id/channels` |  |
| `P2-M218-003` | Test notification | L5 | `/p2/alerts/:id/test` |  |
| `P2-M218-004` | Rate limit 1 alert/5 phút/rule | Cross | `/p2/alerts/:id/rate-limit` |  |
| `P2-M218-005` | Alert cho risk escalate | L5 | `/p2/alerts/risk-escalate` |  |
| `P2-M218-006` | Alert cho data quality drop | L2 | `/p2/alerts/quality-drop` |  |
| `P2-M220-001` | Chọn billing_month | L4.5 | `/p2/billing/roi` |  |
| `P2-M220-002` | Xem breakdown base + overage + ROI bonus | L3 + L4.5 | `/p2/billing/roi/breakdown` |  |
| `P2-M220-003` | Download PDF | L4.5 | `/p2/billing/roi/download/pdf` |  |
| `P2-M220-004` | Export Excel | L4.5 | `/p2/billing/roi/download/xlsx` |  |
| `P2-M221-001` | Node: Dataset (Bronze / Silver / Gold) | L1 + L2 | `/p2/knowledge-graph/nodes/datasets` |  |
| `P2-M221-002` | Node: Column (tên, type, null_rate, sample values, quality_score) | L5 | `/p2/knowledge-graph/nodes/columns` |  |
| `P2-M221-003` | Node: Pipeline (config + lịch sử run) | L5 | `/p2/knowledge-graph/nodes/pipelines` |  |
| `P2-M221-004` | Node: Transformation (cleaning rule, derived formula) | L5 | `/p2/knowledge-graph/nodes/transformations` |  |
| `P2-M221-005` | Node: Metric / KPI (công thức tính, đơn vị) | L5 | `/p2/knowledge-graph/nodes/metrics` |  |
| `P2-M221-006` | Node: Report (auto-gen / user-created / template) | L5 | `/p2/knowledge-graph/nodes/reports` |  |
| `P2-M221-007` | Node: Dashboard / Widget | L5 | `/p2/knowledge-graph/nodes/dashboards` |  |
| `P2-M221-008` | Node: ML Model (version, checksum AP-6) | L5 | `/p2/knowledge-graph/nodes/models` |  |
| `P2-M221-009` | Node: Insight (từ Insights Engine 2.10) | L3 | `/p2/knowledge-graph/nodes/insights` |  |
| `P2-M221-010` | Node: Document / Knowledge Base file (PDF/DOCX/MD) | L5 | `/p2/knowledge-graph/nodes/documents` |  |
| `P2-M221-011` | Node: User / Team (owner, consumer) | L5 | `/p2/knowledge-graph/nodes/users` |  |
| `P2-M221-012` | Edge: SOURCED_FROM (Silver ← Bronze) | L1 + L2 | `/p2/knowledge-graph/edges/sourced-from` |  |
| `P2-M221-013` | Edge: DERIVED_FROM (Gold ← Silver) | L2 | `/p2/knowledge-graph/edges/derived-from` |  |
| `P2-M221-014` | Edge: TRANSFORMED_BY (Dataset ← Pipeline) | L2 | `/p2/knowledge-graph/edges/transformed-by` |  |
| `P2-M221-015` | Edge: USES_COLUMN (Metric → Column) | L5 | `/p2/knowledge-graph/edges/uses-column` |  |
| `P2-M221-016` | Edge: COMPUTED_BY (Metric ← Formula) | L5 | `/p2/knowledge-graph/edges/computed-by` |  |
| `P2-M221-017` | Edge: DISPLAYED_IN (Metric → Widget → Dashboard) | L5 | `/p2/knowledge-graph/edges/displayed-in` |  |
| `P2-M221-018` | Edge: REFERENCED_IN (Column → Report) | L5 | `/p2/knowledge-graph/edges/referenced-in` |  |
| `P2-M221-019` | Edge: TRAINED_ON (Model ← Dataset) | L2 + L3 | `/p2/knowledge-graph/edges/trained-on` |  |
| `P2-M221-020` | Edge: PREDICTS_TO (Model → Column) | L5 | `/p2/knowledge-graph/edges/predicts-to` |  |
| `P2-M221-021` | Edge: CITES (Insight → Document / Data row) | L3 | `/p2/knowledge-graph/edges/cites` |  |
| `P2-M221-022` | Edge: OWNED_BY (Dataset/Report → User/Team) | L2 | `/p2/knowledge-graph/edges/owned-by` |  |
| `P2-M221-023` | Edge: CONSUMED_BY (Dashboard → User) | L5 | `/p2/knowledge-graph/edges/consumed-by` |  |
| `P2-M221-024` | Interactive graph canvas (zoom/pan/drag) | L3 | `/p2/knowledge-graph/visualize/canvas` |  |
| `P2-M221-025` | Toggle visibility theo node type | L5 | `/p2/knowledge-graph/visualize/filters` |  |
| `P2-M221-026` | Filter nodes theo owner/tag/layer | L5 | `/p2/knowledge-graph/visualize/filters` |  |
| `P2-M221-027` | Click node → expand surrounding ecosystem | L5 | `/p2/knowledge-graph/visualize/node/:id/expand` |  |
| `P2-M221-028` | Inspect node properties + metadata | L5 | `/p2/knowledge-graph/visualize/node/:id/inspect` |  |
| `P2-M221-029` | Highlight path giữa 2 nodes | L5 | `/p2/knowledge-graph/visualize/path` |  |
| `P2-M221-030` | Mini-map navigation | L5 | `/p2/knowledge-graph/visualize/minimap` |  |
| `P2-M221-031` | Export graph PNG / SVG / JSON | L5 | `/p2/knowledge-graph/visualize/export` |  |
| `P2-M221-032` | Trace ngược (upstream lineage): Metric → Column → Dataset → file upload gốc | L1 + L2 | `/p2/knowledge-graph/lineage/upstream` |  |
| `P2-M221-033` | Trace xuôi (downstream lineage): Column → Metric → Widget → Dashboard → Report | L5 + Cross | `/p2/knowledge-graph/lineage/downstream` |  |
| `P2-M221-034` | Trace toàn tuyến (end-to-end): file upload → Bronze → Silver → Gold → KPI | L1 + L2 | `/p2/knowledge-graph/lineage/end-to-end` |  |
| `P2-M221-035` | Visualize lineage như Sankey/Flow chart | L5 | `/p2/knowledge-graph/lineage/visualize` |  |
| `P2-M221-036` | Lineage snapshot theo thời điểm (time-travel) | L5 | `/p2/knowledge-graph/lineage/snapshot` |  |
| `P2-M221-037` | Export lineage report PDF (compliance/audit) | Cross | `/p2/knowledge-graph/lineage/export` |  |
| `P2-M221-038` | Vector embedding mỗi node (dùng SH-F05 Internal LLM) | L3 | `/p2/knowledge-graph/search/embeddings` |  |
| `P2-M221-039` | Natural language query ("tìm cột liên quan đến doanh thu") | L5 | `/p2/knowledge-graph/search/nl` |  |
| `P2-M221-040` | GraphRAG — kết hợp graph traversal + vector similarity | L3 | `/p2/knowledge-graph/search/graph-rag` |  |
| `P2-M221-041` | Suggested similar datasets/metrics | L2 | `/p2/knowledge-graph/search/similar` |  |
| `P2-M221-042` | Auto-tag node với concept (sales, customer, inventory...) | L5 | `/p2/knowledge-graph/search/auto-tag` |  |
| `P2-M221-043` | Auto-build graph khi ingest data (từ Bronze) | L1 + L5 | `/p2/knowledge-graph/maintenance/autobuild` |  |
| `P2-M221-044` | Auto-update edges khi pipeline chạy | L5 | `/p2/knowledge-graph/maintenance/autoupdate` |  |
| `P2-M221-045` | Manual annotation (user add custom edge/tag) | L5 | `/p2/knowledge-graph/maintenance/annotate` |  |
| `P2-M221-046` | Detect orphan nodes (dataset không ai dùng) | L2 + L3 | `/p2/knowledge-graph/maintenance/orphans` |  |
| `P2-M221-047` | Detect cycle / redundant path | L5 | `/p2/knowledge-graph/maintenance/cycles` |  |
| `P2-M221-048` | Graph version history (snapshot hàng ngày) | L3 | `/p2/knowledge-graph/maintenance/versions` |  |
| `P2-M221-049` | REST API: list nodes/edges, get node detail | L3 | `/api/v1/knowledge-graph` |  |
| `P2-M221-050` | GraphQL API: flexible query | L5 | `/api/v1/knowledge-graph/graphql` |  |
| `P2-M221-051` | Cypher-like query language cho power user | L5 | `/api/v1/knowledge-graph/cypher` |  |
| `P2-M221-052` | Export subgraph as JSON / GraphML | L5 | `/api/v1/knowledge-graph/export` |  |
| `P2-M221-053` | Webhook: notify khi graph structure thay đổi | L1 + L5 | `/api/v1/knowledge-graph/webhooks` |  |
| `P2-M222-001` | Trigger khi user mở edit form (cột/metric/pipeline/dataset) | L2 + L3 | `/p2/blast-radius/pre-change/trigger` |  |
| `P2-M222-002` | Dry-run simulate change | L3 | `/p2/blast-radius/pre-change/dry-run` |  |
| `P2-M222-003` | List downstream affected: metrics, widgets, dashboards, reports, models | L3 + L5 | `/p2/blast-radius/pre-change/downstream` |  |
| `P2-M222-004` | Phân loại impact severity (CRITICAL / HIGH / MEDIUM / LOW) | L3 | `/p2/blast-radius/pre-change/severity` |  |
| `P2-M222-005` | Count affected users / teams | L3 | `/p2/blast-radius/pre-change/user-count` |  |
| `P2-M222-006` | Hiển thị dạng tree hoặc Sankey | L3 + L5 | `/p2/blast-radius/pre-change/visualize` |  |
| `P2-M222-007` | Require approval từ data owner nếu severity CRITICAL | L3 + L5 | `/p2/blast-radius/pre-change/approval` |  |
| `P2-M222-008` | Đổi tên / xóa cột (Silver/Gold layer) | L2 + L3 | `/p2/blast-radius/change-types/rename-drop-column` |  |
| `P2-M222-009` | Đổi data type cột | L3 | `/p2/blast-radius/change-types/change-type` |  |
| `P2-M222-010` | Sửa công thức metric | L3 | `/p2/blast-radius/change-types/edit-metric` |  |
| `P2-M222-011` | Xóa dataset | L2 + L3 | `/p2/blast-radius/change-types/delete-dataset` |  |
| `P2-M222-012` | Deactivate pipeline | L3 | `/p2/blast-radius/change-types/deactivate-pipeline` |  |
| `P2-M222-013` | Thay đổi business rule (Gold) | L2 + L3 | `/p2/blast-radius/change-types/change-business-rule` |  |
| `P2-M222-014` | Archive ML model version | L3 | `/p2/blast-radius/change-types/archive-model` |  |
| `P2-M222-015` | Xóa / đổi schema source file | L3 | `/p2/blast-radius/change-types/source-schema` |  |
| `P2-M222-016` | Radar chart mức độ ảnh hưởng theo category | L3 | `/p2/blast-radius/visualization/radar` |  |
| `P2-M222-017` | Tree view downstream artifact | L3 | `/p2/blast-radius/visualization/tree` |  |
| `P2-M222-018` | Heat map severity | L3 | `/p2/blast-radius/visualization/heatmap` |  |
| `P2-M222-019` | Diff view before/after (khi đổi công thức) | L3 | `/p2/blast-radius/visualization/diff` |  |
| `P2-M222-020` | Inline comment trên graph node bị impact | L3 | `/p2/blast-radius/visualization/comment` |  |
| `P2-M222-021` | Log mọi change đề xuất + approved/rejected (audit trail) | L3 + Cross | `/p2/blast-radius/governance/log` |  |
| `P2-M222-022` | Auto-notify downstream owners qua email / Slack | L3 | `/p2/blast-radius/governance/notify` |  |
| `P2-M222-023` | Pending approval queue cho Data Steward role | L3 | `/p2/blast-radius/governance/approvals` |  |
| `P2-M222-024` | Rollback change trong 30 ngày | L3 | `/p2/blast-radius/governance/rollback` |  |
| `P2-M222-025` | Export change report (cho compliance) | L3 | `/p2/blast-radius/governance/export` |  |
| `P2-M222-026` | AI đề xuất cách refactor (VD: deprecate cột cũ + thêm cột mới song song 60 ngày) | L3 | `/p2/blast-radius/assistant/refactor` |  |
| `P2-M222-027` | Auto-generate migration script | L3 | `/p2/blast-radius/assistant/migration-script` |  |
| `P2-M222-028` | Test impact với historical data trước khi apply | L3 | `/p2/blast-radius/assistant/test-history` |  |
| `P2-M222-029` | Notify user đang mở dashboard bị ảnh hưởng (real-time banner) | L3 + L5 | `/p2/blast-radius/assistant/live-banner` |  |

**Studio (11)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P3-M37-001` | Tạo prompt template cho ngành/tác vụ | L3 | `/p3/prompts/new` |  |
| `P3-M37-002` | Test prompt với sample data | L3 | `/p3/prompts/:id/test` |  |
| `P3-M37-003` | Version prompt | L3 | `/p3/prompts/:id/versions` |  |
| `P3-M37-004` | Share prompt với enterprise | L3 | `/p3/prompts/:id/share` |  |
| `P3-M37-005` | A/B test 2 prompt versions | L3 | `/p3/prompts/:id/ab` |  |
| `P3-M38-001` | List all members | L5 | `/p3/settings/members` |  |
| `P3-M38-002` | Invite new member | L3 | `/p3/settings/members/invite` |  |
| `P3-M38-003` | Change type KAORI_STAFF / ENTERPRISE_ANALYST | L5 | `/p3/settings/members/:id/type` |  |
| `P3-M38-004` | Scope enterprise_id cho Analyst | L5 | `/p3/settings/members/:id/scope` |  |
| `P3-M38-005` | Deactivate member | L5 | `/p3/settings/members/:id/deactivate` |  |
| `P3-M38-006` | Enforce ≥1 KAORI_STAFF admin active | L5 | `/p3/settings/members/:id/deactivate` |  |

**Cross-cutting (102)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| ~~`SH-M56a-001`~~ | ~~DetectPII~~ ✅ 2026-05-18 (PIIDetectRule wraps `pii.py`) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-002`~~ | ~~PromptInjectionDetector~~ ✅ 2026-05-18 (PromptInjectionRule — 7 jailbreak regex patterns) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-003`~~ | ~~TopicRestriction~~ ✅ 2026-05-18 (TopicRestrictionRule, tenant_config['business_topics']) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-004`~~ | ~~ToxicLanguage threshold 0.7~~ ✅ 2026-05-18 (ToxicLanguageInputRule + `score_toxic`) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-005`~~ | ~~Rate limit per-user per-enterprise~~ ✅ 2026-05-18 (RateLimitRule, in-mem token bucket; Redis Phase 2.5) | L0 + L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-006`~~ | ~~Input length check~~ ✅ 2026-05-18 (InputLengthRule, default 32K chars) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-007`~~ | ~~ValidJson schema enforcement~~ ✅ 2026-05-18 (ValidJsonRule, JSON-Schema Draft 2020-12) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-008`~~ | ~~ValidLength min/max chars~~ ✅ 2026-05-18 (OutputLengthRule) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-009`~~ | ~~ToxicLanguage threshold 0.5~~ ✅ 2026-05-18 (ToxicLanguageOutputRule) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-010`~~ | ~~ProfanityFree~~ ✅ 2026-05-18 (ProfanityFreeRule) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-011`~~ | ~~CompetitorCheck~~ ✅ 2026-05-18 (CompetitorCheckRule with FIX → `[competitor]`) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-012`~~ | ~~Kaori: TopFactorsMinLength~~ ✅ 2026-05-18 (TopFactorsMinLengthRule) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-013`~~ | ~~Kaori: CitationRequired~~ ✅ 2026-05-18 (CitationRequiredRule) | L3 + L5 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-014`~~ | ~~Kaori: BusinessLanguage~~ ✅ 2026-05-18 (BusinessLanguageRule with FIX) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-015`~~ | ~~Kaori: NumericPrecisionCheck~~ ✅ 2026-05-18 (NumericPrecisionCheckRule, JSON tree walk) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-016`~~ | ~~Kaori: HallucinationDetector~~ ✅ 2026-05-18 (HallucinationDetectorRule, entity+number cross-check) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-017`~~ | ~~EXCEPTION~~ ✅ 2026-05-18 (OnFailAction.EXCEPTION → GuardrailBlockedError) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-018`~~ | ~~REASK~~ ✅ 2026-05-18 (OnFailAction.REASK → feedback list propagated) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-019`~~ | ~~FIX~~ ✅ 2026-05-18 (OnFailAction.FIX → rule.fixed_text swap) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-020`~~ | ~~NOOP~~ ✅ 2026-05-18 (OnFailAction.NOOP → log + persist + continue) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-021`~~ | ~~guardrail_violations PARTITIONED monthly~~ ✅ 2026-05-18 (mig 082, monthly RANGE partitions) | L3 | `(llm-gateway guardrails)` |  |
| ~~`SH-M56a-022`~~ | ~~Dashboard top violations~~ ✅ 2026-05-18 (`GET /guardrails/violations[/top]`) | L3 + L5 | `/guardrails/violations` |  |
| `SH-M56a-023` | Alert ops khi CRITICAL violation — defer (Prometheus alert rule, Phase 2.5 ops) | L3 | `(future)` |  |
| ~~`SH-M56a-024`~~ | ~~Retention 180 ngày~~ ✅ 2026-05-18 (`run_retention` DROP PARTITION, `POST /guardrails/retention/run`) | L3 | `/guardrails/retention/run` |  |
| ~~`SH-M56a-025`~~ | ~~Implement in app/llm_gateway/guardrails/~~ ✅ 2026-05-18 (`services/llm-gateway/guardrails/`) | L3 | (internal) |  |
| `SH-M56a-026` | Contribute lên Guardrails Hub — defer Phase 3 per BACKLOG | L3 | `(future)` |  |
| `SH-M56b-001` | Planner Agent (phân tách task phức tạp) | L5 | `/shared/agents/configs/planner` |  |
| `SH-M56b-002` | Retriever Agent (RAG + graph query) | L3 | `/shared/agents/configs/retriever` |  |
| `SH-M56b-003` | Analyzer Agent (run Basic/Intermediate/Advanced analysis) | L3 | `/shared/agents/configs/analyzer` |  |
| `SH-M56b-004` | Critic Agent (validate output schema + citations) | L5 | `/shared/agents/configs/critic` |  |
| `SH-M56b-005` | Explainer Agent (translate en → tiếng Việt business) | L3 | `/shared/agents/configs/explainer` |  |
| `SH-M56b-006` | Strategy Agent (generate action plan) | L4 | `/shared/agents/configs/strategy` |  |
| `SH-M56b-007` | BA Agent (ideas → requirement specs) | L5 | `/shared/agents/configs/ba` |  |
| `SH-M56b-008` | Insight Generation (Planner→Retriever→Analyzer→Explainer→Critic) | L3 | `/shared/agents/workflows/insight-gen` |  |
| `SH-M56b-009` | Auto DB Design (SchemaAnalyzer→Normalization→Validator→MigrationGen) | L3 | `/shared/agents/workflows/auto-db` |  |
| `SH-M56b-010` | Framework Fill (SWOT/6W/2H/Fishbone — multi-step fill each cell) | L5 | `/shared/agents/workflows/framework-fill` |  |
| `SH-M56b-011` | Report Composition (Draft → Review → Polish agents) | L5 | `/shared/agents/workflows/report-compose` |  |
| `SH-M56b-012` | MCP Tool Call (AuthCheck → Retrieve → Mask → Return) | L3 + L5 | `/shared/agents/workflows/mcp-tool-call` |  |
| `SH-M56b-013` | agent_sessions tracking (RUNNING/SUCCESS/FAILED/CANCELED) | L3 + L5 | `/shared/agents/sessions/tracking` |  |
| `SH-M56b-014` | agent_session_messages append-only (compound PK AP-1) | L5 | `/shared/agents/sessions/messages` |  |
| `SH-M56b-015` | Max iterations limit per agent (default 10) | L5 | `/shared/agents/sessions/max-iterations` |  |
| `SH-M56b-016` | Memory optional per agent | L5 | `/shared/agents/sessions/memory` |  |
| `SH-M56b-017` | Cancel running session qua API | L5 | `/shared/agents/sessions/:id/cancel` |  |
| `SH-M56b-018` | Total cost tracking per session | L3 + L5 | `/shared/agents/sessions/:id/cost` |  |
| `SH-M56b-019` | fetch_gold_data (query Gold layer views) | L2 | `/shared/agents/tools/fetch-gold-data` |  |
| `SH-M56b-020` | rag_query (semantic search knowledge_base_chunks) | L3 | `/shared/agents/tools/rag-query` |  |
| `SH-M56b-021` | run_analysis (trigger analysis_runs) | L3 | `/shared/agents/tools/run-analysis` |  |
| `SH-M56b-022` | blast_radius (check impact before change) | L5 | `/shared/agents/tools/blast-radius` |  |
| `SH-M56b-023` | generate_chart (từ Chart Library 2.14) | L5 | `/shared/agents/tools/generate-chart` |  |
| `SH-M56b-024` | graph_traverse (Knowledge Graph lineage) | L5 | `/shared/agents/tools/graph-traverse` |  |
| `SH-M56b-025` | mcp_proxy (relay to external MCP servers) | L5 | `/shared/agents/tools/mcp-proxy` |  |
| `SH-M56b-027` | Test agent responses | L5 | `/shared/agents/studio/test` |  |
| `SH-M56b-028` | Deploy custom agents | L5 | `/shared/agents/studio/deploy` |  |
| ~~`SH-M59-001`~~ | ~~Cron monthly aggregate~~ ✅ 2026-05-18 (mig 081 + `org_intel/economics/roi_billing.py` + `POST /economics/roi/cron/compute`) | L4.5 | `/economics/roi/cron/compute` |  |
| ~~`SH-M59-002`~~ | ~~0.015 × SUM(revenue_at_risk WHERE is_actioned=true)~~ ✅ 2026-05-18 (`compute_roi_addon` pure compute) | L4 + L4.5 | `/economics/roi/cron/compute` |  |
| ~~`SH-M59-003`~~ | ~~Cap 20M/tháng~~ ✅ 2026-05-18 (`chk_roi_cap_consistency` + `apply_cap` logic) | L4.5 | `/economics/roi/cron/compute` |  |
| ~~`SH-M59-004`~~ | ~~Chỉ áp dụng ENT MAX opt-in~~ ✅ 2026-05-18 (`enterprise_roi_subscriptions` + `POST /economics/roi/opt-in[out]`) | L4.5 | `/economics/roi/{opt-in,opt-out,subscription}` |  |
| ~~`SH-M59-005`~~ | ~~Yêu cầu ≥3 tháng data~~ ✅ 2026-05-18 (`MIN_MONTHS_OF_DATA=3` + `fetch_months_of_data` gate) | L4.5 | `(internal compute)` |  |
| `SH-M510-001` | Implement MCP spec (JSON-RPC 2.0 over stdio/HTTP/SSE) | L5 | `/mcp/core/transport` |  |
| `SH-M510-002` | Auth bằng API key per enterprise/user | L5 | `/mcp/core/auth` |  |
| `SH-M510-003` | Rate limit theo gói subscription | Cross | `/mcp/core/rate-limit` |  |
| `SH-M510-004` | Enforce row-level isolation (tenant_id) | Cross | `/mcp/core/isolation` |  |
| `SH-M510-005` | Audit log mọi MCP call | Cross | `/mcp/core/audit` |  |
| `SH-M510-006` | Health check + metrics endpoint | L5 | `/mcp/core/health` |  |
| `SH-M510-007` | Tool: `query_dataset` — truy vấn Bronze/Silver/Gold | L1 + L2 | `/mcp/tools/query-dataset` |  |
| `SH-M510-008` | Tool: `get_metric` — lấy giá trị metric theo period | L5 | `/mcp/tools/get-metric` |  |
| `SH-M510-009` | Tool: `trace_lineage` — upstream/downstream cho 1 node | Cross | `/mcp/tools/trace-lineage` |  |
| `SH-M510-010` | Tool: `semantic_search` — tìm dataset/column bằng ngôn ngữ tự nhiên | L2 | `/mcp/tools/semantic-search` |  |
| `SH-M510-011` | Tool: `run_analysis` — chạy Basic/Intermediate analysis | L3 | `/mcp/tools/run-analysis` |  |
| `SH-M510-012` | Tool: `get_insight` — gọi Insights Engine (What/Why/What-to-do) | L3 | `/mcp/tools/get-insight` |  |
| `SH-M510-013` | Tool: `list_reports` — list reports user có quyền xem | L5 | `/mcp/tools/list-reports` |  |
| `SH-M510-014` | Tool: `get_report` — fetch report content + charts | L5 | `/mcp/tools/get-report` |  |
| `SH-M510-015` | Tool: `blast_radius` — impact analysis cho 1 node (từ 2.22) | L3 | `/mcp/tools/blast-radius` |  |
| `SH-M510-016` | Tool: `list_risks` — lấy risk register | L5 | `/mcp/tools/list-risks` |  |
| `SH-M510-017` | Tool: `generate_chart` — sinh chart từ Chart Library 2.14 | L5 | `/mcp/tools/generate-chart` |  |
| `SH-M510-018` | Resource: Data Knowledge Graph subset (filter by role) | L5 | `/mcp/resources/graph` |  |
| `SH-M510-019` | Resource: Report library (markdown + metadata) | L5 | `/mcp/resources/reports` |  |
| `SH-M510-020` | Resource: Metric catalog (definitions + formula) | L5 | `/mcp/resources/metrics` |  |
| `SH-M510-021` | Resource: Document knowledge base (RAG corpus) | L3 | `/mcp/resources/documents` |  |
| `SH-M510-022` | Resource: Organization branding (logo/color cho auto-style chart) | L5 | `/mcp/resources/branding` |  |
| `SH-M510-023` | Prompt: `monthly_review` — sinh báo cáo tháng từ data mới nhất | L3 | `/mcp/prompts/monthly-review` |  |
| `SH-M510-024` | Prompt: `risk_briefing` — summary rủi ro tuần này | L3 | `/mcp/prompts/risk-briefing` |  |
| `SH-M510-025` | Prompt: `data_health_check` — quality score Bronze/Silver/Gold | L1 + L2 | `/mcp/prompts/data-health-check` |  |
| `SH-M510-026` | Prompt: `onboard_new_dataset` — guide user import + clean dataset mới | L2 + L3 | `/mcp/prompts/onboard-new-dataset` |  |
| `SH-M510-027` | Prompt: `explain_metric` — giải thích metric X là gì, tính từ đâu | L3 + L5 | `/mcp/prompts/explain-metric` |  |
| `SH-M510-028` | OAuth 2.1 flow cho browser-based MCP clients | L5 | `/mcp/security/oauth` |  |
| `SH-M510-029` | Scoped API keys (read-only / read-write / admin) | L5 | `/mcp/security/scoped-keys` |  |
| `SH-M510-030` | PII masking trước khi trả về (tùy enterprise config) | L5 | `/mcp/security/pii-masking` |  |
| `SH-M510-031` | Whitelist/blacklist tool per user role | L5 | `/mcp/security/tool-acl` |  |
| `SH-M510-032` | Request signing + replay protection | L5 | `/mcp/security/signing` |  |
| `SH-M510-033` | Rotation API key | L5 | `/mcp/security/rotation` |  |
| `SH-M510-034` | Official support: Claude Desktop | L5 | `/mcp/clients/claude-desktop` |  |
| `SH-M510-035` | Official support: Cursor IDE | L5 | `/mcp/clients/cursor` |  |
| `SH-M510-036` | Official support: Windsurf / Antigravity | L5 | `/mcp/clients/windsurf` |  |
| `SH-M510-037` | Official support: VSCode + Copilot MCP | L5 | `/mcp/clients/vscode` |  |
| `SH-M510-038` | Web-based MCP client (built-in Kaori portal) | L5 | `/mcp/clients/web` |  |
| `SH-M510-039` | Install wizard + config generator | L5 | `/mcp/clients/wizard` |  |
| `SH-M510-040` | Troubleshooting dashboard (connection/tool errors) | L5 | `/mcp/clients/troubleshoot` |  |
| `SH-M510-041` | Dashboard: top tool calls per enterprise | L5 | `/mcp/analytics/top-tools` |  |
| `SH-M510-042` | Dashboard: token usage qua MCP (cross với SH-F05/SH-F06) | L5 | `/mcp/analytics/tokens` |  |
| `SH-M510-043` | Alert: unusual pattern (possible abuse) | L5 | `/mcp/analytics/alerts` |  |
| `SH-M510-044` | Latency tracking per tool | L5 | `/mcp/analytics/latency` |  |

### ~~P2-S24~~ ✅ DONE — Phase 2 retro doc shipped (Features:0 = milestone only)  
*Batch:* `B2.6 — Internationalization + Phase 2 Wrap`  ·  *Window:* Week 47-48  ·  *Features:* 0

> **Sprint status (2026-05-17 shipped `68233e0`):** retro doc landed at `docs/sprint/P2_RETRO_PHASE2_CLOSEOUT.md`. The 100-customer milestone is a business KPI tracked separately, not a code deliverable — sprint slot is closed.

### ~~P2-S25~~ ⭐ ✅ DONE — SSO Google + MFA + field-encryption (Microsoft defer until Entra tenant provisioned)  
*Batch:* `B2.6 — Internationalization + Phase 2 Wrap`  ·  *Window:* Week 47-48 (parallel to S24)  ·  *Features:* 3

> **Added 2026-05-17.** Carved out from P2-S18 — the original title there ("SSO + MFA + field-level encryption") didn't match its OBS-* feature list. Em consolidate the security work into this new row so the title-vs-features mismatch is resolved.

> **Sprint status (2026-05-18 final):** ✅ shipped end-to-end. **P2-AUTH-001 SSO Google** live (mig 083 + `shared/sso_providers/` + `routers/sso.py` + `auth-service/SsoController` + `auth-service/SsoExchangeService` + gateway sso-public route + JwtAuthFilter pre-auth whitelist + FE `/sso-callback` page + Google login button on `/login` + `.env` Google credentials provisioned by anh + docker-compose env forwarding + 33 Python + 6 Java tests). Browser-tested 2026-05-18 with `nguyentruongan25051997@gmail.com` — full chain works (FE → ai-orchestrator OAuth → Google → callback → exchange_code → auth-service mints RS256 JWT → FE dashboard). **P2-AUTH-002 MFA TOTP** + **P2-ENC-001 field encryption** shipped 2026-05-17 (mig 074 + `shared/totp.py` + `shared/crypto.py` + `/p2/auth/{mfa,field-key}` 7 endpoints + 43 tests). **Microsoft provider** code-complete but inactive — activates when anh provisions M365 Dev Program tenant + sets `MICROSOFT_CLIENT_ID/SECRET` env.
>
> **Follow-up 2026-05-18 (F-NEW11):** P2 retro defer item 6 — **field-key rotation history + re-encrypt worker**. Mig 080 `tenant_field_key_versions` history table (+4 status cols on `tenant_field_keys`) + `shared/field_key_rotation.py` worker (column registry + decrypt-with-history fallback) + 2 endpoints `POST /p2/auth/field-key/reencrypt` + `GET /p2/auth/field-key/reencrypt/status` + 41 tests. **Closes latent bug** where rotation overwrote `key_ref` in-place leaving prior ciphertext permanently undecryptable; the new lifecycle is `rotate → pending → trigger worker → completed`, with full key history retained for audit.

**Cross-cutting (3 — proposed codes; rename when sprint plan lands)**

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| ~~`P2-AUTH-001`~~ | ~~SSO via OAuth (Google + Microsoft)~~ ✅ 2026-05-18 — Google live end-to-end; Microsoft inactive pending tenant | L3 + L5 | `/p2/auth/sso/{provider}/{start,callback}` + `/auth/sso/exchange` | ⭐ |
| ~~`P2-AUTH-002`~~ | ~~MFA enforce: TOTP + email backup code~~ ✅ 2026-05-17 | L5 | `/p2/auth/mfa/{enroll,verify}` | ⭐ |
| ~~`P2-ENC-001`~~ | ~~Field-level encryption~~ ✅ 2026-05-17 (mig 074 + 2026-05-18 mig 080 history) | Cross | `(internal via shared/crypto.py)` | ⭐ |

> **Anh chốt khi nào ship.** Đề xuất Week 47-48 song song với P2-S24 retro (security là blocking cho SOC 2 Type 1 Phase 2 acceptance criteria — ≥10 KH có thể yêu cầu SSO/MFA).

---

## Phase 3 (Year 2)

### P3-S25 — All layers as microservices  
*Batch:* `B3.1 — Full Microservices + Multi-Region`  ·  *Window:* Month 13  ·  *Features:* 266

**Enterprise (214)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `P2-M28-001` | Descriptive statistics (mean, median, mode, std, range) | L3 | `/p2/analysis/basic/descriptive` |  |
| `P2-M28-002` | Data distribution (histogram, box plot) | L3 | `/p2/analysis/basic/distribution` |  |
| `P2-M28-003` | Frequency count / proportion | L3 | `/p2/analysis/basic/frequency` |  |
| `P2-M28-004` | Top N / Bottom N | L3 | `/p2/analysis/basic/top-bottom` |  |
| `P2-M28-005` | Missing data analysis | L3 | `/p2/analysis/basic/missing` |  |
| `P2-M28-006` | Correlation matrix đơn giản | L3 | `/p2/analysis/basic/correlation` |  |
| `P2-M28-007` | Time-series trend (line chart) | L3 | `/p2/analysis/basic/time-series` |  |
| `P2-M28-008` | Category breakdown (pie/bar) | L3 | `/p2/analysis/basic/category-breakdown` |  |
| `P2-M28-009` | Segmentation (K-means, hierarchical clustering) | L3 | `/p2/analysis/intermediate/segmentation` |  |
| `P2-M28-010` | Cohort analysis | L3 | `/p2/analysis/intermediate/cohort` |  |
| `P2-M28-011` | Funnel analysis | L3 | `/p2/analysis/intermediate/funnel` |  |
| `P2-M28-012` | RFM analysis (Recency/Frequency/Monetary) | L3 | `/p2/analysis/intermediate/rfm` |  |
| `P2-M28-013` | A/B test statistics | L3 | `/p2/analysis/intermediate/ab-test` |  |
| `P2-M28-014` | Hypothesis testing (t-test, chi-square) | L3 | `/p2/analysis/intermediate/hypothesis` |  |
| `P2-M28-015` | Regression đơn giản (linear/logistic) | L3 | `/p2/analysis/intermediate/regression` |  |
| `P2-M28-016` | Forecasting (ARIMA, Prophet) | L3 | `/p2/analysis/intermediate/forecasting` |  |
| `P2-M28-017` | MoM / YoY comparison | L3 | `/p2/analysis/intermediate/mom-yoy` |  |
| `P2-M28-018` | Machine Learning models (XGBoost, Random Forest, NN) | L3 | `/p2/analysis/advanced/ml` |  |
| `P2-M28-019` | Deep Learning (CNN/RNN — Phase 2) | L3 | `/p2/analysis/advanced/dl` |  |
| `P2-M28-020` | NLP text analytics (sentiment, topic modeling) | L3 | `/p2/analysis/advanced/nlp` |  |
| `P2-M28-021` | Anomaly detection | L3 | `/p2/analysis/advanced/anomaly` |  |
| `P2-M28-022` | Causal inference | L3 | `/p2/analysis/advanced/causal` |  |
| `P2-M28-023` | Recommendation systems | L3 | `/p2/analysis/advanced/recommendation` |  |
| `P2-M28-024` | Multi-variate analysis | L3 | `/p2/analysis/advanced/multivariate` |  |
| `P2-M28-025` | Survival analysis (churn, lifetime) | L3 | `/p2/analysis/advanced/survival` |  |
| `P2-M28-026` | Network / graph analysis — Phase 2 | L3 | `/p2/analysis/advanced/graph` |  |
| `P2-M28-027` | Call external AI API (OpenAI/Claude/Gemini) nếu user opt-in | L3 | `/p2/analysis/advanced/external-ai` |  |
| `P2-M28-028` | Privacy toggle: internal LLM vs external AI | L3 | `/p2/analysis/advanced/privacy-toggle` |  |
| `P2-M28-029` | Phân tích 1 loại dữ liệu (single dataset) | L2 + L3 | `/p2/analysis/scope/single` |  |
| `P2-M28-030` | Phân tích nhiều loại dữ liệu (multi-dataset join) | L2 + L3 | `/p2/analysis/scope/multi` |  |
| `P2-M28-031` | Phân tích theo workflow (cross-pipeline) | L3 + L4 | `/p2/analysis/scope/cross-pipeline` |  |
| `P2-M28-032` | Phân tích theo thời gian (time-window) | L3 | `/p2/analysis/scope/time-window` |  |
| `P2-M28-033` | Phân tích so sánh (A vs B) | L3 | `/p2/analysis/scope/compare` |  |
| `P2-M29-001` | Strengths (điểm mạnh) — AI fill từ data | L3 | `/p2/frameworks/swot/strengths` |  |
| `P2-M29-002` | Weaknesses (điểm yếu) | L3 | `/p2/frameworks/swot/weaknesses` |  |
| `P2-M29-003` | Opportunities (cơ hội) | L3 | `/p2/frameworks/swot/opportunities` |  |
| `P2-M29-004` | Threats (thách thức) | L3 | `/p2/frameworks/swot/threats` |  |
| `P2-M29-005` | User có thể edit/add từng ô | L3 | `/p2/frameworks/swot/edit` |  |
| `P2-M29-006` | Export SWOT template PDF/PPT | L3 | `/p2/frameworks/swot/export` |  |
| `P2-M29-007` | What — Điều gì đang diễn ra? | L3 | `/p2/frameworks/6w/what` |  |
| `P2-M29-008` | Where — Ở đâu? | L3 | `/p2/frameworks/6w/where` |  |
| `P2-M29-009` | Why — Tại sao xảy ra? | L3 | `/p2/frameworks/6w/why` |  |
| `P2-M29-010` | Who — Ai liên quan? | L3 | `/p2/frameworks/6w/who` |  |
| `P2-M29-011` | When — Khi nào? | L3 | `/p2/frameworks/6w/when` |  |
| `P2-M29-012` | Whom — Với ai/cho ai? | L3 | `/p2/frameworks/6w/whom` |  |
| `P2-M29-013` | Auto-fill từ data + LLM | L3 | `/p2/frameworks/6w/auto-fill` |  |
| `P2-M29-014` | How — Làm thế nào? | L3 | `/p2/frameworks/2h/how` |  |
| `P2-M29-015` | How much — Bao nhiêu (cost/impact/effort)? | L3 | `/p2/frameworks/2h/how-much` |  |
| `P2-M29-016` | Auto-fill từ data + LLM | L3 | `/p2/frameworks/2h/auto-fill` |  |
| `P2-M29-017` | Root cause analysis canvas | L3 | `/p2/frameworks/fishbone/canvas` |  |
| `P2-M29-018` | 6M branches: Man / Machine / Method / Material / Measurement / Environment | L3 | `/p2/frameworks/fishbone/branches` |  |
| `P2-M29-019` | AI đề xuất sub-causes từ data | L3 | `/p2/frameworks/fishbone/auto-suggest` |  |
| `P2-M29-020` | Drag-drop chỉnh sửa | L3 | `/p2/frameworks/fishbone/edit` |  |
| `P2-M29-021` | Export PDF/PNG | L3 | `/p2/frameworks/fishbone/export` |  |
| `P2-M29-022` | Month-over-Month % change | L3 | `/p2/frameworks/mom-yoy/mom` |  |
| `P2-M29-023` | Year-over-Year % change | L3 | `/p2/frameworks/mom-yoy/yoy` |  |
| `P2-M29-024` | Quarter-over-Quarter | L3 | `/p2/frameworks/mom-yoy/qoq` |  |
| `P2-M29-025` | Week-over-Week | L3 | `/p2/frameworks/mom-yoy/wow` |  |
| `P2-M29-026` | Drill-down theo metric bất kỳ | L3 | `/p2/frameworks/mom-yoy/drill-down` |  |
| `P2-M29-027` | Highlight bất thường (red/green arrow) | L3 | `/p2/frameworks/mom-yoy/highlights` |  |
| `P2-M29-028` | Chart trend line + % change | L3 | `/p2/frameworks/mom-yoy/chart` |  |
| `P2-M29-029` | Tạo framework custom (N ô bất kỳ) | L3 + L5 | `/p2/frameworks/custom/new` |  |
| `P2-M29-030` | Save framework template | L3 | `/p2/frameworks/custom/templates` |  |
| `P2-M29-031` | Share framework trong tổ chức | L3 | `/p2/frameworks/custom/templates/:id/share` |  |
| `P2-M213-001` | Báo cáo tự động từ file upload (LLM nội bộ) | L1 + L3 | `/p2/reports/auto/internal` |  |
| `P2-M213-002` | Báo cáo tự động qua External AI (ChatGPT/Claude/Gemini) | L3 | `/p2/reports/auto/external` |  |
| `P2-M213-003` | Toggle privacy mode (internal-only / allow external) | L5 | `/p2/reports/auto/privacy` |  |
| `P2-M213-004` | Toggle privacy mode (internal-only / allow external) | L3 | `/p2/reports/auto/privacy/confirm` |  |
| `P2-M213-005` | Chọn tone báo cáo (professional / casual / executive summary) | L5 | `/p2/reports/auto/tone` |  |
| `P2-M213-006` | Chọn ngôn ngữ output (VN / EN) | L5 | `/p2/reports/auto/language` |  |
| `P2-M213-007` | Báo cáo hàng tuần / tháng / quý tự động | L5 | `/p2/reports/auto/schedule` |  |
| `P2-M213-008` | Auto-send email báo cáo scheduled | L3 | `/p2/reports/auto/email` |  |
| `P2-M213-009` | Báo cáo so sánh (period comparison) | L5 | `/p2/reports/auto/compare` |  |
| `P2-M213-010` | Report Builder (drag-drop chart, text, table, image) | L3 + L5 | `/p2/reports/builder/new` |  |
| `P2-M213-011` | Rich text editor có công thức LaTeX | L5 | `/p2/reports/builder/editor` |  |
| `P2-M213-012` | Insert chart từ Chart Library (Section 2.14) | L5 | `/p2/reports/builder/insert/chart` |  |
| `P2-M213-013` | Insert KPI card | L5 | `/p2/reports/builder/insert/kpi` |  |
| `P2-M213-014` | Chèn insight từ Insights Engine | L3 | `/p2/reports/builder/insert/insight` |  |
| `P2-M213-015` | Branding auto (logo, màu tổ chức) | L5 | `/p2/reports/builder/branding` |  |
| `P2-M213-016` | Draft autosave mỗi 30s | L5 | `/p2/reports/builder/autosave` |  |
| `P2-M213-017` | Version history | L5 | `/p2/reports/builder/:id/versions` |  |
| `P2-M213-018` | Collaborate (multi-user editing) — Phase 2 | L5 | `/p2/reports/builder/collab` |  |
| `P2-M213-019` | Comment / review / approve workflow | L4 | `/p2/reports/builder/:id/review` |  |
| `P2-M213-020` | Executive Summary template | L5 | `/p2/reports/templates/executive-summary` |  |
| `P2-M213-021` | Monthly Business Review template | L5 | `/p2/reports/templates/mbr` |  |
| `P2-M213-022` | Sales Report template | L5 | `/p2/reports/templates/sales` |  |
| `P2-M213-023` | Marketing Performance template | L5 | `/p2/reports/templates/marketing` |  |
| `P2-M213-024` | Financial Summary template | L5 | `/p2/reports/templates/financial` |  |
| `P2-M213-025` | Customer Health template | L5 | `/p2/reports/templates/customer-health` |  |
| `P2-M213-026` | Operational KPI template | L5 | `/p2/reports/templates/operational` |  |
| `P2-M213-027` | Custom template (save own) | L5 | `/p2/reports/templates/custom` |  |
| `P2-M213-028` | Export PDF | L5 | `/p2/reports/:id/export/pdf` |  |
| `P2-M213-029` | Export PPT (slide deck) | L5 | `/p2/reports/:id/export/pptx` |  |
| `P2-M213-030` | Export Word (DOCX) | L5 | `/p2/reports/:id/export/docx` |  |
| `P2-M213-031` | Export Excel (data tables) | L5 | `/p2/reports/:id/export/xlsx` |  |
| `P2-M213-032` | Share link (read-only hoặc edit) | L5 | `/p2/reports/:id/share` |  |
| `P2-M213-033` | Send via email | L3 | `/p2/reports/:id/send-email` |  |
| `P2-M213-034` | Schedule auto-send | L5 | `/p2/reports/:id/schedule` |  |
| `P2-M213-035` | Password-protect PDF | L5 | `/p2/reports/:id/password` |  |
| `P2-M213-036` | Watermark | L5 | `/p2/reports/:id/watermark` |  |
| `P2-M214-001` | Auto-recommend chart type theo dạng data (category × value, time-series, distribution...) | L3 | `/p2/charts/picker/recommend` |  |
| `P2-M214-002` | Chart picker modal (gallery preview) | L5 | `/p2/charts/picker/modal` |  |
| `P2-M214-003` | Filter chart theo use case (so sánh / xu hướng / phân phối / quan hệ / KPI...) | L5 | `/p2/charts/picker` |  |
| `P2-M214-004` | Đổi loại chart on-the-fly (giữ nguyên data binding) | L5 | `/p2/charts/picker/swap` |  |
| `P2-M214-005` | Chart preview với data mẫu | L2 | `/p2/charts/picker/preview` |  |
| `P2-M214-006` | Pin chart yêu thích | L5 | `/p2/charts/picker/favorites` |  |
| `P2-M214-007` | Bar chart (cột ngang) | L5 | `/p2/charts/comparison/bar` |  |
| `P2-M214-008` | Column chart (cột dọc) | L5 | `/p2/charts/comparison/column` |  |
| `P2-M214-009` | Stacked bar / column | L5 | `/p2/charts/comparison/stacked` |  |
| `P2-M214-010` | Grouped (clustered) bar / column | L5 | `/p2/charts/comparison/grouped` |  |
| `P2-M214-011` | 100% stacked bar / column | L5 | `/p2/charts/comparison/100-stacked` |  |
| `P2-M214-012` | Bullet chart (actual vs target) | L5 | `/p2/charts/comparison/bullet` |  |
| `P2-M214-013` | Lollipop chart | L5 | `/p2/charts/comparison/lollipop` |  |
| `P2-M214-014` | Diverging bar (positive/negative) | L5 | `/p2/charts/comparison/diverging` |  |
| `P2-M214-015` | Line chart (đường đơn) | L5 | `/p2/charts/trend/line` |  |
| `P2-M214-016` | Multi-line chart (nhiều series) | L5 | `/p2/charts/trend/multi-line` |  |
| `P2-M214-017` | Area chart | L5 | `/p2/charts/trend/area` |  |
| `P2-M214-018` | Stacked area chart | L5 | `/p2/charts/trend/stacked-area` |  |
| `P2-M214-019` | Step chart | L5 | `/p2/charts/trend/step` |  |
| `P2-M214-020` | Spline chart (đường cong) | L5 | `/p2/charts/trend/spline` |  |
| `P2-M214-021` | Candlestick (nến tài chính) | L5 | `/p2/charts/trend/candlestick` |  |
| `P2-M214-022` | OHLC chart | L5 | `/p2/charts/trend/ohlc` |  |
| `P2-M214-023` | Waterfall chart (thác nước) | L5 | `/p2/charts/trend/waterfall` |  |
| `P2-M214-024` | Sparkline (mini trend) | L5 | `/p2/charts/trend/sparkline` |  |
| `P2-M214-025` | Pie chart (tròn) | L5 | `/p2/charts/proportion/pie` |  |
| `P2-M214-026` | Donut chart (bánh rán) | L5 | `/p2/charts/proportion/donut` |  |
| `P2-M214-027` | Semi-donut / Gauge donut | L5 | `/p2/charts/proportion/semi-donut` |  |
| `P2-M214-028` | Treemap | L5 | `/p2/charts/proportion/treemap` |  |
| `P2-M214-029` | Sunburst chart | L5 | `/p2/charts/proportion/sunburst` |  |
| `P2-M214-030` | Nested pie | L5 | `/p2/charts/proportion/nested-pie` |  |
| `P2-M214-031` | Histogram | L5 | `/p2/charts/distribution/histogram` |  |
| `P2-M214-032` | Box plot (hộp râu) | L5 | `/p2/charts/distribution/box` |  |
| `P2-M214-033` | Violin plot | L5 | `/p2/charts/distribution/violin` |  |
| `P2-M214-034` | Density plot (KDE) | L5 | `/p2/charts/distribution/density` |  |
| `P2-M214-035` | Ridgeline plot | L5 | `/p2/charts/distribution/ridgeline` |  |
| `P2-M214-036` | Q-Q plot | L5 | `/p2/charts/distribution/qq` |  |
| `P2-M214-037` | Swarm plot | L5 | `/p2/charts/distribution/swarm` |  |
| `P2-M214-038` | Scatter plot | L5 | `/p2/charts/relationship/scatter` |  |
| `P2-M214-039` | Bubble chart (3 chiều) | L5 | `/p2/charts/relationship/bubble` |  |
| `P2-M214-040` | Heatmap (ma trận nhiệt) | L5 | `/p2/charts/relationship/heatmap` |  |
| `P2-M214-041` | Correlation matrix | L5 | `/p2/charts/relationship/correlation-matrix` |  |
| `P2-M214-042` | Radar / Spider chart | L5 | `/p2/charts/relationship/radar` |  |
| `P2-M214-043` | Parallel coordinates | L5 | `/p2/charts/relationship/parallel-coordinates` |  |
| `P2-M214-044` | Polar chart | L5 | `/p2/charts/relationship/polar` |  |
| `P2-M214-045` | Chord diagram | L5 | `/p2/charts/relationship/chord` |  |
| `P2-M214-046` | KPI card (số + label + delta) | L5 | `/p2/charts/kpi/basic` |  |
| `P2-M214-047` | KPI card với mini trend (sparkline) | L5 | `/p2/charts/kpi/with-spark` |  |
| `P2-M214-048` | Gauge chart (đồng hồ đo) | L5 | `/p2/charts/kpi/gauge` |  |
| `P2-M214-049` | Speedometer | L5 | `/p2/charts/kpi/speedometer` |  |
| `P2-M214-050` | Progress bar | L5 | `/p2/charts/kpi/progress-bar` |  |
| `P2-M214-051` | Progress circle / ring | L5 | `/p2/charts/kpi/progress-ring` |  |
| `P2-M214-052` | Target vs Actual card | L5 | `/p2/charts/kpi/target-vs-actual` |  |
| `P2-M214-053` | Comparison card (vs previous period) | L5 | `/p2/charts/kpi/comparison` |  |
| `P2-M214-054` | Sankey diagram (luồng) | L5 | `/p2/charts/hierarchy/sankey` |  |
| `P2-M214-055` | Funnel chart (phễu) | L5 | `/p2/charts/hierarchy/funnel` |  |
| `P2-M214-056` | Pyramid chart | L5 | `/p2/charts/hierarchy/pyramid` |  |
| `P2-M214-057` | Dendrogram | L5 | `/p2/charts/hierarchy/dendrogram` |  |
| `P2-M214-058` | Tree chart (sơ đồ cây) | L5 | `/p2/charts/hierarchy/tree` |  |
| `P2-M214-059` | Organization chart | L5 | `/p2/charts/hierarchy/org` |  |
| `P2-M214-060` | Network graph | L5 | `/p2/charts/hierarchy/network` |  |
| `P2-M214-061` | Flow chart / Process diagram | L5 | `/p2/charts/hierarchy/flowchart` |  |
| `P2-M214-062` | Vietnam choropleth (bản đồ 63 tỉnh/thành) | L5 | `/p2/charts/geo/vn-provinces` |  |
| `P2-M214-063` | Quận/huyện level drill-down | L5 | `/p2/charts/geo/vn-districts` |  |
| `P2-M214-064` | World choropleth | L5 | `/p2/charts/geo/world` |  |
| `P2-M214-065` | Bubble map (điểm trên bản đồ) | L5 | `/p2/charts/geo/bubble` |  |
| `P2-M214-066` | Heatmap geo | L5 | `/p2/charts/geo/heatmap` |  |
| `P2-M214-067` | Flow map (điểm A → điểm B) | L5 | `/p2/charts/geo/flow` |  |
| `P2-M214-068` | Cluster map (marker grouping) | L5 | `/p2/charts/geo/cluster` |  |
| `P2-M214-069` | Data table (sortable, filterable) | L5 | `/p2/charts/table/data` |  |
| `P2-M214-070` | Pivot table | L3 | `/p2/charts/table/pivot` |  |
| `P2-M214-071` | Crosstab (bảng chéo) | L5 | `/p2/charts/table/crosstab` |  |
| `P2-M214-072` | Conditional formatting (heatmap cells) | L5 | `/p2/charts/table/conditional-format` |  |
| `P2-M214-073` | Data bar trong cell (mini bar) | L5 | `/p2/charts/table/data-bar` |  |
| `P2-M214-074` | Cohort retention heatmap | L5 | `/p2/charts/time-cohort/cohort-retention` |  |
| `P2-M214-075` | Calendar heatmap (GitHub-style) | L5 | `/p2/charts/time-cohort/calendar-heatmap` |  |
| `P2-M214-076` | Gantt chart (timeline) | L5 | `/p2/charts/time-cohort/gantt` |  |
| `P2-M214-077` | Timeline chart (sự kiện) | L5 | `/p2/charts/time-cohort/timeline` |  |
| `P2-M214-078` | Swimlane chart | L5 | `/p2/charts/time-cohort/swimlane` |  |
| `P2-M214-079` | Word cloud / Tag cloud | L5 | `/p2/charts/text-specialty/wordcloud` |  |
| `P2-M214-080` | Sentiment bar (positive/neutral/negative) | L5 | `/p2/charts/text-specialty/sentiment` |  |
| `P2-M214-081` | Icon array (pictograph) | L5 | `/p2/charts/text-specialty/pictograph` |  |
| `P2-M214-082` | Nightingale rose (polar bar) | L5 | `/p2/charts/text-specialty/rose` |  |
| `P2-M214-083` | Fishbone/Ishikawa (liên kết Section 2.9.4) | L5 | `/p2/charts/text-specialty/fishbone` |  |
| `P2-M214-084` | Color palette picker (preset + custom) | L5 | `/p2/charts/customization/palette` |  |
| `P2-M214-085` | Theme theo brand tổ chức (auto-apply từ 2.1) | L5 | `/p2/charts/customization/brand-theme` |  |
| `P2-M214-086` | Data label on/off, format (%, số, currency) | L5 | `/p2/charts/customization/data-label` |  |
| `P2-M214-087` | Axis customization (min/max/tick/log scale) | L5 | `/p2/charts/customization/axis` |  |
| `P2-M214-088` | Legend position (top/right/bottom/hidden) | L5 | `/p2/charts/customization/legend` |  |
| `P2-M214-089` | Grid line on/off | L5 | `/p2/charts/customization/grid` |  |
| `P2-M214-090` | Annotation (text, line, area marker) | L5 | `/p2/charts/customization/annotation` |  |
| `P2-M214-091` | Title, subtitle, caption | L5 | `/p2/charts/customization/title` |  |
| `P2-M214-092` | Reference line (trung bình / mục tiêu) | L5 | `/p2/charts/customization/reference-line` |  |
| `P2-M214-093` | Trend line (linear/polynomial/exponential) | L5 | `/p2/charts/customization/trend-line` |  |
| `P2-M214-094` | Error bar | L5 | `/p2/charts/customization/error-bar` |  |
| `P2-M214-095` | Dual Y-axis | L5 | `/p2/charts/customization/dual-axis` |  |
| `P2-M214-096` | Tooltip khi hover | L5 | `/p2/charts/interactivity/tooltip` |  |
| `P2-M214-097` | Click to drill-down | L3 | `/p2/charts/interactivity/drilldown` |  |
| `P2-M214-098` | Zoom (wheel / pinch) | L5 | `/p2/charts/interactivity/zoom` |  |
| `P2-M214-099` | Pan / scroll | L5 | `/p2/charts/interactivity/pan` |  |
| `P2-M214-100` | Brush select range (chart linking) | L5 | `/p2/charts/interactivity/brush` |  |
| `P2-M214-101` | Cross-filter (chọn 1 → filter các chart khác) | L5 | `/p2/charts/interactivity/cross-filter` |  |
| `P2-M214-102` | Toggle series qua legend | L5 | `/p2/charts/interactivity/toggle-series` |  |
| `P2-M214-103` | Animation on load / update | L5 | `/p2/charts/interactivity/animation` |  |
| `P2-M214-104` | Export PNG | L5 | `/p2/charts/export/png` |  |
| `P2-M214-105` | Export SVG (vector) | L5 | `/p2/charts/export/svg` |  |
| `P2-M214-106` | Export PDF | L5 | `/p2/charts/export/pdf` |  |
| `P2-M214-107` | Copy image to clipboard | L5 | `/p2/charts/export/clipboard` |  |
| `P2-M214-108` | Embed link (iframe) — Phase 2 | L5 | `/p2/charts/export/embed` |  |
| `P2-M214-109` | Export data underlying chart (CSV) | L5 | `/p2/charts/export/data-csv` |  |
| `P2-M214-110` | Lưu chart thành template cá nhân | L5 | `/p2/charts/templates/personal` |  |
| `P2-M214-111` | Share template trong tổ chức | L5 | `/p2/charts/templates/:id/share` |  |
| `P2-M214-112` | Chart gallery của tổ chức | L5 | `/p2/charts/templates/gallery` |  |
| `P2-M214-113` | Duplicate chart | L5 | `/p2/charts/templates/:id/duplicate` |  |
| `P2-M214-114` | Version chart (khi edit) | L5 | `/p2/charts/templates/:id/versions` |  |

**Cross-cutting (52)**  

| Code | Feature | Layer | API | NEW |
|---|---|---|---|---|
| `SH-M55-001` | Docker container vllm/vllm-openai:latest | L0 + L3 | `/shared/llm/internal/vllm/docker` |  |
| `SH-M55-002` | GPU provisioning (L40S 48GB cho Qwen 14B AWQ) | L0 + L3 | `/shared/llm/internal/vllm/gpu` |  |
| `SH-M55-003` | OpenAI-compatible API endpoint | L0 + L3 | `/shared/llm/internal/vllm/api` |  |
| `SH-M55-004` | Health check + readiness probes | L0 + L3 | `/shared/llm/internal/vllm/probes` |  |
| `SH-M55-005` | Prometheus /metrics scrape | L0 + L3 | `/shared/llm/internal/vllm/metrics` |  |
| `SH-M55-006` | Tensor parallelism (Phase 2: Qwen 32B multi-GPU) | L0 + L3 | `/shared/llm/internal/vllm/tensor-parallel` |  |
| `SH-M55-007` | Continuous batching config (--max-num-seqs) | L0 + L3 | `/shared/llm/internal/vllm/batching` |  |
| `SH-M55-008` | Prefix caching enabled (--enable-prefix-caching) | L0 + L3 | `/shared/llm/internal/vllm/prefix-cache` |  |
| `SH-M55-009` | Chunked prefill (--enable-chunked-prefill) | L0 + L3 | `/shared/llm/internal/vllm/chunked-prefill` |  |
| `SH-M55-010` | Qwen 2.5-3B-Instruct-AWQ (dev) | L0 + L3 | `/shared/llm/internal/qwen/3b-awq` |  |
| `SH-M55-011` | Qwen 2.5-7B-Instruct-AWQ (staging) | L0 + L3 | `/shared/llm/internal/qwen/7b-awq` |  |
| `SH-M55-012` | Qwen 2.5-14B-Instruct-AWQ (prod Phase 1) | L0 + L3 | `/shared/llm/internal/qwen/14b-awq` |  |
| `SH-M55-013` | Qwen 2.5-32B-Instruct-AWQ (prod Phase 2) | L0 + L3 | `/shared/llm/internal/qwen/32b-awq` |  |
| `SH-M55-014` | Qwen 2.5-72B-Instruct-FP8 (prod Phase 3) | L0 + L3 | `/shared/llm/internal/qwen/72b-fp8` |  |
| `SH-M55-015` | Model weights integrity check (checksum AP-6) | L0 + L3 | `/shared/llm/internal/qwen/checksum` |  |
| `SH-M55-016` | HuggingFace Hub download + cache volume | L0 + L3 | `/shared/llm/internal/qwen/download` |  |
| `SH-M55-017` | Quantization AWQ/GPTQ (60-80% cost reduction) | L0 + L3 | `/shared/llm/internal/optimize/quantization` |  |
| `SH-M55-018` | Prefix cache cho system prompts chung | L0 + L3 | `/shared/llm/internal/optimize/prefix-cache` |  |
| `SH-M55-019` | Response cache Redis TTL 1h (identical prompts) | L0 + L3 | `/shared/llm/internal/optimize/response-cache` |  |
| `SH-M55-020` | Structured output (xgrammar/guidance) cho JSON schema | L0 + L3 | `/shared/llm/internal/optimize/structured-output` |  |
| `SH-M55-021` | Streaming output (Server-Sent Events) | L0 + L3 | `/shared/llm/internal/optimize/streaming` |  |
| `SH-M55-022` | LoRA multi-adapter (Phase 3: per-industry fine-tune) | L0 + L3 | `/shared/llm/internal/optimize/lora` |  |
| `SH-M55-023` | inference_logs PARTITIONED monthly | L0 + L3 | `/shared/llm/internal/logs/partitioning` |  |
| `SH-M55-024` | Token counting + cost computation | L0 + L3 | `/shared/llm/internal/logs/tokens` |  |
| `SH-M55-025` | Trace ID propagation (W3C) | L0 + L3 | `/shared/llm/internal/logs/tracing` |  |
| `SH-M55-026` | Latency tracking (p50/p95/p99, TTFT) | L0 + L3 | `/shared/llm/internal/logs/latency` |  |
| `SH-M55-027` | Cache hit rate analytics | L0 + L3 | `/shared/llm/internal/logs/cache-hit` |  |
| `SH-M55-028` | Retention 90 ngày → archive S3 | L0 + L3 | `/shared/llm/internal/logs/retention` |  |
| `SH-M55-029` | Collect training data từ inference_logs (opt-in) | L0 + L3 | `/shared/llm/internal/fine-tune/collect` |  |
| `SH-M55-030` | LoRA fine-tune pipeline | L0 + L3 | `/shared/llm/internal/fine-tune/lora-pipeline` |  |
| `SH-M55-031` | Evaluation vs baseline (MMLU-vi, business QA) | L0 + L3 | `/shared/llm/internal/fine-tune/eval` |  |
| `SH-M55-032` | Staged rollout (5% traffic test) | L0 + L3 | `/shared/llm/internal/fine-tune/rollout` |  |
| `SH-M56-001` | OpenAI API (GPT-4o, GPT-4o-mini) | L3 | `/shared/llm/external/providers/openai` |  |
| `SH-M56-002` | Anthropic Claude API (Haiku, Sonnet, Opus) | L3 | `/shared/llm/external/providers/anthropic` |  |
| `SH-M56-003` | Google Gemini API (2-Flash, 2-Pro) | L3 | `/shared/llm/external/providers/gemini` |  |
| `SH-M56-004` | Azure OpenAI Service | L3 | `/shared/llm/external/providers/azure` |  |
| `SH-M56-005` | Unified OpenAI-compatible interface (qua LiteLLM proxy optional) | L3 | `/shared/llm/external/providers/unified` |  |
| `SH-M56-006` | Fallback chain khi primary timeout (OpenAI → Claude → Gemini) | L3 | `/shared/llm/external/reliability/fallback` |  |
| `SH-M56-007` | Circuit breaker (stop calling bad provider 5 phút) | L3 + L5 | `/shared/llm/external/reliability/circuit-breaker` |  |
| `SH-M56-008` | Retry với exponential backoff (5 lần, 1-30s) | L3 | `/shared/llm/external/reliability/retry` |  |
| `SH-M56-009` | Rate limit handling (respect provider quota) | L3 + Cross | `/shared/llm/external/reliability/rate-limit` |  |
| `SH-M56-010` | PII detection (Guardrails DetectPII) trước khi gọi external | L3 | `/shared/llm/external/privacy/detect` |  |
| `SH-M56-011` | Mask PII (name, email, phone, CCCD VN) in situ | L3 | `/shared/llm/external/privacy/mask` |  |
| `SH-M56-012` | Un-masking response khi trả user (nếu user là owner) | L3 | `/shared/llm/external/privacy/unmask` |  |
| `SH-M56-013` | Enterprise privacy toggle (INTERNAL/HYBRID/EXTERNAL) | L3 | `/shared/llm/external/privacy/toggle` |  |
| `SH-M56-014` | Per-analysis override (user chọn provider) | L3 | `/shared/llm/external/privacy/override` |  |
| `SH-M56-015` | Per-user force INTERNAL (trump enterprise default) | L3 | `/shared/llm/external/privacy/user-force` |  |
| `SH-M56-016` | Data Processing Agreement (DPA) tracking per provider | L3 | `/shared/llm/external/privacy/dpa` |  |
| `SH-M56-017` | Real-time cost per call (USD + VND) | L3 | `/shared/llm/external/cost/realtime` |  |
| `SH-M56-018` | Per-enterprise budget limit | L3 | `/shared/llm/external/cost/budget` |  |
| `SH-M56-019` | Cost allocation report monthly | L3 | `/shared/llm/external/cost/report` |  |
| `SH-M56-020` | Compare cost internal vs external (ROI analysis) | L3 + L4.5 | `/shared/llm/external/cost/compare` |  |

### P3-S26 — Multi-region active-active  
*Batch:* `B3.1 — Full Microservices + Multi-Region`  ·  *Window:* Month 14  ·  *Features:* 0

### P3-S27 — Singapore region  
*Batch:* `B3.1 — Full Microservices + Multi-Region`  ·  *Window:* Month 15  ·  *Features:* 0

### P3-S28 — Multi-agent orchestration framework  
*Batch:* `B3.2 — Multi-Agent + Marketplace`  ·  *Window:* Month 16  ·  *Features:* 0

### P3-S29 — Public marketplace launch  
*Batch:* `B3.2 — Multi-Agent + Marketplace`  ·  *Window:* Month 17  ·  *Features:* 0

### P3-S30 — Federated workflows  
*Batch:* `B3.2 — Multi-Agent + Marketplace`  ·  *Window:* Month 18  ·  *Features:* 0

### P3-S31 — Vietnamese fine-tuned model  
*Batch:* `B3.3 — Self-Hosted LLM + Hybrid`  ·  *Window:* Month 19  ·  *Features:* 0

### P3-S32 — Hybrid LLM routing  
*Batch:* `B3.3 — Self-Hosted LLM + Hybrid`  ·  *Window:* Month 20  ·  *Features:* 0

### P3-S33 — On-premises deployment option  
*Batch:* `B3.3 — Self-Hosted LLM + Hybrid`  ·  *Window:* Month 21  ·  *Features:* 0

### P3-S34 — Developer platform  
*Batch:* `B3.4 — Ecosystem + Scale + Cert`  ·  *Window:* Month 22  ·  *Features:* 0

### P3-S35 — Indonesia + Thailand expansion  
*Batch:* `B3.4 — Ecosystem + Scale + Cert`  ·  *Window:* Month 23  ·  *Features:* 0

### P3-S36 — 1000 customer + SOC 2 Type 2 + Year 2 wrap  
*Batch:* `B3.4 — Ecosystem + Scale + Cert`  ·  *Window:* Month 24  ·  *Features:* 0
