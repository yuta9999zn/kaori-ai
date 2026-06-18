# UI Screens Inventory — 77 screens across 6 portals

> **Source:** `D:\Kaori Document\define màn hình.txt` (2026-05-09) + Phase 2.8 Round 3 expansion (2026-05-21)
> **Last imported:** 2026-05-12 · **Synced to Phase 2.8 Round 3:** 2026-05-24 (P2.8 scaffold + BIL→P6 + SH→P5 rename per BRD v4.1 / PRD v6.1 / RACI v1.1)
> **Canonical screen catalog:** `docs/sprint/feature-screens.html` (card-level, v 2026-05-21 Round 3) — this file is the route/scope mirror.
> **Audience:** Frontend (route + page scaffolding), Product (scope tracking)
> **Cross-ref:** `D:\Kaori Document\frontend template\` for design templates per portal (memory `feedback_design_templates`). FE Impl Spec: `docs/sprint/PHASE_2_8_FE_IMPL_SPEC.md`. Screen catalog HTML: `docs/sprint/feature-screens.html`.

77 screens total (16 P1 + 37 P2 + 8 P3 + 6 P4 + 6 P5 + 4 P6). Numbering: per-portal sequential. Each row = one Next.js route. Round 3 (2026-05-21) added 7 P2 screens (P2-31..37) and renamed Shared→P5, Billing→P6 per BA 6-portal convention (BRD v4.1 / PRD v6.1).

---

## P1 — Platform Manager (16 screens)

Route base: `/platform/*`. Users: SUPER_ADMIN, ADMIN, SUPPORT, CSM. MFA required for SUPER_ADMIN.

| # | Screen | Purpose |
|---|---|---|
| P1-01 | Platform Login / MFA | Đăng nhập admin, MFA TOTP, session security |
| P1-02 | Internal Command Center | Dashboard tổng quan: incidents, tenants, MRR, token cost |
| P1-03 | Workspaces List | Filter theo plan / status / industry / health |
| P1-04 | Create Workspace | Sinh KAORI-XXXX, chọn plan / industry / quota |
| P1-05 | Workspace Detail | Usage, members, billing, health, keys, recent events |
| P1-06 | Private Key Management | Reveal once, revoke, usage history |
| P1-07 | Platform Admin Directory | Invite admin, role, MFA status, session revoke |
| P1-08 | Billing Monitor | Quota, unique customers billed, overage, revenue |
| P1-09 | Pilot Conversion Pipeline | D1-D30 funnel, D25 reminder, D30 upgrade prompt |
| P1-10 | Customer Success Portfolio | Health state, CSM queue, tenants cần gọi hôm nay |
| P1-11 | Tenant Health Detail | 5 sub-scores, 90-day trend, milestone gates, playbook |
| P1-12 | Renewal Risk Dashboard | At-risk customers, save campaign, executive escalation |
| P1-13 | Platform Health / Observability | API uptime, workflow failures, token latency, DLQ |
| P1-14 | LLM Provider Management | Qwen, external providers, token quotas, privacy mode |
| P1-15 | Subscription Plan Config | Plan versions, quota rules, historical subscribers |
| P1-16 | Audit Query / Security Ops | Cross-tenant audit search, denied access, policy events |

---

## P2 — Enterprise Portal (37 screens)

Route base: `/p2/*`. Users: MANAGER (≥1 required), OPERATOR, ANALYST, VIEWER.

| # | Screen | Purpose |
|---|---|---|
| P2-01 | Enterprise Login / Activate Key | Login flow + first-time activation |
| P2-02 | Onboarding Wizard | Company, branding, departments, invite, wedge selection |
| P2-03 | Enterprise Dashboard | ROI/NOV, health score, alerts, quota, insights |
| P2-04 | Organization / Departments | Folders, quota allocation, sensitivity tags |
| P2-05 | Branding Editor | Logo, theme, report/email branding |
| P2-06 | Users & Roles | Invite, role editor, manager enforcement |
| P2-07 | Data Explorer | Bronze/Silver/Gold overview |
| P2-08 | Bronze Layer Detail | Raw files, checksum, schema preview |
| P2-09 | Silver Layer Detail | Cleaned data, quality rules, transformations |
| P2-10 | Gold Layer Detail | Churn, LTV, revenue_at_risk, features |
| P2-11 | Pipeline Step 1 — Upload | Resumable upload, pre-flight check |
| P2-12 | Pipeline Step 2 — Columns Mapping | Schema detection + user confirmation. 3-tier grouping (🔴 cần xác nhận / 🟡 kiểm tra nhanh / 🟢 đã chuẩn) + Unnamed "bỏ qua tất cả" + real sample/null% + value-sniffed types + business labels (UX rebuild 2026-05-24) |
| P2-13 | Pipeline Step 3 — Clean Rules | 3-layer cleaning preview |
| P2-14 | Pipeline Step 4 — Analyze | Framework + question composition |
| P2-15 | Pipeline Step 5 — Results | Insight + action |
| P2-16 | Auto Database Design | Schema suggestion, ERD, SQL, generated forms |
| P2-17 | Analysis Dashboard | Basic / intermediate / advanced analysis |
| P2-18 | Framework Canvas | SWOT, 6W, 2H, Fishbone, MoM/YoY |
| P2-19 | Insights List | Stream of generated insights |
| P2-20 | Insight Detail | "Chuyện gì / Tại sao / Nên làm gì" + citation + confidence |
| P2-21 | AI Decision Log | Decision history per workflow |
| P2-22 | Decision Detail / Override | View + override (K-6 audit trail) |
| P2-23 | Reports Dashboard | List + schedule |
| P2-24 | Report Builder | Compose + preview |
| P2-25 | Report Distribution | Channels: email, slack, webhook |
| P2-26 | Workflow Builder | **PIVOT → BPMN thật (bpmn-js)** 2026-05-29. BE ship: `GET/PUT /workflows/{id}/bpmn` (lưu BPMN 2.0 XML, mig 115) + `POST /workflows/{id}/bpmn/sync` (chiếu BPMN → nodes/edges có pool/lane, mig 116) + nối runner (`node_type_catalog_key`, mig 117). Mapper full-fidelity `workflow_runtime/bpmn_mapper.py`. **FE ship 2026-05-30:** tab "BPMN" trong `60-workflow-detail.tsx` → `components/bpmn/BpmnPanel.tsx` (dynamic `ssr:false`) + `BpmnEditor.tsx` (bpmn-js 18 modeler + panel VN gán KAORI_ACTIONS qua `kaori:nodeType`, moddle ext `lib/bpmn/kaori-moddle.ts`); nút Tải lại / Lưu sơ đồ / Lưu & Đồng bộ; hiện design_summary + dangling. Watermark bpmn.io giữ. **Constructs ship 2026-05-31→06-01 (PR #306-311, LinearBuilderView):** rẽ nhánh if/else (condition editor) · switch theo khoảng tiền · dry-run "▶ Chạy thử" tô sáng đường đi · reroute "Đi tới bước" · loop/for-each (runner chạy thật N lần) · field-picker datalist từ /schema/fields · BPMN swimlane phân quyền (lane/bước → pool+laneSet). Spec → `WORKFLOW_BUILDER_REDESIGN.md` §11/§13 + §"Builder constructs SHIPPED 2026-05-31" |
| P2-27 | Workflow Testing / 90-day Parallel Run | Test + parallel-run mode |
| P2-28 | Process Mining | Scope, findings, translate to workflow |
| P2-29 | Risk / Strategy / OKR Workspace | Combined planning canvas |
| P2-30 | Subscription & Quota | Usage, forecast, upgrade CTA |
| P2-31 ⭐ | Industry Template Library | Catalog 8 ngành; bootstrap entry (ADR-0026, mig 101/103, scaffolded 2026-05-23) |
| P2-32 ⭐ | Bootstrap Preview | Dry-run preview pre-confirm; 2-step type-to-confirm (scaffolded 2026-05-23) |
| P2-33 ⭐ | CS Ticket Inbox & Triage | Multi-channel triage (email/Zalo/web/phone) — workflow D.1 (scaffolded 2026-05-23) |
| P2-34 ⭐ | CS Ticket Detail | Conversation + customer 360 + AI suggested reply — D.1+D.2 (scaffolded 2026-05-23) |
| P2-35 ⭐ | NPS Dashboard & Follow-up | Scorecard + auto-followup rules — D.3 (scaffolded 2026-05-23) |
| P2-36 ⭐ | Refund Approval Queue | Policy match + claim-gated approve — D.4 (scaffolded 2026-05-23) |
| P2-37 ⭐ | Churn Save Workspace | Kanban risk tier + NOV impact + playbooks — D.5 (scaffolded 2026-05-23) |

---

## P3 — Studio (8 screens)

Route base: `/p3/*`. Users: STUDIO_ADMIN, STUDIO_ANALYST (per-enterprise scope).

| # | Screen | Purpose |
|---|---|---|
| P3-01 | Studio Home | Project list + recent activity |
| P3-02 | Projects List | Filter + create |
| P3-03 | Project Detail | Datasets, members, models, reports |
| P3-04 | Model Registry | Versions, deploy state |
| P3-05 | Training Log / Compare Runs | Per-run metrics + diff |
| P3-06 | Report Composer & Delivery | Compose for P2 consumption |
| P3-07 | Prompt Tuning / A/B Test | LLM prompt evolution + variant comparison |
| P3-08 | Studio Settings / Enterprise Scope | Scoping to assigned enterprises |

---

## P4 — Personal Portal (6 screens)

Route base: `/p4/*`. Users: PERSONAL_USER (self only).

| # | Screen | Purpose |
|---|---|---|
| P4-01 | Personal Signup / Login | Signup + login flow |
| P4-02 | Personal Dashboard | Self overview |
| P4-03 | Data Upload | Personal data ingest |
| P4-04 | Data Library | Personal data catalog |
| P4-05 | Goals & Plans | Personal OKR (P4 only) |
| P4-06 | Tracking + AI Suggestions | Daily / weekly check-in |

---

## P5 — Shared Infrastructure (6 screens)

Route base: `/shared/*`. (Renamed from `SH-*` in Round 3 per 6-portal convention; route stays `/shared/*` per CLAUDE.md §1.)

| # | Screen | Purpose |
|---|---|---|
| P5-01 | Guardrails Review | LLM output validation review (K-3 / output_schema fails) |
| P5-02 | MCP Server Console | MCP authz + tool catalog (K-15) |
| P5-03 | Observability Trace Detail | Per-trace tenant_id timeline (K-19) |
| P5-04 | DLQ Recovery Console | 5-source unified DLQ inspection + manual replay (Phase 2.7) |
| P5-05 | Audit Event Detail | Per-event drilldown |
| P5-06 | Knowledge Graph / Lineage / Blast Radius | Neo4j 7-Primitives view + impact analysis |

---

## P6 — Billing (4 screens)

Route base: `/billing/*`. (Renamed from `BIL-*` in Round 3 per 6-portal convention; route stays `/billing/*` per CLAUDE.md §1.)

| # | Screen | Purpose |
|---|---|---|
| P6-01 | Payment Methods | Card / bank / wallet management |
| P6-02 | Invoice List / Detail | History + per-invoice line items |
| P6-03 | Subscription Lifecycle | Renew, upgrade, downgrade, cancel |
| P6-04 | ROI Hybrid Billing Report | Revenue-saved tracking for ENT ROI plan |

---

## Priority order (anh chốt)

8 màn hình ưu tiên build trước (per định nghĩa cuối file source):

1. **P1-02** Internal Command Center — admin mission control
2. **P1-10** Customer Success Portfolio — lấy từ playbook 90 ngày, differentiation
3. **P1-11** Tenant Health Detail — Health State Machine + milestone gates + CSM playbook
4. **P2-03** Enterprise Dashboard — màn khách hàng nhìn thấy giá trị đầu tiên
5. **P2-11..15** Pipeline Wizard 5 steps — flagship UX
6. **P2-20** Insight Detail — AI decision loop
7. **P2-26 / P2-28** Workflow Builder / Process Mining — moat capability v4
8. **P3-03** Studio Project Detail — analyst / data team

---

## Coverage mapping vs current `frontend/` code

Tracking which screens already have code in `frontend/app/` (last verified 2026-05-12). To be filled when FE restructure starts:

| # | Route | Status | Notes |
|---|---|---|---|
| **P2-03** | `/p2/dashboard/overview` | ✅ **WIRED** | **Reference pattern** (2026-05-24). First screen on real backend: `useQuery` + `api<T>()`, dashboard/state + north-star + billing + insights/feed, loading/error/empty/state-machine. Header comment = the playbook to replicate. Mock kept at `09-dashboard-overview.tsx`. |
| (others) | ... | ⏳ | Replicate P2-03 pattern as FE work resumes |

> **⚠️ Legacy mock route wrappers (resolve during FE restructure).** `frontend/app/` currently holds ~124 `page.tsx` files vs the 77 canonical screens here — the extra are dynamic `[id]` routes, pipeline sub-steps, and **6 orphaned legacy-mock wrappers** that duplicate canonical `[id]` routes and are not linked from anywhere: `p2/decisions/id`, `p2/insights/id-detail`, `p2/users/id-detail`, `p2/workflows/detail` (already a redirect alias), `p2/workflows/id-test`, `p2/alerts/detail`. Each thinly wraps a numbered template under `components/p2/templates/NN-*` (anh's mockup library). Decision 2026-05-24: **keep as-is**, fold into the canonical `[id]` routes when FE restructure resumes (§2 CLAUDE.md). Do NOT count them as screens.

---

## Maintenance

- Add a screen → row in §1-§6 + bump count in section header + cross-ref any `frontend/app/` route added.
- Remove a screen → strike-through with date + reason. Do NOT delete (history matters for product retrospective).
- Re-prioritise → update §Priority order with a date stamp.
