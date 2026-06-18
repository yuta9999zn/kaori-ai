# Phase 2.8 — FE Implementation Spec (thin) — v1.1

> **Version:** 1.1 · 2026-05-21 · sibling tới `feature-screens.html` + `workflow-builder-ux.html` + `feature-workflows.html` + `kaori-shared-glossary.html`.
>
> **Scaffold log (2026-05-23):** 7 màn NEW (**P2-31, P2-32, P2-33, P2-34, P2-35, P2-36, P2-37**) đã có skeleton template + route page wired. File location: `frontend/components/p2/templates/75-81*.tsx` + `frontend/app/(app)/p2/{templates/industries,onboarding/bootstrap-preview,cs/*}/page.tsx`. Data layer + TanStack Query hooks chưa wire — chỉ stub `[]` + TODO markers. Permission gates marked với `TODO P2-XX-PERM:` comments. Step 2 FE restructure (sequence 1→4 anh chốt 2026-05-23).
>
> **Thay đổi vs v1.0:** (a) cập nhật 72→**77 màn** sau rename BIL/SH→P5/P6 + thêm 5 CS screens; (b) thêm spec **P2-33..P2-37 Customer Service vertical**; (c) thêm §Permission Claims (link NFRS v1.1 §5.bis); (d) thêm §Accessibility WCAG 2.1 AA; (e) thêm §Mobile Responsiveness; (f) thêm §Observability OpenTelemetry; (g) thống nhất naming P5/P6 + STUDIO_ANALYST = STU-01; (h) clarify Phase 2.8 = sprint code; (i) map per-screen ↔ URD US-IDs; (j) test strategy full pyramid.
>
> **Purpose:** Bridge giữa **UX spec** (feature-screens.html + workflow-builder-ux.html) và **code FE** (Next.js 16 + TS). Mỗi màn priority có: route, component tree, state, API, permission gates, empty/loading/error states, **US-ID traceback**. FE team có thể implement theo spec này khi anh restructure FE template xong (CLAUDE.md §2 hiện ĐANG TẠM DỪNG).
>
> **Phase ngữ pháp:** "Phase 2.8" trong tài liệu này là **sprint code nội bộ**, thuộc **Phase 2** trong BA roadmap (BRD v4.1 §8). Không nhầm với BA Phase 1/1.5/2/3.
>
> **Audience:** FE engineers cài đặt portal P2 lần đầu. Không cover P1/P3/P4/**P5 Shared Infrastructure/P6 Billing**.
>
> **Source of truth:**
> - `docs/sprint/feature-screens.html` — full screen catalog (**77 màn · 6 portal: P1-P6**; baseline 2026-05-21 Round 3)
> - `docs/sprint/workflow-builder-ux.html` — Workflow Builder mockup (4-step builder-only post-bootstrap)
> - `docs/specs/WORKFLOW_BUILDER_REDESIGN.md` — Builder hybrid lane+canvas redesign (P0 nhánh→edge thật shipped 2026-05-29; P1/P2 proposed)
> - `docs/sprint/feature-workflows.html` — Internal workflow catalog (KHÔNG dành cho khách, tham khảo cho dev)
> - `docs/sprint/kaori-shared-glossary.html` — Shared glossary (K-rules, L-layers, Medallion, 7-Primitives, T-Cube, NOV, Card 7-field SSOT, 3-Mode UI, Plan Gate)
> - `docs/specs/UI_SCREENS_INVENTORY.md` — design templates location pointers
> - `docs/specs/VALIDATION_RULES.md` — per-field input constraints
> - `docs/specs/MESSAGE_DEFINITIONS.md` — error codes (SYS-ERR* / USR-ERR*) + RFC 7807 wiring
> - **BA layer**: BRD v4.1 · URD v2.1 (G/W/T + UR-CS) · PRD v6.1 · NFRS v1.1 (§5.bis Permission Claims)
>
> **Tech stack** (chốt — không defer):
> - Next.js 16 (App Router) + TypeScript strict mode
> - Design templates ở `D:\Kaori Document\frontend template\` — base với **shadcn/ui** + Tailwind (chốt; thay vì defer FE kickoff)
> - Server state: TanStack Query (React Query v5)
> - Local state: Zustand (predictable + devtools, chốt)
> - Form: react-hook-form + zod (validation per `VALIDATION_RULES.md`)
> - i18n: tiếng Việt default; English Phase 2 sprint P2-S23
> - Routing: file-based `/p2/...`
> - Observability: Sentry (errors) + OpenTelemetry web SDK (tracing — propagate `traceparent` header per W3C Trace Context)
> - Real-time: polling 1-30s tuỳ tốc độ (chốt cho Phase 2.8); WebSocket defer Phase 3.

---

## Scope

**11 priority + 2 NEW Industry-first + 5 NEW Customer Service vertical = 18 màn Phase 2.8:**

| Bucket | Screens | Reason |
|---|---|---|
| Priority hiện tại | P2-02 · P2-03 · P2-04 · P2-11 · P2-15 · P2-20 · P2-26 · P2-27 · P2-28 | Core flow data→insight→action |
| NEW Industry-first | P2-31 (Industry Library) · P2-32 (Bootstrap Preview) | Onboarding wedge per archetype |
| **NEW Customer Service vertical** ⭐ | **P2-33 · P2-34 · P2-35 · P2-36 · P2-37** | Match 5 CS workflow D.1-D.5 trong catalog. Defer 5 CS workflow = orphan UI; phải ship cùng baseline 2026-05-21 |

Defer sau khi 18 priority này có FE production: P2-01/05/06/07/08/09/10/12/13/14/16/17/18/19/21/22/23/24/25/29/30.

Không cover trong Phase 2.8: P1 Platform Manager · P3 Studio · P4 Personal · P5 Shared Infrastructure · P6 Billing.

---

## Shared / Common (mandatory before per-screen work)

### Layout shell

```
<RootLayout>                              # app/(p2)/layout.tsx
├── <AuthGuard>                           # gates by JWT; redirects /p2/login if expired
│   ├── <TenantContext>                   # X-Enterprise-ID + tenant_id + role claim + permissions[] claim
│   ├── <TopNav>                          # Business IA only — see §Navigation IA below
│   │   ├── <BrandLogo>                   # tenant-customized (P2-05)
│   │   ├── <PrimaryMenu>                 # role+claim-gated items
│   │   └── <UserMenu>                    # avatar + logout + MFA
│   ├── <BreadcrumbBar>                   # auto-generated từ route segments
│   ├── <main>{children}</main>
│   └── <Toaster>                         # global RFC 7807 errors + success toasts
```

### Top Nav — Business IA

| Section | Items | Role gate |
|---|---|---|
| Workspace | Dashboard · Org · Branding | All roles |
| Workflows | Builder · Testing · Industry Library · Bootstrap Preview | OPERATOR+ |
| Data | Upload (2-mode) · Mapping · Clean · Bronze · Silver · Gold | OPERATOR+ |
| Insights | Analysis · Results · Insights List · Insight Detail · Process Mining (Discovery) | VIEWER+ |
| Reports | Charts · Reports List · Builder · Distribution | VIEWER+ |
| OKR / Strategy | OKR Workspace | MANAGER+ |
| **Customer Service** ⭐ NEW | **CS Inbox · Ticket Detail · NPS Dashboard · Refund Queue · Churn Save** | OPERATOR+ (mỗi item có claim riêng — xem §Permission Claims) |
| Admin | Onboarding (re-run) · Users · Roles · Subscription | MANAGER+ |

**Platform/Internal IA** (Audit · Observability · DLQ · MCP · Guardrails) — ẨN khỏi customer top nav. Gated qua JWT `permissions[]` claim. **Anti-pattern:** KHÔNG render menu "Permission denied" — hide hoàn toàn nếu không có claim.

### Permission Claims (link tới NFRS v1.1 §5.bis)

NFRS v1.1 vừa formalize concept "Permission Claims" — capability-based granular permission bên trên RBAC role. Spec FE dùng claims sau:

| Claim | Grants | Default for role |
|---|---|---|
| `view_audit_log` | P2-21 AI Decision Log | None (cấp riêng) |
| `view_observability` | P1-13 Platform Health | None |
| `manage_dlq` | P5-04 DLQ Console | None |
| `view_mcp` | P5-02 MCP Console | STU-01 (alias STUDIO_ANALYST) |
| `review_guardrails` | P5-01 Guardrails Review | None |
| `platform_admin` | All P1 screens | SUPER_ADMIN, ADMIN |
| `approve_workflow_promotion` | P2-27 Mode 2 "Promote B" | MANAGER (auto-grant) |
| **`triage_cs_tickets`** ⭐ | P2-33, P2-34 | OPERATOR auto-grant if dept=CS |
| **`approve_refund`** ⭐ | P2-36 approve action | MANAGER auto-grant if dept=CS |
| **`run_churn_save_action`** ⭐ | P2-37 action panel | OPERATOR+ if dept=CS |

`useRequireClaim('claim_name')` wrapper trả `ForbiddenError('USR-ERR-403-CLAIM')` nếu không có claim.

### RBAC route guard

```ts
// lib/auth/use-role.ts
export const ROLE_HIERARCHY = ['VIEWER', 'OPERATOR', 'ANALYST', 'MANAGER'] as const;
// STU-01 (STUDIO_ANALYST) is a cross-tenant role separate from this hierarchy

export function useRequireRole(min: Role) {
  const { role } = useTenant();
  if (ROLE_HIERARCHY.indexOf(role) < ROLE_HIERARCHY.indexOf(min)) {
    throw new ForbiddenError('USR-ERR-403-ROLE');
  }
}

export function useRequireClaim(claim: string) {
  const { permissions } = useTenant();
  if (!permissions.includes(claim)) {
    throw new ForbiddenError('USR-ERR-403-CLAIM');
  }
}
```

Page-level guard via `app/(p2)/<screen>/page.tsx`. Lower-role users SEE màn nhưng hidden CTA per-component qua `<RoleGate min="MANAGER">` hoặc `<ClaimGate claim="approve_refund">` wrapper.

### Error handling (RFC 7807)

```ts
// lib/api/error.ts — global response interceptor
type ProblemDetails = {
  type: string;     // e.g. "https://kaori.ai/errors/IND-001"
  title: string;
  status: number;
  code: string;     // SYS-ERR-* / USR-ERR-*
  detail?: string | object;
  instance: string;
  hints?: string[]; // per MESSAGE_DEFINITIONS.md
  issues?: Array<{ field: string; code: string }>; // 422 only
};
```

- 4xx → render toast hoặc inline error theo `code`; lookup `MESSAGE_DEFINITIONS.md` cho VN/EN string.
- 5xx → red toast + "Retry" button + Sentry capture + OpenTelemetry span error.
- 401 → redirect `/p2/login?return=<current>`.
- 403 (role) → màn "Permission denied — liên hệ admin" (KHÔNG redirect).
- 403 (claim) → tương tự, nhưng message specific "Tính năng X cần quyền Y. Liên hệ admin để được cấp."
- 409 (duplicate / already-bootstrapped) → modal "Resource conflict" + recovery CTAs.

### Loading + Empty + Error states (baseline)

- **Loading:** skeleton per tile/row, KHÔNG full-page spinner.
- **Empty:** text + CTA "Bắt đầu...". Tone friendly, kéo user vào action gần nhất.
- **Error:** red banner inline (tile-level) ưu tiên hơn full-page red. Toast cho transient.
- **Permission:** gate component renders nothing (preferred) hoặc faded chip "Cần MANAGER+/claim X để xem" nếu UX explainability tốt hơn.

### Accessibility (NFR-U-08 — WCAG 2.1 AA Phase 1) ⭐ NEW

- **Contrast:** text 4.5:1, large text 3:1. Tailwind palette đã chuẩn cho default theme; verify dark mode.
- **Keyboard navigation:** mọi interactive element reachable bằng Tab; focus visible (outline 2px solid `--accent`).
- **ARIA labels:** mọi icon button có `aria-label`; SVG decorative có `aria-hidden="true"`.
- **Form labels:** mọi input có `<label for>` hoặc `aria-labelledby`; error state `aria-invalid="true"` + `aria-describedby` linking error message.
- **Skip link:** "Bỏ qua điều hướng" hidden link đầu page, focus visible khi tab.
- **Audit tool:** `axe-core/playwright` chạy trong CI cho 18 priority screens. Block release nếu có violation severity ≥ MODERATE.
- **Phase 3:** WCAG 2.1 AA đầy đủ (NFR-U-08).

### Mobile Responsiveness (NFR-U-07) ⭐ NEW

Phase 2.8: **desktop-first** (1280+ width baseline). Subset responsive:

| Screen | Desktop (1280+) | Tablet (768-1279) | Mobile (<768) |
|---|---|---|---|
| P2-03 Dashboard | Full | Stack tiles; KpiStrip 2-col | Stack tiles; KpiStrip 1-col |
| P2-20 Insight Detail | Full | Tabs vertical; rail bottom | Tabs vertical; rail bottom |
| P2-33 CS Inbox | Full | Single column table | Card list view |
| P2-34..37 CS các màn | Full | Stack panels | Read-only |
| Còn lại (P2-02/04/11/15/26/27/28/31/32) | Full | Read-optimized, không support edit | Redirect "Vui lòng dùng desktop" |

Phase 3: full mobile cho mọi màn (per NFR-U-07).

### Observability (NFR-O-01 — OpenTelemetry) ⭐ NEW

- **Tracing:** instrument `fetch` qua `@opentelemetry/instrumentation-fetch`. Mọi API call attach `traceparent` header per W3C Trace Context. Trace ID kế thừa từ JWT `trace_id` claim nếu có, hoặc generate root span.
- **Logging:** structured JSON `{level, trace_id, tenant_id, user_id, action, ...}` ra console + Sentry.
- **Metrics:** Web Vitals (LCP/FID/CLS/TTI/INP) → Datadog RUM hoặc Sentry Performance.
- **PII:** KHÔNG log raw PII vào trace/metrics; mask trước theo NFR-PR-02.

---

## P2-02 Onboarding Wizard (7-step Industry-first)

**Route:** `/p2/onboarding` · **URD US-ID:** US-A1, US-A3 · **Permission:** MANAGER+ only (Step 7 confirm). Step 1-6 OPERATOR+ có thể preview. · **Reference:** `feature-screens.html § P2-02`

**Component tree:**
```
<OnboardingPage>
├── <StepperBar>                          # 7 steps, current highlighted
├── <StepIndustryPicker step={1} />       # P2-31 reused as embedded
├── <StepBootstrapPreview step={2} />     # P2-32 reused as embedded
├── <StepDepartmentSelect step={3} />     # checkboxes per dept
├── <StepWorkflowSelect step={4} />       # per-dept workflow tiles
├── <StepInviteUsers step={5} />          # CSV upload + role suggest
├── <StepUploadData step={6} />           # schema-typed file slots
├── <StepConfirm step={7} />              # final summary + diff vs Step 2
├── <StepNav>                             # Back / Save draft / Continue
└── <SkipModal>                           # confirm khi click "Skip for now"
```

**State:**
- Local (Zustand `onboardingStore`): `currentStep`, `selectedIndustry`, `selectedDepts[]`, `selectedWorkflows[]`, `inviteCsv`, `uploadedFiles[]`. Persists localStorage + backend draft.
- Server (React Query): `['industries']` · `['industries', id]` · `['enterprise-bootstrap-status', enterpriseId]`.

**API:**
- `GET /industries` — overview list (8 industries, 3 seeded)
- `GET /industries/{id}` — full bundle (depts + workflows + KPIs + schemas + roles)
- `POST /enterprises/{id}/bootstrap-from-industry?dry_run=true` — Step 2 preview compute
- `POST /enterprise-users/onboard-from-csv` — Step 5 bulk invite (mig 061)
- `POST /v1/upload` — Step 6 first data upload
- `POST /enterprises/{id}/bootstrap-from-industry?dry_run=false` — Step 7 final destructive write

**States:** Empty (no industry picked) · Loading dry_run · Error industry not seeded · Permission (V/O read-only đến Step 6) · Already bootstrapped redirect /p2.

**AC checklist:** Maps to US-A1/A3 (URD §3 UR-A). NFRS §13.3 4-case applies.

---

## P2-03 Enterprise Dashboard (action-first)

**Route:** `/p2` · **URD US-ID:** US-E1, US-E2 · **Permission:** VIEWER+. Quick action CTAs MANAGER+ only.

**Component tree:**
```
<DashboardPage>
├── <TodayQueue priority="top" />         # 4 action chips: approvals/wf-failures/docs-need-map/insights
├── <NsmTile />                           # Revenue at risk actioned (North Star)
├── <KpiStrip>                            # ROI / NOV / Health / Workflows / Alerts / Quota
├── <InsightFeed limit={3} />             # top 3 từ P2-19
├── <WhatChangedTimeline window="24h" />  # last 24h decisions + interventions
├── <DepartmentHealthSnapshot />          # mig 090 adoption_health_snapshots
├── <CalendarWidget />                    # upcoming workflow runs + reports
└── <QuickActions>                        # + Upload · + Workflow · View report
```

**State:** Server polls — `['today-queue']` 60s · `['nsm']` 5m · `['kpi-strip']` · `['insight-feed', limit=3]` · `['adoption-snapshots']`.

**API:** `GET /p2/dashboard/today-queue` · `GET /p2/dashboard/nsm` · `GET /p2/dashboard/kpi-strip` · `GET /insights?limit=3&order=recent` · `GET /adoption/snapshots` (mig 090).

**States:** Empty chưa bootstrap → CTA P2-02 · Empty chưa data → upload prompt · Loading skeleton priority Today Queue · Error per-tile retry · Permission VIEWER ẩn QuickActions.

**AC checklist:** Maps to US-E1/E2 (URD §3 UR-E). NFRS §13.3 4-case applies.

---

## P2-04 Organization / Departments (3-view, có Org Tree GAP-01 closeout)

**Route:** `/p2/org` · **URD US-ID:** US-A4, **US-A5** (GAP-01 closeout) · **Permission:** VIEWER+. View 2 (Org Tree) drag-drop MANAGER+ only.

**Component tree:**
```
<OrgPage>
├── <ViewToggle>                          # [Cards | Tree | Cross-WF] persistent
├── <ViewCards>                           # default
│   └── <DepartmentCard /> × N
├── <ViewOrgTree>                         # GAP-01 closeout (CR-0001) — corporate group
│   ├── <TreePane />                      # drag-drop nodes; uses corporate_tree mig 055/056
│   ├── <NodeDetailPane />                # rollup KPI/NOV/Adoption per node
│   └── <CycleDetectionGuard />           # prevent A→B→A
└── <ViewCrossWorkflows>                  # spanning ≥2 dept
    └── <WorkflowCrossLinkTable />        # mig 057
```

**State:** Local `viewMode` persistent localStorage + backend pref. Server `['departments']` · `['org-tree']` · `['workflow-cross-links']`.

**API:**
- `GET /enterprises/{id}/departments`
- `GET /enterprises/{id}/org-tree` — corporate hierarchy mig 055/056
- `GET /workflow-cross-links?enterprise_id=` mig 057
- `POST /enterprises/{id}/departments/{did}/move` — View 2 bulk move (cycle detection BE)
- `POST /workflow-templates/{tid}/clone-to-department`

**States:** Empty (chỉ có Management dept) → CTA P2-02 · Loading skeleton · Error per-dept tile retry · Permission View 2 drag-drop chỉ MANAGER+ · Cycle conflict 409 "Vòng tròn không cho phép".

**AC checklist:** Maps to US-A4 + US-A5 (URD §3 UR-A). GAP-01 closeout: chỉ FE canvas, BE đã shipped.

---

## P2-11 Upload (2-mode + legacy wizard)

**Routes:**
- `/p2/data-inbox` — Mode 1 Quick Upload
- `/p2/workflows/{id}/steps/{sid}/upload` — Mode 2 Workflow Step Upload
- `/p2/pipeline/upload` — Mode 3 **Pipeline Wizard 5 bước** (standalone — Phase 1 flow, vẫn duy trì; không phải "legacy" deprecated)

**URD US-ID:** US-B1, US-B2, US-B3 · **Permission:** OPERATOR+ upload to inbox. MANAGER+ map vào workflow step.

**Component tree:**
```
<UploadShell mode="quick|step|wizard">
├── <ModeTabs>                            # 3 tabs: Quick · Step · Wizard
├── <ContextHeader />                     # Mode 2: workflow + step + dept (BẮT BUỘC visible)
├── <RequiredDocsChecklist />             # Mode 2: từ workflow_nodes.required_document_types
├── <DropZone>                            # resumable chunked (tus)
│   ├── <PreflightChecker />              # magic-byte detect, size, spoof guard
│   └── <DedupHandler />                  # SHA-256 K-8 hit modal
├── <UploadProgress />                    # per-file status pills
└── <InboxTable mode="quick">             # Mode 1 only
    └── <BulkMapDrawer />                 # 3-level picker dept→workflow→step
```

**State:** Local `pendingFiles[]`, `uploadProgress`, `selectedRows`. Server `['inbox']` 30s when pending · `['workflow-step', wfId, sid]` Mode 2 context.

**API:**
- `POST /v1/upload` — multipart, header `X-Workflow-Step-ID` optional (Mode 2 set)
- `GET /p2/data-inbox?status=UNMAPPED`
- `POST /p2/workflows/{id}/steps/{sid}/documents` (mig 053)
- `POST /p2/data-inbox/{file_id}/map`
- `GET /workflow-nodes/{nid}/required-document-types`
- `GET /industry-data-schema-templates/{schema_id}/sample-file`

**States:** Empty inbox · Loading progress · Error per-file chip · Permission V không upload / O inbox only / M+ map · Mode 2 block state "Còn thiếu Quote (XLSX)" · Dedup hit modal.

**AC checklist:** Maps to US-B1/B2/B3 (URD §3 UR-B). NFRS §13.3 4-case applies.

---

## P2-15 Results (workflow context-aware)

**Routes:** `/p2/pipeline/results` (standalone) · `/p2/workflows/{id}/runs/{rid}/results` (workflow-bound, Phase 2.8 chính)

**URD US-ID:** US-B5, US-B6 · **Permission:** VIEWER+ xem; trigger workflow / tạo task MANAGER+.

**Component tree:**
```
<ResultsPage>
├── <WorkflowContextHeader>               # BẮT BUỘC visible: WF name + version + run ID + duration + status
├── <SourceMetadata />
├── <ThreeTuyenInsight>                   # Stage 10
│   ├── <NarrativePanel />
│   ├── <DiagnosticPanel />               # chart + table breakdown
│   └── <PredictivePanel />               # 30-day forecast
├── <DiffPanel run="rid" prev="auto-pick">  # NEW Phase 2.8 — what changed
├── <ActionRail>
│   ├── <ActionRecommendation /> × 3
│   ├── <Citations />                     # inline [1][2][3] with hover preview
│   ├── <ConfidenceBreakdown />
│   └── <LineageWalkButton />             # mig 097 → graph modal
├── <FeedbackBar>                         # 👍/👎 + comment → Stage 12
└── <ActionToolbar>                       # Re-run · Save · Export · Pin · Share
```

**State:** Server `['workflow-run', rid]` · `['workflow-run-nodes', rid]` · `['workflow-run-prev']` for diff · `['lineage', 'workflow_run', rid, 'upstream']` lazy · `['similar-past', insightId]` T-Cube.

**API:** `GET /workflow-runs/{rid}` mig 088 · `GET /workflow-runs/{rid}/nodes` · `GET /workflows/{wfId}/runs?before={rid}&limit=1` · `POST /rag/answer` · `GET /lineage/{kind}/{id}/upstream` mig 097 · `POST /workflow-runs/{rid}/re-run?mode=same|new-data` · `POST /workflow-tasks` · `POST /insights/{id}/feedback`.

**States:** Empty (chưa chạy lần nào) → CTA P2-27 · Loading skeleton · Run in progress poll mig 094 · Run failed banner → DLQ Console link · Low confidence warning · Permission V không Re-run · No previous run diff panel ẩn.

**AC checklist:** Maps to US-B5/B6 (URD §3 UR-B). Confidence-based action policy enforce per NFRS §13.2.

---

## P2-20 Insight Detail (drilldown)

**Route:** `/p2/insights/{id}` · **URD US-ID:** US-B6 · **Permission:** VIEWER+ xem; action panel scoped theo role. "Permanently dismiss" MANAGER+ only.

**Component tree:**
```
<InsightDetailPage>
├── <InsightHeader>                       # severity · confidence · ago · workflow source
├── <ThreeSentenceSummary>                # Chuyện gì / Tại sao / Nên làm gì
├── <Tabs>
│   ├── <TabDescriptive />                # trend chart + numbers + period selector
│   ├── <TabDiagnostic />                 # breakdown + SHAP top-3 + Alt interpretations
│   └── <TabPrescriptive />               # actions priority + ROI estimate + WF template suggest
├── <ConfidenceBreakdown />
├── <CitationsPanel />                    # inline numbered + hover preview + click → P2-08/09/10
├── <AlternativeInterpretations collapsible />
├── <ComparisonRuns />                    # NEW: 3 auto-suggest prior insights
├── <LineageTraceButton />                # NEW mig 097
├── <ActionPanel>
│   ├── <TriggerWorkflowBtn />
│   ├── <CreateTaskBtn />
│   ├── <MarkResolvedBtn />
│   ├── <EscalateBtn />
│   ├── <SnoozeBtn />                     # 7 ngày auto-reactivate
│   ├── <MarkNotActionableBtn />          # NEW: ẩn khỏi list + feed Stage 12
│   └── <PermanentlyDismissBtn />         # NEW: MANAGER+ confirm 1 lần, K-6 audit
├── <SimilarPastInsights />               # T-Cube recall — 3 prior
├── <K6AuditPanel />                      # mig 098 visible (claim view_audit_log)
└── <CommentThread />                     # mig 072 collab pattern
```

**State:** Server `['insight', id]` · `['insight-alternatives', id]` · `['lineage', 'ai_decision', id, 'upstream']` · `['similar-past', id]` T-Cube body `{topic, limit=3}` · `['ai-audit', id]` mig 098.

**API:** `GET /insights/{id}` · `GET /insights/{id}/alternatives` · `POST /insights/{id}/comparison-runs` · `GET /lineage/ai_decision/{id}/upstream` · `POST /workflow-tasks` · `POST /insights/{id}/action` body `{action, reason}` · `GET /reasoning/similar-past?insight_id=` · `GET /ai-decision-audit/{id}` mig 098.

**States:** Empty 404 · Loading skeleton · Error data source missing · Low confidence (<0.5) warning · Permission V no action panel / O can task+snooze / M+ full · Snoozed chip "Snoozed cho đến 2026-06-01 (sample data)" · Resolved chip · Drilldown citation click → modal.

**AC checklist:** Maps to US-B6 (URD §3 UR-B). Confidence policy NFRS §13.2.

---

## P2-26 Workflow Builder (3-mode)

**Route:** `/p2/workflows/{id}/builder` · **URD US-ID:** US-F1, US-F4 (GAP-02 closeout) · **Permission:** VIEWER+ read. Edit theo mode + role + plan gate.

**Component tree:**
```
<WorkflowBuilderPage>
├── <ModeToggle>                          # Simple / Advanced / Developer, plan-gated buttons disabled
├── <WorkflowHeader />                    # name + version + dept + actions
├── <ActionToolbar>                       # Test · Send CR · Publish
├── {mode === 'simple' && (
│   <CardStackVertical>                   # NOT canvas
│     └── <Card editable={false}> × N    # click → CardEditorDrawer
│   </CardStackVertical>
│ )}
├── {mode === 'advanced' && (
│   <TwoPane>
│     <CardStackEditable />
│     <BranchInspectorPanel />
│   </TwoPane>
│ )}
├── {mode === 'developer' && (
│   <CanvasDragDrop>                      # 45-node catalog mig 068
│     <NodePalette /> <Canvas /> <YamlExport />
│   </CanvasDragDrop>
│ )}
├── <CardEditorDrawer mode="simple">      # đặc tả ở workflow-builder-ux.html Step 4 + glossary §Workflow Card (7-field SSOT)
│   ├── ... 7-field form (Owner/Input/Required docs/AI action/Branch/Output/SLA)
│   ├── <BranchActionRow>
│   │   ├── <ViewBranchLogicBtn read-only />
│   │   └── <SwitchToAdvancedBtn />
│   └── <AdvancedModeReference collapsible />
└── <CollabPresence />                    # editors + comments + locks mig 072
```

**State:** Local `currentMode`, `selectedCard`, `unsavedChanges`. Server `['workflow', wfId]` · `['workflow-nodes', wfId]` · `['workflow-mode']` · `['workflow-collab-presence', wfId]` poll 5s when editing.

**API:** `GET /workflows/{wfId}` + nodes · `GET /enterprises/{id}/workflow-mode` · `PATCH .../workflow-mode` · `POST /workflows/{wfId}/customize` body `{operation, edit_mode, diff}` · `POST .../test-run` · `POST .../change-requests` · `POST .../publish` · `POST .../collab/lock` + `DELETE` (K-13 lock token).

**States:** Empty (chưa bootstrap) → P2-02 · Loading skeleton · Error save fail K-2 "Snapshot đã lưu, tạo version mới" · Permission V no Publish / Simple chỉ M+ publish / Developer chỉ Platform admin · Lock state read-only · Plan-gated Advanced/Developer disabled tooltip "Cần ENT_BASIC+".

**AC checklist:** Maps to US-F1, US-F4 (URD §3 UR-F). GAP-02 closeout (CR-0002): BE đã shipped 45 node + 25 template + collab.

---

## P2-27 Workflow Testing (2-mode)

**Routes:** `/p2/workflows/{id}/test` Mode 1 · `/p2/workflows/{id}/parallel-run` Mode 2

**URD US-ID:** US-F2, US-F3 · **Permission:** MANAGER+ (cần `approve_workflow_promotion` claim cho Promote B).

**Component tree:**
```
<TestingPage>
├── <ModeTabs>                            # Test Run | A/B Parallel
├── {mode === 'test-run' && (
│   <TestRunShell>
│     <DatasetPicker />                   # sample Silver 50/100/500 hoặc custom upload
│     <SpeedToggle />                     # Quick / Step-through
│     <CardStackWithStatus />
│     <StateInspectorPane />
│     <RunControls />                     # Tiếp / Bỏ qua / Breakpoint
│   </TestRunShell>
│ )}
└── {mode === 'parallel' && (
    <ParallelRunShell>
      <VariantPicker />                   # A baseline + B variant
      <SplitConfig />                     # 50/50 / 90/10 canary + duration 90d
      <MetricPicker />                    # NOV ROI / approval time / CSAT / cost
      <LiveDashboard>
        <VariantStatsCard variant="A" />
        <VariantStatsCard variant="B" />
        <LiftAndSignificance />           # CI excludes 0?
      </LiveDashboard>
      <PromoteControls />                 # claim approve_workflow_promotion required
    </ParallelRunShell>
  )}
```

**State:** Local `dataset`, `speed`, `currentBreakpoint`, `mockExternalNodes`. Server `['test-run', rid]` 1s during run · `['parallel-run', wfId]` 30s · `['parallel-run-stats', rid]` 60s.

**API:** `POST /workflows/{wfId}/test-run` body `{dataset, speed, mock_external=true}` mig 088 side_effect mock=TRUE · `GET /workflow-runs/{rid}` poll · `POST .../parallel-run` body `{baseline_version, variant_version, split, duration_days, metric}` Stage 12 Loop · `GET .../parallel-run/{rid}/status` · `POST .../promote` claim required · `POST .../discard` · `POST /test-runs/{rid}/replay` mig 094 replay.

**States:** Empty no Silver data · Loading run starting · Error external node fail dry-run · Permission SME chỉ Mode 1 / A/B claim required · Mode 2 inconclusive @90d yellow · Auto-stop early green.

**AC checklist:** Maps to US-F2/F3 (URD §3 UR-F).

---

## P2-28 Process Mining (2-mode)

**Routes:** `/p2/process-mining` landing · `/p2/process-mining/discover` Mode 1 · Mode 2 Analyst View via tab.

**URD US-ID:** US-C1, US-C2, US-C3, US-C4 · **Permission:** OPERATOR+ Mode 1 discover. **STU-01 (alias STUDIO_ANALYST)** mới mở Mode 2.

**Component tree:**
```
<ProcessMiningPage>
├── <ModeTabs>                            # Discovery | Analyst
├── {mode === 'discovery' && (
│   <DiscoveryShell>
│     <BigDiscoverCta />                  # "Phát hiện workflow của tôi"
│     <DiscoveryWizard>
│       <StepConnectSources />            # 10 sources: Postgres CDC/Excel/Zalo/Gmail/Outlook/Calendar/Slack/Teams/SharePoint/webhook
│       <StepFilterRange />               # dept + 90 ngày default
│       <StepPrivacyConsent />            # K-5 PII redact MUST tick
│     </DiscoveryWizard>
│     <FindingsList>
│       <FindingCard /> × N
│     </FindingsList>
│   </DiscoveryShell>
│ )}
└── {mode === 'analyst' && (
    <AnalystShell>
      <ConnectorStatusPanel />            # 10 sources throughput/lag/errors
      <ProcessTreeViz />                  # Inductive/Fuzzy/Heuristic Miner
      <ConformanceCheck />                # actual vs documented side-by-side
      <AnomalyCatalog />                  # 5 detector: z-score/EWMA/token-replay/rework/bypass
      <CohortCompare />                   # AI-HSC-016 2-cohort
      <PerCaseDrilldown />
    </AnalystShell>
  )}
```

**State:** Server `['pm-sessions']` · `['pm-findings', sessionId]` · `['pm-connectors-status']` 60s · `['pm-process-tree', sessionId]`.

**API:** `POST /process-mining/sessions/start` body `{sources[], date_range, dept_ids[]}` · `GET /process-mining/sessions/{id}/findings` · `POST .../findings/{id}/translate-to-workflow` (sinh `source='process_mining_discovered'` mig 053) · 10 connector register endpoints.

**States:** Empty chưa connect → wizard · Loading mining ETA · Empty no findings · Error PII redact fail · Permission V xem result / O+M discover / **STU-01 Mode 2** · Consent gate `data_residency_strict=true` block external.

**AC checklist:** Maps to US-C1/C2/C3/C4 (URD §3 UR-C). Consent gate NFR-PR-08.

---

## P2-31 Industry Template Library (NEW)

**Route:** `/p2/templates/industries` · **URD US-ID:** (mới — chưa formal US, link CR-0011) · **Permission:** VIEWER+ xem. "Bootstrap" CTA MANAGER+ only.

**Component tree:**
```
<IndustryLibraryPage>
├── <FilterBar />                         # search + seeded-only toggle + pricing plan
├── <IndustryGrid>
│   └── <IndustryCard active|deferred> × 8
│       # icon + name + VN name + 6 dept · 15 wf · 8 KPI · suggested_plan + chip "Đang dùng" / "Sắp có Phase 3"
├── <IndustryDetailDrawer>
│   ├── <DepartmentList />
│   ├── <WorkflowList />
│   ├── <KpiList />
│   └── <DataSchemaList />
└── <BootstrapNotifyForm />               # deferred industry: "Đăng ký nhận thông báo"
```

**State:** Server `['industries']` 8 cards · `['industry-detail', id]` lazy · `['bootstrap-status', enterpriseId]`.

**API:** `GET /industries` · `GET /industries/{id}` · `GET /enterprises/{id}/bootstrap-status` · `POST /industries/{id}/notify-when-available`.

**States:** Loading skeleton · Empty network fail · Permission VIEWER xem / MANAGER+ click Bootstrap · Deferred industry click → notify form.

---

## P2-32 Bootstrap Preview (NEW)

**Route:** `/p2/onboarding/bootstrap-preview` · **URD US-ID:** US-A3 (extension) · **Permission:** MANAGER+ only.

**Component tree:**
```
<BootstrapPreviewPage>
├── <HeaderSummary />                     # Industry name + counts (X depts + Y wf + Z KPI)
├── <PreviewGrid>
│   ├── <PreviewSection title="Phòng ban" entities=depts />     # checkbox uncheck cho TUỲ CHỌN
│   ├── <PreviewSection title="Workflow" entities=workflows />
│   ├── <PreviewSection title="KPI" entities=kpis />
│   └── <PreviewSection title="Data schema" entities=schemas />
├── <SkipOptionalToggle />
├── <DestructiveWarningBanner />          # "Sau khi tạo, không bootstrap lại được trừ khi force=true"
├── <ConfirmModal step={1 | 2}>           # 2-step type-to-confirm
│   ├── <Modal1 title="Xác nhận hành động" />
│   └── <Modal2 title="Gõ tên doanh nghiệp" />  # type-to-confirm
└── <ActionFooter>
```

**State:** Local `selectedDeptSkips[]`, `confirmStep` (0|1|2), `typedEnterpriseName`. Server `['bootstrap-preview']` invalidate khi deptSkips change.

**API:** `POST /enterprises/{id}/bootstrap-from-industry?dry_run=true` body `{industry_id, dept_keys_to_skip[]}` · `POST .../?dry_run=false` (final) · `GET /industry-data-schema-templates/{schema_id}/sample-file`.

**States:** Loading dry-run · Already bootstrapped 409 modal · Permission M+ only · Error industry seed thiếu · Confirm modal 1/2 ESC=đóng · Confirm modal 2/2 enterprise name match unlock CTA · Success redirect P2-03.

---

## P2-33 CS Ticket Inbox & Triage ⭐ NEW

**Route:** `/p2/cs/inbox` · **URD US-ID:** US-CS-1 (URD v2.1 §3 UR-CS) · **Permission:** OPERATOR+ với claim `triage_cs_tickets` (auto-grant nếu dept=CS).

**Mapping workflow:** D.1 Ticket Triage (feature-workflows.html § Vertical D).

**Component tree:**
```
<CsInboxPage>
├── <FilterBar>                           # status (open/pending/resolved) · priority · channel · assignee · SLA breach
├── <SavedViewsSwitcher />                # "My queue" · "Unassigned" · "High priority" · "SLA breach risk"
├── <TicketTable virtualized>
│   ├── <TicketRow>
│   │   ├── <ChannelBadge />              # email/zalo/web-form/phone-log
│   │   ├── <PriorityChip />              # AI-classified
│   │   ├── <SlaTimer />                  # countdown to breach
│   │   ├── <AssigneeAvatar />
│   │   └── <QuickActions>                # Assign · Snooze · Resolve · Escalate
│   └── ... × N
├── <BulkActionToolbar visible-on-select />
└── <NewTicketDrawer />                   # manual create
```

**State:** Server `['cs-tickets', filters]` poll 30s · `['cs-saved-views', userId]`. Local `selectedRows`, `activeFilter`, `currentView`.

**API:**
- `GET /cs/tickets?status=&priority=&channel=&assignee=&sla=` — paginated
- `POST /cs/tickets/{id}/assign` body `{assignee_id}`
- `POST /cs/tickets/{id}/snooze` body `{snooze_until}`
- `POST /cs/tickets/{id}/resolve` body `{resolution_note}`
- `POST /cs/tickets/{id}/escalate` body `{escalation_reason, to_role}`
- `POST /cs/tickets/bulk-action` body `{ticket_ids[], action, params}`
- `POST /cs/tickets` body `{channel, customer_id, subject, body, priority?}`
- `GET /cs/saved-views?user_id=` · `POST /cs/saved-views`

**States:**
- Empty: "Inbox sạch — chưa có ticket nào." + minor stats "Tháng này resolved X tickets, avg 4.2h".
- Loading: skeleton 10 rows.
- Error: per-row retry on action fail; full-table retry on list fail.
- Permission: V không thấy quick actions; O thấy Assign/Resolve own; M thấy bulk + escalate.
- SLA breach imminent: red row highlight + alert tone (subtle).
- Permission denied claim: empty state "Bạn chưa được cấp quyền CS Triage. Liên hệ admin."

**AC checklist:** Maps to US-CS-1 (URD v2.1 §3 UR-CS). NFRS §13.3 4-case.

---

## P2-34 CS Ticket Detail ⭐ NEW

**Route:** `/p2/cs/tickets/{id}` · **URD US-ID:** US-CS-2 · **Permission:** OPERATOR+ với claim `triage_cs_tickets`. Reply MANAGER+ approval cho HIGH-risk.

**Mapping workflow:** D.1 + D.2 (Ticket Triage → SLA Escalation).

**Component tree:**
```
<CsTicketDetailPage>
├── <TicketHeader>                        # subject + priority + SLA timer + assignee + channel
├── <CustomerSidebar>                     # 360 view: history + LTV + churn risk + last contact
│   └── <Link to="P2-37 Churn Save" if churn_risk='HIGH' />
├── <ConversationThread>                  # chronological + agent/customer/system
│   └── <Message channel=email|zalo|web|ai-summary />
├── <ReplyComposer>
│   ├── <AiSuggestedReplyButton />        # generates draft, 3-tuyến reasoning
│   ├── <CannedResponsePicker />          # template snippets
│   └── <SendApprovalGate />              # HIGH-risk: M+ must approve
├── <RightRail>
│   ├── <InternalNotes />                 # mig 072 collab notes
│   ├── <RelatedTickets />                # T-Cube similar past
│   ├── <SuggestedActions />              # AI: "Refund $X" / "Escalate to L2" / "Create churn save case"
│   └── <SlaEscalationPath />             # D.2 workflow visualisation if breach imminent
└── <FooterActions>                       # Resolve · Snooze · Reassign · Merge · Link to insight
```

**State:** Server `['cs-ticket', id]` · `['cs-customer-360', customerId]` · `['cs-related-tickets', customerId]` · `['cs-ai-reply-draft', ticketId]` on demand. Local `composerDraft`, `selectedTemplate`.

**API:**
- `GET /cs/tickets/{id}` — full ticket with conversation
- `GET /enterprises/{eid}/customers/{cid}/360` — customer sidebar
- `POST /cs/tickets/{id}/reply` body `{body, channel}` — sends via connector
- `POST /cs/tickets/{id}/ai-draft-reply` body `{tone}` — returns suggested draft + reasoning
- `POST /cs/tickets/{id}/internal-note` mig 072
- `POST /cs/tickets/{id}/escalate-to-d2` — triggers D.2 SLA Escalation workflow
- `POST /cs/tickets/{id}/link-to-churn-save` — creates P2-37 case

**States:**
- Empty (ticket 404): "Ticket không tồn tại hoặc đã xoá."
- Loading: skeleton thread + customer sidebar.
- Error: per-action toast; thread load fail → retry CTA.
- Permission: VIEWER read-only thread; OPERATOR reply own; MANAGER+ reply any + bulk.
- AI draft confidence < 0.6: badge "AI draft tin cậy thấp, review kỹ trước khi gửi."
- SLA breach: red banner "SLA breach trong 2h — escalate ngay?"
- Customer high churn risk: yellow chip "Khách HIGH risk churn — link sang P2-37 Churn Save?" CTA.

**AC checklist:** Maps to US-CS-2 (URD v2.1 §3 UR-CS).

---

## P2-35 NPS Dashboard & Follow-up ⭐ NEW

**Route:** `/p2/cs/nps` · **URD US-ID:** US-CS-3 · **Permission:** VIEWER+ xem; campaign config MANAGER+.

**Mapping workflow:** D.3 NPS Follow-up.

**Component tree:**
```
<NpsPage>
├── <NpsScorecard>                        # NPS overall + trend + segment breakdown
├── <SurveyTriggerConfig />                # trigger: post-resolution / scheduled / event-based
├── <ResponseTable virtualized>
│   ├── <ResponseRow>
│   │   ├── <NpsScore />                  # 0-10 with color
│   │   ├── <CommentSentiment />          # AI-classified pos/neutral/neg
│   │   ├── <SegmentTags />               # plan / dept / channel
│   │   └── <FollowupStatus />            # auto-replied / awaiting / done
│   └── ...
├── <FollowupRulesEditor>                  # promoter/passive/detractor → action
│   ├── <RuleRow trigger="detractor" />   # → create ticket P2-33 + notify owner
│   ├── <RuleRow trigger="promoter" />    # → request review on Google/FB
│   └── ...
└── <CampaignManager>                      # send survey to cohort
```

**State:** Server `['nps-scorecard', timeRange]` · `['nps-responses', filters]` · `['nps-rules']` · `['nps-campaigns']`. Local `editingRule`, `campaignDraft`.

**API:**
- `GET /cs/nps/scorecard?from=&to=` — aggregated metrics
- `GET /cs/nps/responses?segment=&score=` — paginated
- `POST /cs/nps/rules` body `{trigger, action, condition}` — auto-followup rules
- `POST /cs/nps/campaigns` body `{cohort_filter, survey_template, schedule}` — send campaign
- `GET /cs/nps/responses/{id}/sentiment` — re-classify on demand

**States:**
- Empty (chưa survey nào): "Chưa có response — cài đặt survey trigger đầu tiên." + CTA SurveyTriggerConfig.
- Loading: skeleton scorecard + table.
- Error: per-rule save fail toast; scorecard fail → retry.
- Permission: V xem scorecard + responses; M+ edit rules + campaigns.
- Low response volume (<30): warning "NPS chưa đủ tin cậy thống kê (n<30). Tăng frequency hoặc cohort."

**AC checklist:** Maps to US-CS-3 (URD v2.1 §3 UR-CS).

---

## P2-36 Refund Approval Queue ⭐ NEW

**Route:** `/p2/cs/refunds` · **URD US-ID:** US-CS-4 · **Permission:** OPERATOR+ xem; **approve action MANAGER+ với claim `approve_refund`**.

**Mapping workflow:** D.4 Refund Approval.

**Component tree:**
```
<RefundQueuePage>
├── <ApprovalQueueTable virtualized>
│   ├── <RefundRow>
│   │   ├── <AmountVnd />                 # VND, format
│   │   ├── <PolicyMatchBadge />          # AI-check vs refund policy: AUTO_OK / MANUAL_REVIEW / POLICY_VIOLATION
│   │   ├── <CustomerContext />           # LTV + history (link customer 360)
│   │   ├── <ReasonCategory />            # damaged / late / wrong-item / change-mind
│   │   ├── <RequestedBy />               # agent who initiated
│   │   ├── <DaysWaiting />               # SLA approval timer
│   │   └── <ApprovalActions claim="approve_refund">
│   │       ├── <ApproveBtn />            # → triggers payment-service refund
│   │       ├── <RejectBtn />
│   │       └── <RequestMoreInfoBtn />
│   └── ...
├── <PolicyConfigDrawer />                 # MANAGER+: refund policy thresholds
├── <AuditPanel claim="view_audit_log">    # mig 098 ai_decision_audit cho AI policy match
└── <BulkApprovalDrawer claim="approve_refund">  # bulk only AUTO_OK
```

**State:** Server `['refund-queue', filters]` poll 60s · `['refund-policy']` · `['refund-audit', refundId]`. Local `selectedRows`, `policyDraft`.

**API:**
- `GET /cs/refunds?status=pending` — queue
- `POST /cs/refunds/{id}/approve` body `{note}` — claim `approve_refund` required
- `POST /cs/refunds/{id}/reject` body `{reason_code, note}`
- `POST /cs/refunds/{id}/request-info` body `{message}` — sends to agent who initiated
- `POST /cs/refunds/bulk-approve` body `{refund_ids[]}` — claim + AUTO_OK only
- `GET /cs/refund-policy/{enterpriseId}` · `PATCH .../policy`
- `GET /ai-decision-audit/refund/{id}` — mig 098

**States:**
- Empty queue: "Không có refund đang chờ duyệt 🎉."
- Loading: skeleton 5 rows.
- Error per-action; bulk → partial success report.
- Permission: V không thấy approve buttons; O xem queue; M+ với claim approve.
- Policy violation: red badge + tooltip "Vượt policy limit $X — escalate to BoD or override với reason mandatory."
- Audit trail: timeline of approvers + AI recommendation + final action.

**AC checklist:** Maps to US-CS-4 (URD v2.1 §3 UR-CS). K-6 audit per approval mig 098.

---

## P2-37 Churn Save Workspace ⭐ NEW

**Route:** `/p2/cs/churn-save` · **URD US-ID:** US-CS-5 · **Permission:** OPERATOR+ với claim `run_churn_save_action` (auto-grant dept=CS).

**Mapping workflow:** D.5 Churn Save.

**Component tree:**
```
<ChurnSavePage>
├── <PortfolioFilters />                  # plan · health · risk score · last action
├── <ChurnRiskGrid>                       # card view, kanban-style
│   ├── <ChurnRiskColumn risk="CRITICAL" />  # imminent churn
│   ├── <ChurnRiskColumn risk="HIGH" />
│   ├── <ChurnRiskColumn risk="MEDIUM" />
│   └── <ChurnRiskColumn risk="LOW" />
│   └── <CustomerCard>
│       ├── <RiskScoreBadge />
│       ├── <PrimaryRiskFactor />         # AI SHAP top-1: "Usage drop 60% in last 14d"
│       ├── <NovImpact />                 # estimated NOV at risk (VND)
│       ├── <SuggestedAction />           # discount / training / personal call / escalate to AE
│       └── <ActionPanel claim="run_churn_save_action">
│           ├── <RunActionBtn />          # opens playbook drawer
│           └── <AssignToAeBtn />
├── <PlaybookDrawer>                       # intervention templates per archetype
├── <InterventionHistoryPanel />           # past 30d actions + effectiveness
└── <EffectivenessSummary />               # before/after retention by intervention type
```

**State:** Server `['churn-portfolio', filters]` poll 5m · `['playbooks']` · `['intervention-history', customerId]` on drawer · `['effectiveness-summary']`. Local `selectedCustomer`, `selectedPlaybook`.

**API:**
- `GET /cs/churn-portfolio?risk=&plan=` — kanban data
- `GET /cs/playbooks` — intervention templates
- `POST /cs/churn-save/run-action` body `{customer_id, playbook_id, custom_message?}` — claim required
- `POST /cs/churn-save/assign-to-ae` body `{customer_id, ae_id, urgency}`
- `GET /cs/churn-save/intervention-history?customer_id=`
- `GET /cs/churn-save/effectiveness-summary?from=&to=`
- Links to Adoption Intelligence (EPIC-13) signals via `GET /adoption/signals?customer_id=`

**States:**
- Empty (no customers at risk): "Portfolio sạch — 0 khách HIGH risk 🎉."
- Loading: skeleton kanban.
- Error per-action.
- Permission: V xem portfolio; O+claim run action; M+ assign to AE + edit playbooks.
- Intervention in flight: card chip "Đang chạy action X — kết quả sau 14d."
- Effectiveness low (<20% recovery): yellow banner "Playbook X effectiveness thấp — review playbook?"

**AC checklist:** Maps to US-CS-5 (URD v2.1 §3 UR-CS). Adoption Intelligence integration EPIC-13.

---

## Cross-cutting validation rules

Per `VALIDATION_RULES.md`. Tất cả form fields validated qua react-hook-form + zod. Inline error message từ `MESSAGE_DEFINITIONS.md` lookup theo error code.

**Common field constraints:**
- `enterprise_id`, `workflow_id`, etc. → UUID v4 pattern + path param validation
- `discount_pct`, `margin_pct` → NUMERIC(5,4) 0..1 range (CLAUDE.md K-9)
- VND amounts → integer ≥0, max 1 trillion VND
- Email → RFC 5322, max 254 chars
- VN phone → `+84` or `0` prefix, 9-10 digits after (vn_phone normalizer in BE mig 086)
- File upload → max 100MB per file, magic-byte verified per `MESSAGE_DEFINITIONS.md` SYS-ERR-006/007

---

## Permission claims reference

Per JWT `permissions[]` claim. Full table xem **NFRS v1.1 §5.bis**. Highlights:

| Claim | Grants access to |
|---|---|
| `view_audit_log` | P2-21 AI Decision Log standalone, P2-36 audit panel |
| `view_observability` | P1-13 Platform Health (SRE only) |
| `manage_dlq` | P5-04 DLQ Console |
| `view_mcp` | P5-02 MCP Console (STU-01 Studio Analyst) |
| `review_guardrails` | P5-01 Guardrails Review |
| `platform_admin` | All P1 screens |
| `approve_workflow_promotion` | P2-27 Mode 2 "Promote B" button |
| `triage_cs_tickets` ⭐ | P2-33, P2-34 |
| `approve_refund` ⭐ | P2-36 approve action |
| `run_churn_save_action` ⭐ | P2-37 action panel |

**Default claim grants per role** (auto-grant logic in BE auth-service):
- VIEWER: read-only on Business IA
- OPERATOR: + upload to inbox; if dept=CS → +`triage_cs_tickets`, +`run_churn_save_action`
- ANALYST: + workflow customize advanced mode, model retrain
- MANAGER: + publish workflow, bulk user mgmt, bootstrap industry, dismiss insights permanently, +`approve_workflow_promotion`; if dept=CS → +`approve_refund`
- **STU-01** (Studio Analyst, alias STUDIO_ANALYST in code): cross-tenant scope per assigned enterprises; +`view_mcp`

---

## Implementation phasing (suggested — updated for 18 priority)

**Phase A (3 weeks):**
- Week 1: Shared / Layout / Auth / Error handling / Accessibility / OpenTelemetry baseline
- Week 2: P2-31 + P2-32 + P2-02 (Industry-first bootstrap)
- Week 3: P2-03 Dashboard + P2-04 Org (incl. GAP-01 closeout View 2)

**Phase B (3 weeks):**
- Week 4: P2-11 Upload 2-mode + P2-15 Results context-aware
- Week 5: P2-20 Insight Detail
- Week 6: P2-26 Workflow Builder Simple mode only (Advanced + Developer defer)

**Phase C (3 weeks):**
- Week 7: P2-27 Test Run mode (A/B Parallel-Run defer)
- Week 8: P2-28 Discovery mode (Analyst view defer)
- Week 9: **CS vertical — P2-33 CS Inbox + P2-34 CS Ticket Detail**

**Phase D (2 weeks):**
- Week 10: **P2-35 NPS + P2-36 Refund Queue**
- Week 11: **P2-37 Churn Save Workspace** + integration testing

Total ~**11 weeks** for 18 priority (vs 8 weeks v1.0 cho 11+2 priority). Cộng thêm 3 tuần cho 5 CS screens.

---

## Test Strategy (full pyramid)

| Layer | Tool | Scope | Coverage target |
|---|---|---|---|
| Unit | Vitest | lib/, hooks/, utils/, zod schemas | ≥70% (NFR-M-01 P1) → ≥85% P3 |
| Integration | Testing Library + MSW | Components with API + state | All 18 priority screens render + key interactions |
| E2E | Playwright | Happy paths + critical permission flows | 18 priority happy + 5 permission-denied paths |
| Accessibility | `axe-core/playwright` | All 18 priority | Block release if violations ≥ MODERATE |
| Visual regression | Playwright snapshot | 18 priority main states | New + diff approval workflow |
| Performance | Lighthouse CI | P2-03 Dashboard + P2-20 Insight Detail | LCP <2.5s, CLS <0.1, INP <200ms |

**Negative scenarios** (per NFRS §13.3): mọi US trong URD v2.1 phải có test cho 4 case Happy/Validation/Permission/Dependency. Coverage matrix tracked trong `docs/uat/COVERAGE_MATRIX.md`.

---

## Open questions for FE team (rút từ 5 → 3)

1. **i18n loading strategy:** SSR per locale vs client-fetch on language switch? (Recommendation chính thức trong FE kickoff.)
2. **Component library deep customisation:** shadcn/ui base với Tailwind chốt rồi, nhưng cần xác nhận có cần fork một số shadcn components cho design template `D:\Kaori Document\frontend template\` không?
3. **CS vertical screens coordination:** P2-33..P2-37 spec dựa trên 5 CS workflow D.1-D.5; cần PO + CS Lead confirm content per screen (e.g., NPS scorecard metrics specific) trong kickoff trước khi start Week 9.

Đã chốt sẵn (không còn defer FE meeting):
- ✅ Component library: shadcn/ui + Tailwind
- ✅ Local state: Zustand
- ✅ Real-time: polling 1-30s tuỳ tốc độ; WebSocket Phase 3
- ✅ Test pyramid: full Unit + Integration + E2E + a11y + visual + perf

---

## Changelog v1.0 → v1.1

| Item | Change |
|---|---|
| Source of truth dòng | "72 màn" → "**77 màn · 6 portal P1-P6**, baseline 2026-05-21 Round 3" |
| Audience | "Không cover P1/P3/P4/Billing/Shared" → "Không cover P1/P3/P4/**P5/P6**" |
| Scope | +5 CS screens (P2-33..P2-37), tổng 18 priority |
| §Shared/Common | +§Permission Claims, +§Accessibility WCAG 2.1 AA, +§Mobile Responsiveness, +§Observability OpenTelemetry |
| Top Nav | +Customer Service section (5 items, claim-gated) |
| P2-04 | Clarify Org Tree = GAP-01 closeout, BE shipped |
| P2-11 | "Mode 3 Pipeline Wizard (legacy)" → "(standalone — Phase 1 flow, vẫn duy trì; không phải deprecated)" |
| P2-26 | Add reference `kaori-shared-glossary.html § Workflow Card (7-field SSOT)` |
| P2-28 | "STUDIO_ANALYST" → "**STU-01 (alias STUDIO_ANALYST in code)**"; sources 8 → 10 |
| 5 NEW screens | P2-33 CS Ticket Inbox · P2-34 CS Ticket Detail · P2-35 NPS Dashboard · P2-36 Refund Queue · P2-37 Churn Save |
| Permission claims | +3 new claims (`triage_cs_tickets`, `approve_refund`, `run_churn_save_action`); link tới NFRS v1.1 §5.bis |
| Phasing | 8 weeks → 11 weeks for 18 priority |
| Test strategy | Either-or → full pyramid (6 layer) |
| Open Qs | 5 → 3 (chốt 2 in spec: component library shadcn, Zustand local state) |
| Per-screen | +URD US-ID traceback per screen |
| Phase token | Clarify "Phase 2.8" = sprint code thuộc BA Phase 2 |

---

*Document version 1.1 · 2026-05-21 · supersedes v1.0 (2026-05-20 EOD3).*
