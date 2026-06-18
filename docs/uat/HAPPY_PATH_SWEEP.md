# UAT — Happy Path Sweep (toàn bộ surface đã ship)

> **Created:** 2026-05-04 · **Last updated:** 2026-05-04 (F-033 PR A+B+C+D — all 3 tiers + approval workflow live)
> **Goal:** Bao quát mọi màn hình + endpoint hiện đã ship để (a) anh tự smoke-test cuối phiên, (b) feed cho claude edge audit edge cases.
> **Scope:** Phase 1 (32 functions ✅) + Phase 2 Sprint 2.1+2.2 đã ship (F-033 ✅, F-034, F-035, F-036, F-037, F-038, F-039, F-040, F-041 ✅ this PR, F-060, F-NEW3) + Sprint 8 ChatPanel + Đường A pipeline routes (PR #161).
> **Out of scope:** Phase 2 chưa ship (F-033, F-035, F-041, F-042..F-068) · Phase 3 (F-069..F-092).
>
> **Per-feature deep-dive UAT files** (chi tiết hơn, có pre-flight DB queries + Kafka inspect):
> `F-008-workspace.md` · `F-034-frameworks.md` · `F-036-decision-override.md` · `F-037-alerts.md` · `F-038-reports.md` · `F-039-risks.md` · `F-060-north-star.md` · `CHAT_PANEL.md` · `PILOT_ROUND_2.md`.
> File này là sweep ngắn — không thay thế chúng.

---

## 0. Pre-flight

### Mode A — Dev mode (MSW intercept, không cần BE)

```bash
cd "D:\Kaori System\frontend"
npm run dev          # Next on :3000, MSW intercepts /api/v1/*
```

Dev login (mock):

| Email | Role | Use |
|---|---|---|
| `test@demo.com` | MANAGER (P2) | Default account — pass mọi happy path |
| `locked@test.com` | — | 423 lockout (edge — không trong sweep này) |
| `error@test.com` | — | 401 (edge — không trong sweep này) |

Password mọi tài khoản: `password123`.

### Mode B — Full stack (real BE)

```bash
docker compose up postgres redis kafka zookeeper ollama -d
docker exec kaori-ollama-1 ollama pull qwen2.5:14b   # hoặc 7b cho laptop 16GB
docker compose up -d
cd frontend && npm run dev
```

Service URLs: `:3000` FE · `:8080` Gateway · `:8082` Swagger · `:8085` Kafka UI · `:11434` Ollama.

---

## 1. P1 Platform Manager Portal

> Truy cập qua `/platform/login` (token_kind=platform). MFA TOTP yêu cầu cho SUPER_ADMIN sau khi enable.

### 1.1 Auth + MFA + Sessions (F-007, deepened Batch 2)

| # | Surface | Action | Expected |
|---|---|---|---|
| 1.1.a | `POST /api/v1/auth/platform/login` | Body `{email, password}` của platform admin | 200 + JWT (`token_kind=platform`, `session_id`); `admin_sessions` row mới |
| 1.1.b | `/platform/security/mfa` | Bấm "Bật MFA" → quét QR Google Authenticator → nhập 6 số | `mfa_enabled=true`; toàn bộ session phải verify code lần kế |
| 1.1.c | `/platform/security/sessions` | Xem danh sách session | Hiện ít nhất 1 row (session hiện tại); `last_active_at` cập nhật mỗi 60s |
| 1.1.d | `/platform/security/sessions` | Bấm "Revoke all other sessions" → confirm | Chỉ còn 1 row (current); audit log `admin.session.revoked` reason=manual_bulk |
| 1.1.e | `POST /api/v1/auth/platform/refresh` | Trước absolute timeout (24h) | 200 + new access token; cùng `session_id` |
| 1.1.f | Idle 30+ min không request | Gửi request bất kỳ | 401 `application/problem+json` reason=idle_timeout; `revoke_reason='idle_timeout'` |

### 1.2 Workspace Management (F-008)

| # | Surface | Action | Expected |
|---|---|---|---|
| 1.2.a | `/platform/workspaces` | Mở page | Bảng list workspaces; "+ Tạo workspace" button |
| 1.2.b | `/platform/workspaces/new` | Form tạo + submit | 201 + redirect `/platform/workspaces/{id}` |
| 1.2.c | `/platform/workspaces/{id}` | Mở detail | 4 tabs: Members, Billing, Audit, Keys |
| 1.2.d | `.../members` | "+ Thêm thành viên" → chọn role | 201 + member row; `workspace_audit_log` entry |
| 1.2.e | `.../billing` | Xem | KPI tiles + 30d chart; `BillingMath` đúng |
| 1.2.f | `.../audit` | Xem | Cursor pagination; mọi action vừa làm hiện ở top |
| 1.2.g | `PATCH /api/v1/platform/workspaces/{id}` | Đổi name | 200 + audit row |
| 1.2.h | `DELETE /api/v1/platform/workspaces/{id}` | Soft-delete | 204; row có `deleted_at` |

### 1.3 Private Key Management (F-009)

| # | Surface | Action | Expected |
|---|---|---|---|
| 1.3.a | `/platform/workspaces/{id}/keys` | "+ Cấp khoá" | 201 + key (chỉ hiện 1 lần plaintext); `workspace_keys` row với SHA-256 |
| 1.3.b | Cùng page | Bấm "Thu hồi" trên 1 key | 204; key marked revoked, không xài được nữa |
| 1.3.c | `POST /auth/workspace/activate` (legacy flat) | Body `{workspace_key}` | 200 nếu key valid; rate-limit 5/min/IP |

### 1.4 Platform Admin Management (F-010)

| # | Surface | Action | Expected |
|---|---|---|---|
| 1.4.a | `/platform/admins` | List | Bảng admin + role + last_login |
| 1.4.b | `/platform/admins/invite` | Form mời | 201 + email gửi qua notification-service; `platform_admin_password_resets` row |
| 1.4.c | `/platform/admins/{id}` | Mở detail | Tabs: profile, sessions, audit |
| 1.4.d | `.../reset-password` | Bấm reset | Token mới gửi email; old sessions không revoke (để admin tự logout) |

### 1.5 Billing Monitor (F-011)

| # | Surface | Action | Expected |
|---|---|---|---|
| 1.5.a | `/platform/billing/overview` | Mở | KPI tổng MRR + quota cảnh báo + cron health card (3-tier OK/warn/critical) |
| 1.5.b | `/platform/billing/quota` | Mở | Bảng % quota từng enterprise; ≥80% highlight |
| 1.5.c | `/platform/billing/enterprises/{id}` | Mở detail | Trend tháng + list distinct customers |
| 1.5.d | `/platform/billing/export` | "Tải CSV" | File `billing-YYYY-MM-DD.csv` UTF-8 BOM (Excel-VN OK) |
| 1.5.e | `POST /api/v1/platform/billing/aggregate-now` | Manual trigger | 202 + cron rerun ngay |

### 1.6 Platform Health (F-012)

| # | Surface | Action | Expected |
|---|---|---|---|
| 1.6.a | `/platform` | Mở | KPI cards (workspaces, admins, MRR, ingest 24h); 30d chart |
| 1.6.b | `GET /api/v1/platform/stats` | Hit trực tiếp | 200 với schema match dashboard |

---

## 2. P2 Enterprise — Phase 1 (F-013..F-032)

> Login qua `/login` (P2 enterprise users). Default test account: `test@demo.com / password123`.

### 2.1 Auth + Onboarding (F-002, F-003, F-013)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.1.a | `/login` | Email + password | 200 + JWT (`role=MANAGER\|OPERATOR\|ANALYST\|VIEWER`); redirect `/dashboard` |
| 2.1.b | `/forgot-password` | Email | 202 (luôn, anti-enum); email gửi qua notification-service |
| 2.1.c | `/reset-password?token=<token>` | New password 2 lần | 200 + tự login |
| 2.1.d | `/register` | Step 1 paste workspace key → Step 2 admin credentials | 201 + redirect `/dashboard` |
| 2.1.e | `POST /auth/logout` | Bất kỳ | 204; refresh token blacklisted |

### 2.2 User & Role Management (F-015)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.2.a | `/p2/users/manager` | List | Bảng members + role filter |
| 2.2.b | `/p2/users/invite` | Email + role + submit | 201; user nhận invite email |
| 2.2.c | `/p2/users/id-detail` | Mở detail member | Tabs: profile, role, deactivate |
| 2.2.d | `PATCH /api/v1/enterprises/users/{id}` body `{role: 'MANAGER'}` | Đổi role | 200 nếu giữ ≥ 1 MANAGER; 422 nếu cố demote MANAGER cuối |
| 2.2.e | `DELETE /api/v1/enterprises/users/{id}` | Xoá member | 204 (phải còn ≥ 1 MANAGER) |

### 2.3 Enterprise Settings (F-016)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.3.a | `/p2/settings` (assume mounted) | Mở | Tabs: Branding, Language, AI Consent, Notifications |
| 2.3.b | AI Consent toggle | Bật `consent_external` | 200; cache cập nhật ngay; Step 4 wizard sẽ enable Claude/GPT-4o option |
| 2.3.c | Notifications | Toggle `notification_email` | 200; alert + report-ready emails sẽ gửi |

### 2.4 Pipeline Wizard 5-step (F-017..F-021) — **PR #161 vừa merge**

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.4.a | `/p2/pipelines` | List | Bảng runs + filter status; SSE indicator |
| 2.4.b | `/p2/pipelines/new` | Splash + source picker → "Bắt đầu" | Redirect `/p2/pipelines/new/upload?source=upload` (KHÔNG POST gì) |
| 2.4.c | `/p2/pipelines/new/upload` | Drag/drop file CSV/Excel/Parquet/JSON | SHA-256 hash client-side; Idempotency-Key header per file |
| 2.4.d | Click "Tải lên Bronze" | `POST /api/v1/upload` | 200 với `{run_id, status: 'uploading'\|'duplicate', sha256}`; `bronze_files` + `pipeline_runs` row |
| 2.4.e | Sau upload | "Sang Bước 2" | Redirect `/p2/pipelines/{run_id}/step-2-columns` |
| 2.4.f | `/p2/pipelines/{id}/step-2-columns` | Mở | `GET /api/v1/schema/{runId}` trả mapping; confidence badges (exact/fuzzy/llm/manual) |
| 2.4.g | Edit cột rồi "Xác nhận" | `POST /api/v1/schema/{runId}/confirm` | 200; `column_mappings` row + `decision_audit_log` (K-6) |
| 2.4.h | `/p2/pipelines/{id}/step-3-clean` | Mở | `GET /api/v1/clean/suggestions/{runId}` trả 4 group rules |
| 2.4.i | Tick rules → "Áp dụng" | `POST /api/v1/clean/apply` | 200; `silver_rows` + `cleaning_rules_applied` |
| 2.4.j | `/p2/pipelines/{id}/step-4-analyze` | Mở | `GET /analytics/templates`; toggle `consent_external` (K-4 modal nếu bật) |
| 2.4.k | Chọn template + "Bắt đầu" | `POST /api/v1/analytics/runs` | 202 với `run_id`; redirect `/p2/pipelines/{id}/step-5-results?run_id=...` |
| 2.4.l | `/p2/pipelines/{id}/step-5-results?run_id={run_id}` | Mở | `GET /api/v1/analytics/runs/{id}` trả `ChartBlock[]`; render qua chart-registry (F-027) |
| 2.4.m | Click stepper bước trước | Anchor reload page | Wizard back nav OK; current step highlighted gold |
| 2.4.n | `/p2/pipelines/{id}/events` (SSE, F-NEW2) | Subscribe | Event stream: `run.update` event mỗi khi status đổi |

### 2.5 Pipeline Run History (F-022, F-NEW2)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.5.a | `/p2/pipelines` | Lọc status="analyzing" | Bảng shrink theo filter |
| 2.5.b | Search "Q3" | | Rows match name |
| 2.5.c | Click 1 row | Redirect `/p2/pipelines/{id}` (chuyển tới step hiện tại của run) — **TODO: route này chưa tạo, sẽ 404, anh ghi nhận** |
| 2.5.d | SSE indicator | Online | Badge "Đang nhận cập nhật trực tiếp" xanh |

### 2.6 Insights (F-025)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.6.a | `/p2/insights/list` | Mở | Bảng insights; filter category |
| 2.6.b | `/p2/insights/generate` | Form ask question → submit | `POST /api/v1/strategy/ask`; redirect `/p2/insights/{id}` |
| 2.6.c | `/p2/insights/id-detail` | Mở | 3-tuyến (What/Why/What-to-do); narrative; "Tạo Decision" button |
| 2.6.d | Click "Tạo Decision" | `POST /api/v1/decisions` (TBD endpoint) | Redirect `/p2/decisions/{id}` |
| 2.6.e | `/p2/insights/knowledge-base` | Mở | List kb articles |

### 2.7 Charts (F-027)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.7.a | `/p2/charts/picker` | Chọn data source + chart kind | Preview render client-side (chart-registry, không API) |
| 2.7.b | `/p2/charts/categories` | Mở | 15 chart kinds với thumbnail |

### 2.8 Dashboard (F-028)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.8.a | `/p2/dashboard/overview` | Mở | 5-state machine; KPI cards; quota progress |
| 2.8.b | `/p2/dashboard/customize` | Drag-reorder widgets | Layout persist localStorage |
| 2.8.c | `GET /api/v1/dashboard/state` | Hit | 200 với `{state, kpis, quota, recent_runs[]}` |

### 2.9 AI Decision Log (F-029)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.9.a | `/p2/decisions/log` | Mở | Bảng cursor-paginated; filter type |
| 2.9.b | `/p2/decisions/{id}` | Mở 1 decision | Detail page; reasoning + alternatives + audit; `is_actioned` toggle (Sprint 7 PR D) |
| 2.9.c | `GET /api/v1/decisions/export.csv?from=&to=` | Download | UTF-8 BOM CSV; max 10k rows; 422 nếu > 10k |
| 2.9.d | `POST /api/v1/decisions/{id}/action` | Toggle | 200; `decision_actions` UPSERT |

### 2.10 Subscription & Quota (F-030)

| # | Surface | Action | Expected |
|---|---|---|---|
| 2.10.a | `/p2/subscription/quota-screen` | Mở | Tabs: Quota, Plan, Upgrade; forecast; warn banner ≥80% |
| 2.10.b | `/p2/subscription/upgrade` | Chọn plan + submit | `POST /api/v1/enterprises/me/subscription/upgrade` 202; manual workflow Phase 1 |

---

## 3. P2 Enterprise — Phase 2 đã ship

### 3.0 F-033 Multi-tier Analysis (BE PR A + B merged + FE PR C/D — all 3 tiers end-to-end + approval workflow)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.0.a | `/p2/analysis` | Hub | 3 tier cards + scope picker + recent-runs section (≥1 row from MSW seed). All 3 tier buttons ENABLE (Advanced không còn "PR B" badge) |
| 3.0.b | Basic flow | `/p2/analysis/basic` → POST tier=basic | 202; redirect `/p2/analysis/runs/{id}`; status queued → running → done ~3s (MSW); narrative trong detail |
| 3.0.c | Intermediate flow | `/p2/analysis/intermediate` → POST tier=intermediate framework=swot | 202; result page render SWOT 4-quadrant + summary |
| 3.0.d | Validation 1 source only | Click run | FE disable (intermediate yêu cầu ≥2) hoặc BE 400 |
| 3.0.e | Advanced — chưa opt-in tenant | `/p2/analysis/advanced` → pick sources + framework + question → Dispatch | 202 với `status='awaiting_approval'`; redirect detail page; banner vàng "Đang chờ MANAGER duyệt" |
| 3.0.f | Click "Duyệt + dispatch" trong banner | `POST /api/v1/analysis/runs/{id}/approve` | 200; banner biến mất; status pollback queued → running → done; `approved_at` + `approved_by` hiển thị |
| 3.0.g | Advanced — tenant đã opt-in (`UPDATE tenant_settings SET consent_external_ai=true`) | POST advanced run | 202 với `status='queued'` (KHÔNG `awaiting_approval`); auto-dispatch ngay |
| 3.0.h | `GET /api/v1/analysis/quota/external-ai` | Real counter | `external_calls_used` tăng sau mỗi advanced run done (count `decision_audit_log` `llm_provider != 'qwen-internal'`) |
| 3.0.i | `GET /api/v1/analysis/cross-workspaces` với `X-Role: ANALYST` | Real role | 200 + 1 item; `can_include=true`; `member_role='ANALYST'` |
| 3.0.j | Cùng endpoint với `X-Role: VIEWER` | | `can_include=false` — FE block checkbox |
| 3.0.k | `POST /approve` với `X-Role: VIEWER` | 403 | `Only MANAGER can approve advanced runs` |
| 3.0.l | Approve idempotency: gọi /approve 2 lần | Lần 2 | 404 — `Run not found or already actioned` |
| 3.0.m | Result page polling | Mở `runs/[id]` của run mới | Status tự update; đối với advanced pending, polling DỪNG khi awaiting_approval, resume khi approve flip |
| 3.0.n | Cross-tenant `GET /api/v1/analysis/runs/{other tenant id}` | 404 (RLS) | Row invisible |
| 3.0.o | DB CHECK: tier='advanced' + consent_external=false (direct INSERT) | Reject | `analysis_runs_advanced_consent_check` (K-4) |
| 3.0.p | DB CHECK: tier='intermediate' + framework=NULL | Reject | `analysis_runs_intermediate_framework_check` (K-10) |
| 3.0.q | Audit advanced done | K-6 | `decision_audit_log` 2 rows: `analysis.advanced.approved` (manual method) + `analysis.advanced` (llm_provider='external') |
| 3.0.r | Kafka `kaori.analysis.tier.{started,completed}` | Events | started fired on queue + completed on terminal |

### 3.05 F-035 Cohort Retention (Phase 1 engine + Phase 2 surfacing)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.05.a | `/p2/analysis/basic` template list | Open page | "Cohort Retention" hiển thị giữa list 5 templates — không bị disable |
| 3.05.b | Pick pipeline + tick "Cohort Retention" only → submit | POST tier=basic templates=["cohort"] | 202; redirect `/p2/analysis/runs/{id}` |
| 3.05.c | Wait result | Status done | Detail page: 1 heatmap (rows = cohort tháng, cols = M0/M1/M2/M3) + 1 stats card (cohorts_analysed, avg_month1_retention) |
| 3.05.d | Heatmap colors | Inspect | Gradient từ đỏ (low retention) → xanh (high); period 0 luôn = 100% (đỉnh xanh) |
| 3.05.e | Wizard alternative `/p2/pipelines/{id}/step-4-analyze` | Multi-select template | "Cohort Retention" eligible chỉ khi pipeline có cột customer_id + date + ≥100 rows |
| 3.05.f | Engine validation: pipeline thiếu customer column | Submit | Run errors out với "Cần cột customer_id và date cho Cohort." (RFC 7807 surface trên detail page) |

### 3.07 F-041 Explainability (this PR — closes Sprint 2.1)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.07.a | `/p2/decisions/[id]` | Mở 1 decision | Section "Vì sao Kaori quyết định thế?" hiển thị giữa "Lý do AI chọn" và "Lựa chọn thay thế" với button "Tạo giải thích" |
| 3.07.b | Click "Tạo giải thích" | `POST /api/v1/explainability/explain` body `{decision_id, consent_external:false}` | 200 sau ~1-15s; render top-3 yếu tố (direction icon + weight % + evidence) + narrative + confidence_explanation footer |
| 3.07.c | DB audit | `SELECT decision_type, subject FROM decision_audit_log ORDER BY created_at DESC LIMIT 1` | row `decision_type='explainability.explain', subject=<decision_id>` |
| 3.07.d | Click "Tạo lại" | New POST | 200; top_factors có thể khác chút (LLM temperature) — đó là OK, second-opinion feature |
| 3.07.e | Cross-tenant: enterprise B POST với A's decision_id | 404 RFC 7807 — `Decision not found` (RLS prunes; không leak existence) |
| 3.07.f | LLM gateway down hoặc Issue #3 repair fail | 502 RFC 7807 | `LLM gave up explaining this decision: …`; FE hiện ErrorBanner; button stay available cho retry |
| 3.07.g | Validation: POST không có decision_id | 422 | pydantic — `field required` |
| 3.07.h | K-4: POST với `consent_external:true` khi tenant chưa opt-in | 403 từ llm_router | `Tenant has not enabled consent_external_ai (K-4)` |

### 3.1 F-034 Analysis Frameworks (BE PR #119 + FE)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.1.a | `/p2/frameworks` | Hub | Gallery 4 frameworks: SWOT, 6W, 2H, Fishbone-Ishikawa; recent runs |
| 3.1.b | `/p2/frameworks/swot` | Form input → "Tạo SWOT" | `POST /api/v1/frameworks/generate` 202 + poll; sau 10-30s SWOT 4 ô |
| 3.1.c | `/p2/frameworks/6w`, `/2h`, `/fishbone-ishikawa` | Tương tự | Output match `output_schema` (Issue #3); repair once nếu fail |
| 3.1.d | `GET /api/v1/frameworks` | Cursor list | 200 + items (không có `output_value` để giảm payload) |
| 3.1.e | `GET /api/v1/frameworks/{run_id}` | Detail | 200 với full output |
| 3.1.f | K-4 consent | Bật toggle external | LLM call qua Claude/GPT-4o (PII masked); `decision_audit_log` ghi consent flag |

### 3.2 F-036 Decision Override (BE PR #122 + FE)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.2.a | `/p2/decisions/{id}` | Mở 1 decision có "Override" button | Section override visible |
| 3.2.b | Click Override | Modal | Form: new_value + reason → submit |
| 3.2.c | Submit | `POST /api/v1/decisions/{id}/override` | 201 + Kafka emit `kaori.feedback.actions`; `decision_overrides` row |
| 3.2.d | Override row | "Thu hồi" | `POST /api/v1/decisions/{id}/override/{oid}/revoke` 200 |

### 3.3 F-037 Alert Rules (BE PR #116 + FE PR #117)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.3.a | `/p2/alerts` | Tab "Sự kiện" | Bảng `alert_events` cursor; chỉ MANAGER xem được |
| 3.3.b | Tab "Quy tắc" | List rules | CRUD form (MANAGER-only) |
| 3.3.c | `POST /api/v1/enterprises/alerts` | Tạo rule | 201; rule_id returned |
| 3.3.d | Quota crossing 80% / 95% | Cron tự fire | `notification_outbox` row template=quota-alert; cooldown 6h enforced |
| 3.3.e | `/p2/alerts/detail` | Click 1 event | Detail view |

### 3.4 F-038 Reports (BE PR #113 + FE PR #115 + Distribution PR #118)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.4.a | `/p2/reports/hub` | List | Cursor + status badges |
| 3.4.b | `/p2/reports/auto` | Form template + period + submit | `POST /api/v1/reports/generate` 202 + `report_id` |
| 3.4.c | Poll detail | `GET /api/v1/reports/{id}` | `status: queued → running → ready` (10-30s qua Issue #3) |
| 3.4.d | Detail page | Mở | `content_json` schema-validated (kpi_overview, trends, top_risks, recommendations) |
| 3.4.e | Click "Gửi" trên ready report | Deep-link `/p2/reports/distribution?report=<id>` |
| 3.4.f | `/p2/reports/distribution` | Form recipients + send | `POST /api/v1/reports/{id}/distribute` 202; outbox enqueued |
| 3.4.g | `/p2/reports/builder` | (chưa wire — vẫn MSW mock) | Visible nhưng "coming soon" / mock |
| 3.4.h | `/p2/reports/template` | (chưa wire) | Library mock |

### 3.5 F-039 Risk Management (BE + FE)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.5.a | `/p2/risks` | Hub | Bảng risks; KPI tiles; 5×5 heat map |
| 3.5.b | "+ Thêm rủi ro" | Modal submit | `POST /api/v1/enterprises/risks` 201; auto-computed score (likelihood × impact) + severity tier (low/med/high/critical) |
| 3.5.c | `/p2/risks/{riskId}` | Mở detail | All fields; sliders likelihood/impact live update score |
| 3.5.d | Edit category → save | `PATCH /api/v1/enterprises/risks/{id}` | 200 + persisted |
| 3.5.e | `/p2/risks/export` | Filter + "Tải CSV" | `GET /api/v1/enterprises/risks/severity-rollup`; CSV UTF-8 BOM |
| 3.5.f | "Xoá (soft)" | `DELETE /api/v1/enterprises/risks/{id}` | 204; soft-delete (deleted_at set) |

### 3.6 F-040 Strategy Builder OKR (BE + FE)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.6.a | `/p2/strategy` | Hub | List strategy plans + Gantt overview |
| 3.6.b | `/p2/strategy/okr` | OKR editor | Tree drag-drop Objective → Key Results |
| 3.6.c | `POST /api/v2/enterprise/strategy` | Tạo | 201 + plan_id |
| 3.6.d | `PATCH /api/v2/enterprise/strategy/{id}/okr` | Edit OKR node | 200 |
| 3.6.e | `/p2/strategy/timeline` | Mở | Gantt rendered |
| 3.6.f | `/p2/strategy/review-meeting` | Mở | Review form |

### 3.7 F-060 is_actioned Workflow (BE PR #124 + FE)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.7.a | `/p2/customers/at-risk` | Mở | North Star tile (4 KPIs + recent activity) + cursor list |
| 3.7.b | `GET /api/v1/dashboard/north-star` | Hit | 200 với `{revenue_at_risk_total, actioned_count, actioned_revenue, pending_revenue, recent[]}` |
| 3.7.c | Toggle "Đã xử lý" 1 customer | Modal nhập note → confirm | `POST /api/v1/customers/{external_id}/action` 200; Kafka emit `customer.actioned` |
| 3.7.d | Toggle off | Confirm modal | Emit `customer.unactioned`; `is_actioned=false` |
| 3.7.e | `GET /api/v1/customers/at-risk?cursor=&limit=` | Pagination | Cursor-based; 200 |

### 3.8 F-NEW3 Data Explorer (v0 + v1 lineage)

| # | Surface | Action | Expected |
|---|---|---|---|
| 3.8.a | `/p2/data` | Hub | 3 LayerCards (Bronze/Silver/Gold) + recent activity strip + K-rule reminders |
| 3.8.b | `GET /api/v1/data/explorer` | Hit | 200 với snapshot 3 layers |
| 3.8.c | `/p2/data/bronze` | Mở | List files + sample preview modal (v1) |
| 3.8.d | `/p2/data/silver` | Mở | Datasets list + drill-down |
| 3.8.e | `/p2/data/gold` | Mở | Customers gold features list |
| 3.8.f | Click "Xem lineage" trên 1 row Bronze | Modal lineage trace bronze → silver → gold |

---

## 4. Sprint 8 — Conversational Layer (F-NEW4)

| # | Surface | Action | Expected |
|---|---|---|---|
| 4.a | Bất kỳ page P2 | Click ChatPanel icon (right drawer) | Drawer slide in (cream + gold) |
| 4.b | Type "Tình trạng pipeline tháng này" + Enter | `POST /chat/enterprise/stream` SSE | Stream: text chunks + tool_call cards (P2 tools: pipeline_runs_summary, decisions_search, customers_at_risk_summary) |
| 4.c | ToolCallCard | Click expand | Args + preview JSON visible (audit transparency) |
| 4.d | P1 Platform admin | ChatPanel ở `/platform/*` (role gate SUPER_ADMIN/ADMIN/SUPPORT) | P1 tools: workspaces_summary, llm_usage, sessions_audit |
| 4.e | Args sent | Inspect request body | Tool args **không** chứa `tenant_id`/`user_id`/`workspace_id` (K-12 + K-16 enforced) |
| 4.f | K-15 audit | Query `audit_log` table sau dispatch | 1 row mỗi enterprise tool dispatch với tool_name + tenant_id |

---

## 5. Cross-cutting invariants

| # | Invariant | Cách kiểm tra |
|---|---|---|
| 5.a | K-1 RLS | Login enterprise A; cố `GET /api/v1/decisions/{id}` của enterprise B → 404 (RLS lọc, NOBYPASSRLS) |
| 5.b | K-3 LLM router | Tất cả LLM gọi qua `:8095` llm-gateway; query `decision_audit_log WHERE decision_type='llm.completion'` ra rows |
| 5.c | K-4 Privacy | Tenant `consent_external=false` → mọi LLM call dùng Qwen, không Claude/GPT |
| 5.d | K-5 PII redact | External call → request body chứa `<EMAIL_1>`, `<PHONE_1>`, không plaintext |
| 5.e | K-6 Audit | Sau mọi automated decision (mapping confirm, override, action, framework run) → `decision_audit_log` row |
| 5.f | K-7 JWT headers | Inspect bất kỳ request từ gateway → BE: có `X-Enterprise-ID`, `X-User-Id`, `X-Role` |
| 5.g | K-8 Idempotent upload | Upload cùng file 2 lần | Lần 2 trả `is_duplicate=true`, tái dùng `bronze_file_id` |
| 5.h | K-12 No tenant in QS | Cố `GET /api/v1/decisions?enterprise_id=other` | 200 nhưng JWT enterprise_id thắng (query param ignore) |
| 5.i | K-13 Idempotency-Key | POST cùng mutation 2 lần với cùng key (Redis TTL 24h) | Lần 2 trả cached response, không double-write |
| 5.j | K-14 Problem+JSON | Trigger 401/403/422 bất kỳ → header `Content-Type: application/problem+json`; body `{type, title, status, detail, instance, errors?}` |

---

## 6. Edge cases — đã biết KHÔNG nằm trong sweep này

> Anh + claude edge thấy nên thêm vào danh sách này trước khi audit:

- ~~`/p2/pipelines/new` 404~~ — đã fix PR #161
- `POST /api/v1/pipelines` không tồn tại — đã document trong memory `project_pipeline_create_flow.md`
- `/p2/pipelines/{id}` (route detail không có step segment) — chưa wire (anh sẽ thấy 404 nếu click row trong manager). Đề xuất fix tiếp theo: tạo redirect tới step hiện tại dựa trên `status`
- F-013 onboarding `/p2/onboarding` (Phase 2 path) — chưa wire; legacy `/register` chạy
- `/p2/settings` — chưa explicit có route page riêng (có `/p2/branding`, `/p2/branding/email`); confirm với anh
- F-026 LLM router, F-031 cron, F-032 Gold layer = backend-only (no FE surface)
- Reports builder `/p2/reports/builder` + template library `/p2/reports/template` = MSW mock (BE chưa wire)
- F-013 Phase 2 onboarding wizard, F-029 cursor edge cases, F-030 plan downgrade

---

## 7. Cách dùng file này với claude edge

1. Anh mở claude edge ở browser
2. Paste **toàn file này** + paste 1-2 file UAT chi tiết liên quan từ `docs/uat/` để Claude có sample format
3. Yêu cầu: "Audit edge cases mà sweep này thiếu, focus vào: (a) authorization boundaries — cross-tenant, role downgrade; (b) idempotency replays; (c) RFC 7807 error envelope hoàn chỉnh; (d) race conditions trong pipeline wizard step transitions; (e) LLM consent flag persistence qua refresh"
4. Anh paste phản hồi của claude edge về cho em (Kaori) → em apply fix hoặc thêm test

---

*Last updated: 2026-05-04 sau PR #161 (pipeline canonical routes).*
