# Kaori AI — Enterprise 90-Day Deployment Playbook v3.0
Sổ tay triển khai 90 ngày toàn diện cho khách hàng doanh nghiệp
Phiên bản: v3.0 (Unified — hợp nhất Playbook v1 + Critical Gaps Supplement v2 + framework Comprehensive Visibility/Incremental Change) Phát hành: Tháng 5 / 2026 Audience: CSM team · Implementation Engineer · Sales AE · Product · Customer’s executive sponsor + project lead Mục tiêu: Sau 90 ngày, doanh nghiệp khách hàng đi từ “vừa ký HĐ” đến “self-sufficient với Kaori AI” — đo bằng Health Score ≥80, ROI proven, ≥1 workflow tối ưu thành công, customer’s data team có quyền truy cập Studio (theo archetype). Triết lý: Chuyển đổi số là quá trình lặp đi lặp lại, không thay thế đột ngột. Quan sát toàn diện (comprehensive visibility), thay đổi từng bước (incremental change).

## Mục lục
Phần 0. Tổng quan & Triết lý — vision, primitives, frameworks, phases
Phần 1. PRE-LAUNCH (D-7 → D0) — Sales handoff, discovery, archetype, wedge selection
Phần 2. WEEK 1 (D1-7) — Foundation: workspace, departments, first upload
Phần 3. WEEK 2-4 (D8-30) — Activation: pipeline E2E, first insights, first action
Phần 4. WEEK 5-8 (D31-60) — Workflow phase: mapping, AI optimization, mid-review
Phần 5. WEEK 9-12 (D61-90) — Handover: parallel run, Studio, final review
Phần 6. Domain-Specific DB Schemas + Wedge Canonical
Phần 7. AI Quality & Calibration Framework
Phần 8. Workflow Policy & Governance Engine
Phần 9. Pricing-Based Quotas Matrix
Phần 10. Studio Collaboration with Customer Data Team
Phần 11. Data Volume Management & Sync Architecture
Phần 12. Enterprise Health State Machine
Phần 13. Economic Model & Cost-to-Serve
Phần 14. Special Domain Supplements (Banking, Healthcare, Government)
Phần 15. Templates Library
Phần 16. Critical Success Factors & Anti-patterns

# Phần 0. Tổng quan & Triết lý
## 0.1 Sản phẩm & vision
Kaori AI là hệ điều hành quyết định cho doanh nghiệp — biến dữ liệu phân tán thành quyết định nhất quán thông qua 5 cơ chế:
Data normalization — Bronze→Silver→Gold pipeline
Workflow observability — map toàn bộ workflow của doanh nghiệp
AI-assisted decisioning — Insights Engine 3-tuyến với confidence
Human-in-loop optimization — AI gợi ý, human quyết định
Organizational learning loops — feedback từ outcome → model retrain
Kaori KHÔNG phải BI tool, không phải dashboard. Là platform cho organizational learning — doanh nghiệp ngày càng thông minh theo thời gian khi data + decision + outcome khép kín lại.
## 0.2 7 Core Primitives — Vocabulary của hệ thống
Mọi feature, mọi service, mọi conversation với khách phải express bằng 7 primitives này. Không invent thuật ngữ mới.
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   ENTITY ─────► EVENT ─────► WORKFLOW ─────► DECISION            │
│      │            │              │              │                │
│      └────────────┴──────┬───────┴──────────────┘                │
│                          ↓                                       │
│                       INSIGHT ──► ACTION ──► OUTCOME             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

| # | Primitive | Định nghĩa | Identity |
|---|---|---|---|
| 1 | ENTITY | Bất kỳ thứ gì Kaori observe — customer, product, transaction, employee, asset | tenant_id + entity_type + external_id |
| 2 | EVENT | Cái gì đó xảy ra với entity, có timestamp | event_id (UUID, immutable) |
| 3 | WORKFLOW | Sequence of steps có branches tạo ra outcomes | workflow_id + version |
| 4 | DECISION | 1 phán đoán cụ thể từ AI hoặc human | decision_id + confidence + audit |
| 5 | INSIGHT | Pattern truyền đạt được — format “3-tuyến” (chuyện gì / tại sao / nên làm gì) | insight_id + citations |
| 6 | ACTION | Bước thực tế làm dựa trên decision/insight | action_id + performed_by + evidence |
| 7 | OUTCOME | Kết quả đo được sau action | outcome_id + attributed_to action_id |

The Loop:
ENTITY emits EVENTS → trigger WORKFLOWS → make DECISIONS 
→ surface as INSIGHTS → prompt humans to take ACTIONS 
→ produce OUTCOMES → update EVENTS → ... model retrains
Đây là organizational learning loop — đặc trưng của Kaori vs các BI tools.
## 0.3 Comprehensive Visibility, Incremental Change
Triết lý quan trọng nhất: Khi triển khai cho 1 doanh nghiệp, có 4 dimension QUYẾT ĐỊNH ĐỘC LẬP:

| Dimension | Default position | Lý do |
|---|---|---|
| Data ingestion (data nào lên platform) | 80% Comprehensive | Value của Kaori = connection between domains. Không thể thấy connection nếu chỉ ingest 1 silo |
| Workflow visibility (workflow nào được map) | 90% Comprehensive | Không optimize được nếu không thấy dependency. Workflow A output có thể là input của B |
| Active intervention (workflow nào AI ĐANG optimize) | 90% Wedge | Trust + risk + org change capacity là finite. Một quý đổi 1 workflow |
| User adoption (phòng ban nào dùng) | 60% Wedge | Champion department lead, others follow theo proof. Tùy archetype |

Tóm gọn: Visibility comprehensive. Change incremental. Map toàn bộ workflow ≠ thay đổi toàn bộ workflow. Hai cái khác nhau.
Implications: - Khi sales: không pitch “Kaori transform toàn bộ doanh nghiệp 90 ngày”. Pitch: “90 ngày Kaori map toàn bộ doanh nghiệp + thay đổi 1-2 workflow critical, prove ROI, expand từng quý” - Khi pricing: quota workflow runs/active, không hạn chế workflow mapped. Customer upload tất cả lên free phần map, chỉ trả tiền cho thứ AI active optimize - Khi engineering: build platform-grade từ đầu (Bronze/Silver/Gold/KG/Memory đủ chuẩn cross-domain). Không build “thin wrapper” cho 1 wedge — sẽ stuck mãi mãi. “Tunnel vision in marketing, panoramic in engineering”
## 0.4 5 Customer Archetypes — Adjusted Playbook
Cùng 1 playbook 90 ngày KHÔNG fit mọi customer. Phải segment theo archetype.

| # | Archetype | Profile | Critical need | Wedge intervention Y1 |
|---|---|---|---|---|
| 1 | Data-Chaotic SME | <50 staff, no data team, Excel-driven | Heavy guidance, hand-holding | 1 wedge max |
| 2 | Ops-Driven Mid-market | 50-200 staff, ops manager nhưng no data eng | Workflow-first | 1-2 wedges |
| 3 | Data-Curious Growing | 100-500 staff, 1-2 data analysts | Self-service unlock | 2-3 wedges parallel OK |
| 4 | Data-Mature Enterprise | 500+ staff, full data team | Studio-first, integration-heavy | 3-5 wedges |
| 5 | Compliance-Heavy Regulated | Bank, hospital, insurance — bất kỳ size | Governance-first, audit-heavy | 1 wedge per audit cycle |

Detection: Discovery questionnaire 5 câu (xem Phần 1.3) classify customer trong 30 phút.
## 0.5 4 Phase Structure (90 days)
W1            W2-4          W5-8         W9-12
═══════      ═════════     ═════════    ═════════
FOUNDATION   ACTIVATION    WORKFLOW     HANDOVER
ONBOARDING   ACTIVATING    PROVING      → HEALTHY
═══════      ═════════     ═════════    ═════════
Setup        Pipeline      Map+         Parallel
Workspace    Bronze→       Optimize     Run + 
Departments  Silver→Gold   Workflows    Studio
Upload       First         AI Insight   Final
First Data   Insights      Mid Review   Review

| Phase | Tuần | Mục tiêu cuối phase | Health state | Critical KPI |
|---|---|---|---|---|
| Foundation | W1 | Workspace ready, ≥1 department có data | ONBOARDING → ACTIVATING | Pipeline run thành công lần đầu |
| Activation | W2-W4 | Bronze→Silver→Gold E2E, ≥1 insight per dept | ACTIVATING → PROVING | First “Đã xử lý” action |
| Workflow | W5-W8 | ≥3 workflows mapped, AI suggest ≥1 optimization | PROVING → EXPANDING | ≥10 actions/tháng từ AI insight |
| Handover | W9-W12 | Studio activated (per archetype), ≥1 workflow mới chạy parallel, QBR cadence | EXPANDING → HEALTHY | Health score ≥80 sustained 14d |

Note: Timeline trên là default cho Archetype 2-3. Archetype 1 (chaotic SME) compress phase 4 vào tháng 4-5. Archetype 4 (mature enterprise) accelerate phase 1-2. Xem Phần 1.3 để adjust.
## 0.6 12 Milestone Gates
Mỗi milestone là gate — không pass thì không đi tiếp. Failure → invoke rescue playbook.

| M | Day | Gate criteria | Owner | Failure action |
|---|---|---|---|---|
| M1 | D1 | Workspace + key + credentials sent, customer logged in | CSM | Re-send, schedule call D2 |
| M2 | D3 | ≥1 department folder + ≥1 user invited per dept | CSM | Onboarding call D4 |
| M3 | D5 | ≥1 file uploaded to Bronze, schema detected | Customer + CSM | Manual data import D6 |
| M4 | D7 | Bronze data passed quality (≤30% null) | Implementation Eng | Data engineering session |
| M5 | D14 | Cleaning rules applied, ≥80% records pass | Implementation Eng | Custom cleaning workshop |
| M6 | D21 | ≥1 insight 3-tuyến với confidence ≥0.6 | AI System | Lower threshold + manual review |
| M7 | D30 | Customer click “Đã xử lý” ≥1 lần | Customer + CSM | Personal coaching call |
| M8 | D45 | ≥3 current workflows mapped | Customer | CSM hands-on workshop |
| M9 | D60 | AI suggests ≥1 optimization confidence ≥0.7 | AI System | Manual analysis fallback |
| M10 | D60 | Mid-cycle review meeting completed | CSM + AE | Reschedule, executive escalation |
| M11 | D75 | Parallel workflow live, metrics collected | Implementation + Customer | Roll back to old |
| M12 | D90 | QBR done, plan for next 90d agreed | CSM + Sales | Extension to PROVING phase |

## 0.7 Stakeholder Matrix

| Role | Bên Kaori | Bên Khách | Total time over 90d |
|---|---|---|---|
| Executive sponsor | AE | CMO/CEO/COO | 4 hours (3 reviews) |
| Day-to-day owner | CSM | Project lead (PM/CTO) | 30-40 hours |
| Technical implementation | Implementation Engineer | Data team / IT lead | 20-40h phase 1, 10h phase 2-3 |
| End user | (none) | Department heads + analysts | Depends on dept |
| Studio (Phase 2+) | Studio Analyst (optional) | Customer data eng/scientist | 10-20h from D75 (or earlier per archetype) |


# Phần 1. PRE-LAUNCH (D-7 → D0)
Mục tiêu: Khi customer login D1 lần đầu, mọi thứ phải sẵn sàng. Discovery sai → deployment fail.
## 1.1 Sales-to-CSM Handoff Checklist (D-7)

| Hạng mục | Người chuẩn bị | Done? |
|---|---|---|
| Customer profile (size, industry, vertical) | AE | ☐ |
| Pain points đã agree giải quyết | AE | ☐ |
| Plan đã chọn (PILOT/BASIC/MID/MAX) | AE | ☐ |
| Departments dự kiến cần setup (số lượng + tên) | AE từ discovery | ☐ |
| Data sources có sẵn (POS/ERP/CRM/Excel?) | AE | ☐ |
| Volume estimation (records, files/tháng) | AE | ☐ |
| Critical workflow tâm điểm (vd: chống churn, audit financial) | AE | ☐ |
| Executive sponsor info (tên, role, email) | AE | ☐ |
| Pilot success criteria explicit | AE + customer | ☐ |
| Data residency requirement (VN only? cross-border OK?) | AE | ☐ |
| Archetype classification (1-5) | AE + CSM | ☐ |
| Wedge canonical chọn | AE + Product | ☐ |

## 1.2 Discovery Questionnaire (gửi customer trước D1)
Phần A — Tổ chức: - Số phòng ban dự định setup - Mỗi phòng ban có bao nhiêu user - Ai là MANAGER mỗi phòng ban (mỗi phòng ≥1)
Phần B — Data: - Hệ thống đang dùng (chọn từ list: KiotViet, Sapo, MISA, HubSpot, Excel, …) - Format export (CSV, Excel, API) - Volume: ~bao nhiêu records/tháng/phòng ban - Sensitivity tag per source (PII/financial/medical?)
Phần C — Workflow: - 3-5 workflow quan trọng nhất hiện tại (mô tả 2-3 câu) - Pain points lớn nhất với workflow đó - Mong muốn AI hỗ trợ gì (cảnh báo? gợi ý? automation?)
Phần D — Success metrics: - Định nghĩa thành công với customer (vd: “phát hiện 100 khách HIGH risk/30 ngày”, “giảm thời gian báo cáo từ 2 tuần xuống 2 ngày”)
## 1.3 Archetype Classification (5 câu hỏi quyết định 90-day playbook)
Q1: Số nhân viên chính thức?
  <50           → Likely Archetype 1 (Data-Chaotic SME)
  50-200        → Likely Archetype 2 (Ops-Driven Mid-market)
  200-500       → Likely Archetype 3 (Data-Curious Growing)
  500+          → Likely Archetype 4

Q2: Đã có data analyst/engineer chuyên trách?
  Không         → 1 or 2
  1-2 người    → 3
  Team 3+ người → 4 or 5

Q3: Hệ thống IT hiện tại?
  Excel/manual              → 1
  POS/ERP basic            → 2
  Multiple integrated systems → 3 or 4
  Full data warehouse + BI  → 4

Q4: Industry?
  Bank / Insurance / Healthcare / Government → 5 (regardless other answers)
  
Q5: Compliance constraint nào (data residency, audit, regulation)?
  Strict   → upgrade archetype to 5
  Standard → keep current
Output: 1 archetype label → CSM uses corresponding playbook variant.
### Per-Archetype Adjusted Timeline

| Phase | Default (Arch 2-3) | Arch 1 (Chaotic SME) | Arch 4 (Enterprise) | Arch 5 (Regulated) |
|---|---|---|---|---|
| Foundation | D1-7 | D1-14 (extended workshops) | D1-5 (compressed) | D1-21 (legal review) |
| Activation | D8-30 | D15-45 (curated insights) | D6-21 (accelerated) | D22-45 (sandbox-only first) |
| Workflow | D31-60 | D46-75 (formalize first time) | D22-50 (parallel multiple) | D46-75 (approval-heavy) |
| Handover | D61-90 | D76-90 (Studio delayed Q2) | D51-90 (Studio D14!) | D76-90 (compliance audit) |

## 1.4 Wedge Canonical Selection
Quy tắc: Mỗi domain có 1 wedge default. Sales không phải nghĩ ra. Kaori đề xuất.

| Domain | Wedge canonical (start here) | Why this wedge | Expand sequence |
|---|---|---|---|
| Retail / F&B | Churn retention (HIGH risk customers) | Highest LTV impact, fastest ROI proof, dễ measure | Churn → CLV → Cross-sell → Inventory → Campaign |
| Finance / Banking | Credit risk scoring OR Fraud detection | Regulatory mandatory + clear ROI | Risk → Collection → Cross-sell → Profitability |
| Logistics | On-time delivery prediction | Operational excellence, customer-facing | OTD → Route → Carrier scoring → Demand |
| Manufacturing | Defect prediction OR Predictive maintenance | Direct margin impact | Quality → Maintenance → OEE → Supply chain |
| E-commerce | Cart abandonment recovery | Quick win, measurable, low risk | Cart → Browsing → Repeat → CAC |
| Education | Dropout risk prediction | Mission-critical, data available | Dropout → Engagement → Tuition → Course quality |
| Real Estate | Lead scoring | Sales cycle long, every win matters | Lead → Listing → Time-on-market → Price |
| Healthcare | No-show prediction OR Readmission risk | Operational + patient outcome | No-show → Readmission → Resource utilization |

Rule: Sales pitch → wedge specific. Onboarding → comprehensive visibility. Active changes → 1 wedge / 90 ngày Phase 1.
## 1.5 Onboarding Kit Preparation (D-3 → D-1)
CSM chuẩn bị folder: - Welcome PDF (10 trang) — giới thiệu Kaori, key concepts (Medallion, 3-tuyến insights, North Star), expectations 90 ngày - Video onboarding 15 phút (recorded by Product team) - D1 agenda (60 phút call) - Calendar invite — recurring milestones (D1, D3, D7, D14, D30, D60, D90) - Slack/Email channel created với customer team - Wedge brief — 1-pager về wedge đã chọn + expected outcome 90 ngày - Archetype-specific FAQ — 5-10 questions phổ biến cho archetype này

# Phần 2. WEEK 1 — Foundation (D1-7)

> **Onboarding order revised 2026-05-17 (ADR-0022):** corporate hierarchy first → smallest department → workflow design → workflow-step-aware data upload. Original v3.0 order (`workspace → flat depts → upload → validate`) is now archived; org-first is the default for Mid-Enterprise + Conglomerate archetypes. "Simple SME" archetype retains a flattened path via the `single-enterprise mode` toggle in §2.2.

**Goal:** Workspace running. **Corporate hierarchy mapped** (group → divisions → subsidiaries → enterprise units). **≥1 workflow designed for smallest dept** (template-driven from mig 069 catalog). **≥1 data file uploaded INTO a workflow step** (not free-form). Bronze layer alive only for the step that needed it.

```
D1    Workspace + first login                    (unchanged from v3.0)
D2    Corporate hierarchy setup (group → div → sub → enterprise)
D3    Drill down — departments + sub-departments per smallest unit
D4-5  Workflow design for ONE smallest department first
        (pick from mig 069 catalog filtered by industry_vertical)
D6    Workflow-step-aware data upload
        (each step's required_document_types triggers an upload prompt)
D7    Bronze + Silver landing validation per workflow step + quality scorecard
```
## 2.1 D1 — Workspace Creation & First Login
### Auto + manual actions:
Step 1 (auto, sau khi customer ký):
  - Generate workspace_id (UUID)
  - Generate KAORI-XXXX-XXXX private key (16-char hex, hashed SHA-256 in DB)
  - Allocate quota theo plan (xem Phần 9)
  - Send credentials via 2 channels:
    a) Email: username + temp password
    b) SMS/Zalo: KAORI-XXXX key (separate channel for security)
  - Schedule D1 onboarding call

Step 2 (manual by CSM, D1 9am):
  - Send welcome email
  - Confirm credentials received
  - 60-min onboarding call:
    * Walk through P2 dashboard
    * Show wizard 5 bước (demo)
    * Confirm department list (từ discovery)
    * Set expectation 90-day plan
    * **Brief về wedge canonical** — "Trong 90 ngày, focus chính sẽ là [wedge]. Còn lại sẽ map để observe."
### Customer-side actions D1:
Login lần đầu → buộc đổi password
Verify email + phone
Optional: enable MFA (recommended)
Customize branding (logo, color, theme) — Module 2.1
Confirm/edit department list
### M1 Gate (end of D1):
☐ Customer logged in
☐ Password đổi
☐ Branding setup (≥logo)
☐ Department list confirmed
☐ Wedge focus agreed verbal
## 2.2 D2 — Corporate Hierarchy Setup

Triết lý mới (ADR-0022): khách hàng Tập đoàn không có "danh sách phòng ban phẳng" — họ có **sơ đồ phả hệ tổ chức** (group → divisions → subsidiaries → enterprise). Map hierarchy TRƯỚC; phòng ban là leaf của tree, không phải root.

### Archetype branching

**Conglomerate / Mid-Enterprise:** dùng full corporate tree wizard (theo Vingroup demo mig 055-057). Group level → divisions → subsidiaries → enterprise root.

**Simple SME (≤ 30 nhân viên, 1 văn phòng):** dùng `single-enterprise mode` toggle ở D2 — bỏ qua group/division/subsidiary, đi thẳng vào D3 dept setup. Toggle này được Discovery Questionnaire (§1.2) capture trước, không hỏi lại customer.

### Corporate tree wizard (Conglomerate path)

```
/p2/organization/hierarchy
  → "Tạo Corporate Group"  (level 1)
    Form:
      - Tên group (e.g., "Vingroup", "FPT Corporation")
      - Quốc gia trụ sở
      - Industry verticals chính (multi-select từ mig 069 catalog:
        general / retail / manufacturing / fintech / logistics /
        healthcare / fmcg / saas)
      - CEO/Chairman name (ABAC seed)
    → Submit → corporate_groups row created
  
  → "Thêm Division"  (level 2 — repeat per division)
    Form:
      - Tên division (e.g., "VinFast", "VinHomes", "VinMart")
      - Group parent (auto)
      - Industry vertical (1 per division — narrows template catalog later)
      - Division Director (ABAC seed)
    → Submit → business_divisions row
  
  → "Thêm Subsidiary / Enterprise"  (level 3-4 — repeat per subsidiary)
    Form:
      - Tên subsidiary (e.g., "VinFast Vietnam", "VinFast Singapore")
      - Division parent (auto)
      - Country
      - Industry vertical (inherit from division by default)
    → Submit → enterprises row with FK chain (group_id, division_id)
```

Cross-link option: khi 1 enterprise có **chéo division** (vd. VinTechAcademy thuộc VinTech division nhưng cũng serve VinFast operations) — dùng `workflow_cross_links` (mig 057) để tag relationship sau D6.

### M2a Gate (end of D2):
☐ Corporate group + ≥1 division + ≥1 enterprise unit created
☐ Industry vertical(s) tagged per division
☐ Manager/Director ABAC seeds assigned

## 2.3 D3 — Department Drill-down (smallest unit first)

Triết lý: trong 1 enterprise lớn (vd "VinFast Vietnam"), có 5-50 phòng ban. Đừng map hết — **pick 1 phòng ban nhỏ nhất + đau nhất** (wedge canonical từ §1.4) làm điểm xuất phát. Các phòng còn lại defer đến Week 3-4.

### Why smallest-dept-first?

- Cognitive load: customer focus 1 việc, làm cho thật tốt → confidence build sớm.
- Wedge alignment: phòng ban đau nhất = ROI demonstrable ngay D14 (first insight gate M5).
- Workflow tractability: smallest dept thường có 1-3 quy trình core → fit hoàn toàn 5-card template từ mig 069.

### Department setup flow (per smallest enterprise unit)

```
/p2/enterprises/{enterprise_id}/departments
  → "Thêm phòng ban"  (focus on smallest dept first)
    Form:
      - Tên phòng ban (e.g., "Marketing Performance", "Sales Lead Qualification",
                       "Quality Control Line 3")
      - Mô tả ngắn (1-2 câu — nỗi đau hiện tại)
      - Department type (marketing / sales / customer_service / warehouse / hr /
                       finance / custom — enum cố định cho template filter)
      - Manager assignment (MANAGER role per dept)
      - Storage quota (% của enterprise total — initial 30%, adjust khi workflow live)
      - User count limit
      - Data sensitivity tag (PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED)
    → Submit → folder created /data/{tenant_id}/{enterprise_id}/{department_id}/
```

### M2b Gate (end of D3):
☐ ≥1 smallest department created in target enterprise unit
☐ Department type + manager + sensitivity tag set
☐ Wedge canonical confirmed in dept descriptor (alignment with §1.4)

## 2.4 D4-5 — Workflow Design for Smallest Department

Critical: thay vì upload data trước, ta **thiết kế workflow trước** dựa trên template catalog. Workflow là contract — nó quyết định step nào cần document gì, nên data upload ở D6 sẽ vào đúng chỗ.

### Pre-flight: pick template from catalog (mig 069)

CSM screen-share `/p2/workflow-templates?industry=<vertical>&department_type=<type>`:
- Filter by industry_vertical (từ D2 corporate setup) + department_type (từ D3 dept setup)
- 25 production templates × 5 verticals — customer thấy 3-5 templates phù hợp
- Mỗi template hiện preview: 5 cards × node_type + estimated_setup_minutes

### Template instantiation flow

```
/p2/workflow-templates → "Áp dụng template này"
  → POST /api/v1/workflows/from-template
      body: { template_id, department_id, branch_id (optional), custom_name }
  → Clone template's workflow_definition → real workflow + nodes + edges
  → Customer lands on /p2/workflows/{workflow_id}/builder (drag-drop view)
```

### D4-5 builder customization (CSM-guided, customer-driven)

CSM 60-min call walk through 5 cards:
1. **Adapt step 1 intake** — connector chọn (read_table / read_email / read_form_submission / read_webhook).
2. **Adapt step 2 processing/AI** — node_type catalog 45 lựa chọn (mig 068); palette curated per dept.
3. **Adapt step 3 decision** — if_else / switch / approval_gate threshold.
4. **Adapt step 4 action** — send_email template / create_task assignee.
5. **Adapt step 5 output** — publish_insight audience / display_dashboard tile.

Each step có `required_document_types` — đây là **contract** nói cho hệ thống biết step này cần file gì (mig 053 `workflow_step_documents`).

### M3 Gate (end of D5):
☐ ≥1 workflow live (state = DRAFT or ACTIVE) for smallest dept
☐ All 5 steps customized (not raw template defaults)
☐ required_document_types defined for each step that needs input data
☐ Workflow tree viewer at `/p2/workflows/{id}/tree` renders correctly

## 2.4a D6 — Workflow-Step-Aware Data Upload

Critical change: upload không còn là "drag file vào dept folder". Upload là **đáp ứng required_document_types của 1 step cụ thể**.

### Workflow-step-driven upload flow

```
/p2/workflows/{workflow_id}/builder
  → Click vào step có required_document_types
  → Modal "Step này cần documents:"
       - csv "Lead list" (required)
       - pdf "Source contract" (optional)
  → User upload file
  → POST /api/v1/upload với header X-Workflow-Step-ID = {step_node_id}
  → Backend:
       - Validate file đáp ứng required_document_type (kind whitelist Stage 4 mig 065)
       - SHA-256 dedupe (K-8)
       - Write Bronze + workflow_step_documents row link
       - Emit Kafka kaori.ingest.bronze.upload_complete WITH step_node_id context
  → Step's `has_input_data` flag flips TRUE — UI shows green checkmark
```

### Pre-flight checklist (customer-side):
□ Data đã export ra format đúng (required_document_type.kind)
□ ≥1 cột stable identity (customer_id / order_id / employee_id)
□ ≥1 cột thời gian (transaction_date, created_at, ...)
□ Có ≥500 records (target ≥3 tháng history) cho step có aggregate / forecasting
□ Encoding UTF-8 (KHÔNG dùng Excel default Win-1258 với tiếng Việt)

### Schema detection (Stage 2 — automatic)

Schema mapping flow giữ nguyên từ v3.0 (LLM column detection per domain) — nhưng giờ context là **step-bound**, không phải dept-bound. Nghĩa là step `aggregate` chỉ chấp nhận columns map vào aggregation schema; step `read_table` chấp nhận generic table read.

### M3b Gate (end of D6):
☐ ≥1 step có data uploaded successfully
☐ Schema mapping confirmed per step
☐ Bronze layer có data link đúng workflow_step_documents row
☐ `has_input_data` green checkmark visible trên builder UI

## 2.4b D7 — Bronze + Silver Validation per Workflow Step + Quality Scorecard

**Same as v3.0 §2.4** below — but quality scorecard runs **per workflow step** instead of per file dump, scoped to the step's required_document_types whitelist.
## 2.3 D4-5 — First Data Upload
Critical: Data quality D4 quyết định success cả 90 ngày.
### Pre-flight checklist:
□ Data đã export ra CSV/Excel/JSON
□ ≥1 cột là customer_id ổn định
□ ≥1 cột thời gian (transaction_date, created_at, ...)
□ Có ≥500 records (target ≥3 tháng history)
□ Encoding UTF-8 (KHÔNG dùng Excel default Win-1258 với tiếng Việt)
□ Không có whole rows duplicate
### Upload flow per department
User vào /p2/departments/marketing → upload tab → upload file:
Wizard Step 1: Upload
  [User] Drag drop CSV file
  [System] 
    - Validate kích thước (< plan limit)
    - Validate format
    - Compute SHA-256 checksum
    - Write Bronze layer raw_payload + envelope
    - Emit Kafka event kaori.ingest.bronze.upload_complete
    - Show preview top 10 rows + bottom 10 rows
    - Auto-detect: encoding, delimiter, header row, column count
  
Wizard Step 2: Schema Detection (automatic)
  [System]
    - LLM (Qwen 14B) analyze first 100 rows
    - Detect column semantics: customer_id? date? amount? category? text?
    - Map to standard fields per domain (xem Phần 6)
    - Highlight required-but-missing columns
    - Show: "Phát hiện cột 'ma_kh' = customer_id, 'ngay_mua' = transaction_date, ..."
  [User] Confirm or correct mapping
### Domain-aware schema requirements
System enforces minimum required columns based on declared domain. Đây là gate: nếu không đủ ESSENTIAL columns, không thể qua Step 2.
(Schema chi tiết per domain xem Phần 6)
### M3 Gate (end of D5):
☐ ≥1 file uploaded thành công
☐ Schema mapping confirmed
☐ Bronze layer có data
☐ Data quality scorecard generated
## 2.4 D6-7 — Bronze Layer Validation
### Auto-generated Data Quality Scorecard:
═══════════════════════════════════════════════════════
  DATA QUALITY SCORECARD — Marketing Department
═══════════════════════════════════════════════════════
  Source file: customers_2026Q1.csv
  Records: 14,237
  
  ✓ Schema completeness: 9/10 essential columns present
  ⚠ Null rate (customer_id): 12% — RECOMMENDED FIX
  ✗ Date format inconsistency: 3 different formats detected
  ⚠ Duplicate records: 234 (1.6%) — REVIEW
  ✓ Character encoding: UTF-8 valid
  ⚠ PII detected: phone (78%), email (52%) — will be masked
  ✓ Range validation: amounts in expected range
  
  Overall score: 72/100 — ACCEPTABLE (recommended 80+)
  
  Suggested actions:
  1. Clean rule: drop rows where customer_id IS NULL
  2. Standardize date to ISO 8601
  3. Dedupe by (customer_id, transaction_date)
═══════════════════════════════════════════════════════
### M4 Gate (end of D7):
☐ Data quality score ≥60
☐ Customer informed of issues + acceptance OR rules applied
☐ Bronze layer contains usable data
### State transition: ONBOARDING → ACTIVATING ✅

# Phần 3. WEEK 2-4 — Activation Phase (D8-30)
Goal: Pipeline E2E (Bronze→Silver→Gold). First insight với confidence ≥0.6. First “Đã xử lý” action.
## 3.1 D8-14 — Silver Layer Build (Cleaning + Standardization)
### Cleaning rules workflow
System suggests, user confirms — không bao giờ apply tự động:
For each Bronze table:
  1. AI suggest cleaning rules (Qwen 14B + domain template)
     Examples:
     - "Remove rows where amount < 0 (likely refunds, separate them)"
     - "Convert phone format to +84xxxxxxxxx"
     - "Trim whitespace in name fields"
     - "Detect outliers: amount > P99.5 → flag for review"
     - "Mask PII: email → email_hash, phone → phone_last4"
  
  2. User reviews each rule:
     [✓ Apply] [✗ Skip] [✏️ Edit]
  
  3. Preview Before/After:
     Show: 10 sample rows before, after, diff
  
  4. Apply on full data → write Silver layer
  
  5. Log step_log với:
     - rule_id
     - applied_by (user_id)
     - rows_affected
     - timestamp
     - rollback_query (in case revert needed)
### Silver layer schema (per domain)
Silver layer normalize tất cả về schema chuẩn của Kaori. Đây là interface contract.
Ví dụ Retail domain (xem Phần 6 cho all domains):
silver.customers
  customer_id           STRING (NOT NULL, unique per tenant)
  customer_external_id  STRING (raw từ source — for billing)
  name_masked          STRING (full name removed)
  phone_e164           STRING (+84xxxxxxxxx)
  email_hash           STRING (SHA-256 first 16 char)
  city, region         STRING (normalized)
  first_seen_at        TIMESTAMP
  last_seen_at         TIMESTAMP
  ltv                  NUMERIC(12,2) VND
  segment              ENUM (VIP/REGULAR/NEW/INACTIVE)
  ingested_at          TIMESTAMP
  source_system        STRING

silver.transactions
  txn_id               STRING (NOT NULL, unique)
  customer_id          STRING (FK)
  txn_ts               TIMESTAMP
  amount               NUMERIC(12,2)
  currency             ENUM ('VND', 'USD' Phase 2)
  channel              ENUM (online, in_store, marketplace)
  source_system        STRING
  status               ENUM (completed, refunded, cancelled)
  payment_method       ENUM (vnpay, momo, vietqr, cod, card)
### M5 Gate (end of D14):
☐ Silver layer built cho ≥1 department (wedge dept first)
☐ ≥80% records pass cleaning
☐ Schema documented và versioned
## 3.2 D15-21 — Gold Layer + First Insights
### Gold layer = Business-ready features per domain
Gold layer là VIEWS — refresh daily. Ví dụ Retail Gold view:
CREATE VIEW gold.customer_health AS
SELECT
  c.customer_id,
  c.segment,
  c.ltv,
  
  -- RFM features
  date_diff('day', max(t.txn_ts), now()) AS recency_days,
  count(distinct t.txn_id) AS frequency_30d,
  sum(t.amount) AS monetary_90d,
  
  -- Behavioral features
  std_dev(date_diff('day', lag(t.txn_ts) over (...), t.txn_ts)) AS purchase_interval_variance,
  count(distinct date_part('hour', t.txn_ts)) AS time_diversity,
  
  -- Risk signals
  count(*) filter (where t.status='refunded') / count(*)::float AS refund_rate_30d,
  
  -- Predictions (refreshed daily)
  m.churn_probability,
  m.churn_risk_label,
  m.revenue_at_risk,
  m.top_factors_vi,
  m.recommended_action,
  
  -- Action tracking
  m.is_actioned,
  m.actioned_at,
  m.actioned_by

FROM silver.customers c
LEFT JOIN silver.transactions t ON c.customer_id = t.customer_id
LEFT JOIN model.predictions m ON c.customer_id = m.customer_id
WHERE c.tenant_id = current_tenant_id()
GROUP BY c.customer_id, c.segment, c.ltv, m.*;
### Insights Engine 3-tuyến output
Sau pipeline run, system tự động generate insights cho từng phòng ban (đặc biệt wedge dept):
═══════════════════════════════════════════════════════
  INSIGHT — Marketing Department · 2026-04-22
═══════════════════════════════════════════════════════
  
  📊 CHUYỆN GÌ ĐANG XẢY RA?
  Trong 14 ngày qua, 234 khách VIP có dấu hiệu giảm tần suất
  mua hàng — giảm 38% so với 14 ngày trước đó. Tổng giá trị
  doanh thu tiềm năng đang ở rủi ro: 187 triệu VND.
  
  🔍 TẠI SAO?
  AI phân tích top 3 yếu tố (qua SHAP):
  • [38%] Khách không nhận voucher tháng này (so với 92%
    nhận tháng trước)
  • [29%] Chiến dịch email tháng 4 mở rate giảm xuống 12%
    (baseline 28%)
  • [24%] 3 cửa hàng key tồn kho sản phẩm best-seller dưới 20%
  
  Confidence: 0.74 (chấp nhận được)
  ⚠ Calibration: Predictions ở mức 0.74 thực tế đúng 71% (last 100)
  
  💡 NÊN LÀM GÌ?
  Action 1: Gửi voucher 10% cho 234 khách VIP risk này
            (chi phí ước tính 5tr, ROI dự kiến 12-15x)
  Action 2: A/B test subject line email tháng 5
  Action 3: Re-stock 3 cửa hàng theo demand forecast
  
  [Đã xử lý] [Tạm hoãn] [Không phù hợp + Lý do]
  
  ⚠️ AI-generated — verify before action
═══════════════════════════════════════════════════════
### Frameworks tự động (Module 2.9)
Per phòng ban, AI cũng generate analysis theo frameworks (limit theo plan):

| Framework | Use case | Output format |
|---|---|---|
| SWOT | Tổng quan strategic position | 4 quadrants với data backing |
| 6W2H | Drill into specific issue | Who/What/When/Where/Why/Whom + How/How much |
| Fishbone (xương cá) | Root cause của 1 vấn đề | Diagram 6M: Man/Machine/Method/Material/Measurement/Mother nature |
| MoM/YoY | Trend over time | Time series với highlight anomaly |
| 5 Why | Deep dive root cause | Iterative why questions với data validation |

### M6 Gate (end of D21):
☐ Gold layer refreshed daily
☐ ≥1 insight per department với confidence ≥0.6
☐ ≥1 framework analysis available (SWOT minimum)
☐ Wedge department có ≥3 insights actionable
## 3.3 D22-30 — First Reports + First Action
### Reports per department
Auto-generated reports limited per plan (Phần 9):
Daily reports (auto, 7am):
  - Department KPI snapshot
  - Top 10 risks alerts
  - Yesterday's performance summary

Weekly reports (Monday 7am):
  - Department deep-dive
  - WoW comparison
  - Workflow effectiveness

Monthly reports (1st 7am):
  - Executive summary all departments
  - ROI realized
  - Action conversion rate
### Critical: First “Đã xử lý” (D25-30)
CSM phải push hard cho moment này. Lý do: nếu user không action insight nào trong 30 ngày, churn rate +35%.
CSM playbook D25-30: - Gọi customer, walk through insight cụ thể - Cùng customer thực hiện action ngoài đời (vd: gửi voucher) - 1-on-1 demo nút “Đã xử lý” - 14 ngày sau, follow-up: “khách của bạn có quay lại không?” → ROI proof
### M7 Gate (end of D30):
☐ ≥1 report sent per department
☐ Customer click “Đã xử lý” ≥1 lần
☐ ≥1 insight được customer đánh giá useful (thumbs up)
### State transition: ACTIVATING → PROVING ✅

# Phần 4. WEEK 5-8 — Workflow Phase (D31-60)
Goal: Customer’s existing workflows được map vào hệ thống (comprehensive visibility). AI phân tích, suggest optimization cho wedge workflow. Mid-cycle review meeting.
## 4.1 D31-45 — Map ALL Current Workflows
Quan trọng: Map tất cả, không chỉ wedge. Visibility = comprehensive. Active intervention = wedge.
### Workflow Builder (Module 2.17) onboarding
CSM workshop với customer’s project lead — 2-3 giờ:
Step 1: Inventory ALL workflows - Liệt kê 5-10 workflow chính của doanh nghiệp (từ tất cả phòng ban) - Mỗi workflow: tên, owner, frequency, trigger, expected outcome - Status flag: wedge_focus for the canonical wedge, observed_only for others
Step 2: Detail each workflow
Per workflow, document trong Workflow Builder:
Workflow: "Retention campaign hàng tuần"
Owner: Marketing Manager
Frequency: Mỗi thứ 2
Trigger: Manual
Status: wedge_focus  ← AI sẽ active analyze cái này

Steps (drag-drop nodes):
  [Node 1] Pull khách HIGH risk
    Input: gold.customer_health WHERE churn_risk_label='HIGH'
    Output: list 200-500 customers
    
  [Node 2] Filter eligible
    Input: list từ Node 1
    Filter: VIP segment AND ltv > 5M VND
    Output: filtered list
    
  [Node 3] Generate voucher codes
    Input: filtered list
    Action: call CRM API to generate codes
    Output: codes list
    
  [Node 4] Send email
    Input: codes list + email template
    Action: SendGrid API
    Output: email_sent count
    
  [Node 5] Track conversions (7 days later)
    Input: list từ Node 1
    Action: query gold.customer_health 7 days later
    Output: conversion_rate, revenue_recovered
    
  [Branch] Conversion < 5%? → notify Manager
  [Branch] Conversion ≥ 15%? → expand to MEDIUM risk next week
### Workflow Risk Classification (mandatory)
Mỗi workflow phải declare risk class khi tạo. System auto-suggest, user confirms:

| Trigger | Risk Class | Approval needed |
|---|---|---|
| Read-only reports/insights | LOW | Auto-approve |
| Sends external email/SMS to >100 recipients | MEDIUM | Department manager |
| Modifies pricing/inventory in external system | HIGH | Dept manager + Enterprise manager |
| Triggers financial transaction | CRITICAL | Dept manager + Enterprise manager + Compliance |
| Exposes PII to external system (even masked) | HIGH | Dept manager + Enterprise manager |
| Affects >1 department’s data | MEDIUM | Department managers (all affected) |
| Trains/promotes a model | HIGH | Same as financial |
| Modifies user permissions | HIGH | Same as financial |
| Workflow with no approval gate but high impact | CRITICAL | Up-tier 1 level |

### Workflow quotas per plan
(Đầy đủ trong Phần 9 — Pricing matrix)
### M8 Gate (end of D45):
☐ ≥3 workflows mapped (tất cả depts represented)
☐ Wedge workflow có status wedge_focus
☐ Mỗi workflow có owner + frequency + risk class
☐ Workflow run được test thành công ≥1 lần
## 4.2 D46-60 — AI Workflow Analysis (Wedge focus)
### AI agent observe wedge workflow for 14 days
Daily observation:
  - Workflow execution log
  - Output metrics (conversion rate, time taken, cost)
  - Comparison vs benchmark (industry baseline + tenant historical)
  - Anomaly detection on outputs
  - Bottleneck identification (which step is slowest)

After 14 days:
  - Generate Workflow Health Report
  - Suggest optimizations với confidence score
  - Estimate ROI của mỗi optimization
### Example Workflow Optimization Suggestion (D60)
═══════════════════════════════════════════════════════
  WORKFLOW OPTIMIZATION — "Retention campaign hàng tuần"
═══════════════════════════════════════════════════════
  
  📊 OBSERVATION (14 days):
  - Run 2 lần/tuần → 4 runs total
  - Avg time per run: 3.5 hours (mostly Node 4)
  - Conversion rate: 7.2% (target was 15%)
  - ROI realized: 4.1x (target 12x)
  
  🔍 AI ANALYSIS:
  Bottleneck: Node 2 filter quá strict — chỉ 12% khách HIGH
  risk pass filter "VIP + ltv > 5M". 88% khách HIGH risk không
  được nurture → mất họ.
  
  Statistical evidence: trong 88% bị filter ra, có 31% là
  pre-VIP (ltv 3-5M, lifecycle 6-12 months) — segment cao
  potential nhất theo cohort analysis.
  
  💡 SUGGESTED NEW WORKFLOW: "Retention campaign tier 2"
  
  Difference vs current:
  - Add Node 1.5: separate pre-VIP từ standard
  - Add Node 4.5: send DIFFERENT email to pre-VIP
                  (template emphasis on "đặc quyền VIP near")
  - Add Node 5.5: track upgrade rate (pre-VIP → VIP)
  
  Confidence: 0.71
  Estimated ROI improvement: +180% (4.1x → 11.5x)
  
  RECOMMENDATION:
  Run NEW workflow IN PARALLEL với current từ D75-D90.
  Không thay thế — chạy song song để compare.
  
  [Approve parallel test] [Reject + Reason] [Modify suggestion]
═══════════════════════════════════════════════════════
### Mid-cycle Review Meeting D60 (mandatory)
Attendees: Customer’s executive sponsor + project lead + Kaori AE + Kaori CSM
Agenda (90 phút):

| Time | Item | Owner |
|---|---|---|
| 0-15 | Health score & state recap | CSM |
| 15-30 | ROI realized (60 days) — actual vs projected | CSM + Customer PM |
| 30-50 | AI insights performance — accuracy, action conversion, calibration drift | CSM |
| 50-70 | Workflow optimization recommendations review | CSM |
| 70-85 | Decisions: approve/modify/reject parallel tests | All |
| 85-90 | Action items + next 30 days plan | All |

Output: Decision document signed off.
### M9 + M10 Gate (end of D60):
☐ ≥1 workflow optimization với confidence ≥0.7
☐ Mid-cycle review meeting completed
☐ Decisions documented + signed off
☐ ≥1 new workflow approved for parallel testing
### State transition: PROVING → EXPANDING ✅

# Phần 5. WEEK 9-12 — Handover Phase (D61-90)
Goal: Parallel run new workflow. Studio activated cho customer’s data team (per archetype). Final review + 90-day handover.
## 5.1 D61-75 — Parallel Workflow Execution
Quy tắc cốt lõi: Old workflow KHÔNG bị tắt khi new chạy. Cả 2 chạy song song với traffic split.
Traffic split per plan:
  PILOT:    100% old, 0% new (no parallel — limit)
  ENT BASIC: 80% old, 20% new
  ENT MID:   50% old, 50% new (true A/B)
  ENT MAX:   Configurable per workflow
### Daily monitoring during parallel run
Per workflow being tested: - Daily metric snapshot: conversion rate, ROI, time, cost - Statistical significance check (need ≥7 days for power) - Anomaly detection on either arm - Auto-rollback if new arm performs >20% worse on critical metric
### Workflow status state machine

| Status | Meaning | Auto-transition |
|---|---|---|
| LIVE_OLD | Workflow gốc, đang chạy production | n/a |
| EXPERIMENTAL_NEW | Workflow mới, đang chạy parallel với old | After ≥14d data + significance → DECISION |
| PROMOTED | New workflow đã thắng, replace old | Old → DEPRECATED |
| DEPRECATED | Old workflow đã được replace, hold 30 ngày | After 30d → ARCHIVED |
| ARCHIVED | Workflow đã retire, giữ definition cho audit | n/a |
| ROLLED_BACK | New workflow tệ hơn old, đã rollback | n/a |

### M11 Gate (end of D75):
☐ ≥1 workflow chạy parallel với old
☐ Daily metrics being collected
☐ Significance test running
☐ Auto-rollback triggers configured
## 5.2 D76-89 — Studio Activation cho Customer Data Team
Note: Timing này là default. Per archetype: - Archetype 1 (Chaotic SME): Studio defer to month 4-5 (Phase 2 of contract) - Archetype 2 (Ops-Driven): D60+ if there’s ops analyst - Archetype 3 (Growing): D30-45 (move up — họ wait for này) - Archetype 4 (Enterprise): D14 từ đầu (move up significantly) - Archetype 5 (Regulated): D76+ với compliance audit
### Studio access provisioning per plan

| Plan | Studio access | Roles available | Capabilities |
|---|---|---|---|
| PILOT | ❌ No | — | — |
| ENT BASIC | ❌ No | — | — |
| ENT MID | ✅ Yes Phase 2+ | STUDIO_ANALYST | Read all, propose cleaning rules, propose workflows |
| ENT MAX | ✅ Yes | STUDIO_ANALYST + STUDIO_ADMIN | + custom model training, prompt tuning, project ownership |

### Studio onboarding workshop (4 hours)
CSM + Studio Analyst (Kaori-side) train customer’s data team: - Studio UI walk-through - Project structure - Model registry & versioning - Notebook environment - Cleaning rules collaboration workflow - Workflow proposal workflow
### Cleaning rules collaboration
[Customer's data engineer] notices issue trong silver data:
  "Phone numbers có format không nhất quán - cần normalize"
  → Studio: New cleaning rule proposal
  → Define rule (regex hoặc LLM-assisted)
  → Test on sample 1000 records
  → See Before/After
  → Submit for approval

[Auto/Manual review]:
  Confidence ≥ 0.9 + low risk: auto-approve
  Otherwise: Kaori Studio Analyst review (24h SLA)

[Approved]: 
  - Rule active in next pipeline run
  - Audit log: who proposed, who approved, what changed
  - Reversible: rollback within 7 days

[Rejected]:
  - Reason logged
  - Customer can iterate or escalate
### AI Co-pilot trong Studio
Qwen-powered chat assistant trong Studio sidebar:

| Query type | Example | AI response |
|---|---|---|
| Data exploration | “Top 10 khách mua nhiều nhất Q1” | Generate SQL, run, return result |
| Feature suggestion | “Suggest features cho churn model F&B” | List 15 features ranked by expected importance |
| Code assist | “Tại sao đoạn này throw error?” | Debug + suggest fix |
| Domain knowledge | “Best practice retention F&B Việt Nam?” | Curated answer từ Knowledge Base |
| SHAP explanation | “Tại sao customer X bị classify HIGH?” | Top factors translated tiếng Việt |
| Hypothesis test | “Cohort A has higher LTV than B?” | Run statistical test, return result |

### Workflow proposal workflow
Customer’s data team có thể propose new workflow: 1. Build trong Studio sandbox 2. Test trên historical data (backtest) 3. Submit for review (Kaori Studio Analyst + Customer Manager) 4. If approved: deploy parallel mode (status EXPERIMENTAL_NEW) 5. After 14d significance → promote/rollback
## 5.3 D90 — Final Review & Handover
### 90-Day Final Review Meeting
Attendees: Customer executive + project lead + customer data team lead + Kaori AE + CSM + Studio Analyst (if Studio activated)
Agenda (2 giờ):

| Section | Owner | Output |
|---|---|---|
| 90-day metrics deep dive | CSM | Comprehensive ROI document |
| Health score trajectory | CSM | Visual chart + state transitions |
| Workflow optimization results | Customer PM + CSM | Win/loss/draw per workflow tested |
| Studio onboarding effectiveness | Studio Analyst | Customer team capability score |
| Pain points & feedback | Customer (open) | List for Kaori product team |
| Next 90 days plan | All | Signed plan |
| Pricing review | AE | Upgrade/maintain/downgrade decision |

### 90-Day Report (auto-generated PDF)
Sections: 1. Executive Summary (1 page) 2. Health Score Journey (visual) 3. Data Foundation Achievements 4. Insights Generated (count + quality metrics) 5. Actions Taken (count + ROI) 6. Workflows Mapped + Optimized (table) 7. Studio Adoption (if applicable) 8. Recommendations for next 90 days
### Handover Decision Matrix

| Health Score End of D90 | State | Decision |
|---|---|---|
| ≥80 sustained 14d | HEALTHY | Standard maintenance, QBR cadence quarterly |
| 60-79 | EXPANDING (continuing) | Extended onboarding +30 days, focused workshops |
| 40-59 | AT-RISK | Executive escalation, root cause workshop, possible discount/credit |
| <40 | CHURNING | Save plan: deep call, possible plan downgrade or pause, 30-day decision window |

### M12 Gate (end of D90):
☐ Final review meeting completed
☐ 90-day report delivered
☐ Next 90-day plan signed
☐ Health state confirmed
☐ QBR cadence scheduled
### State transition target: EXPANDING → HEALTHY ✅

# Phần 6. Domain-Specific DB Schemas + Wedge Canonical
Triết lý: Mỗi vertical có ESSENTIAL columns (block deployment if missing), PRIORITY columns (warn, degraded experience), OPTIONAL columns (nice-to-have, advanced features unlock). Plus 1 wedge canonical đề xuất sales pitch.
## 6.1 Retail / F&B / FMCG / Beauty / Fashion
Wedge canonical: Churn retention (HIGH risk customers)
### Customer table

| Tier | Column | Type | Why critical |
|---|---|---|---|
| ESSENTIAL | customer_id | string | Anchor cho mọi feature |
| ESSENTIAL | first_seen_date | date | LTV, cohort analysis |
| PRIORITY | name | string (PII masked) | Insight readability |
| PRIORITY | phone | E.164 | Channel for retention action |
| PRIORITY | gender | enum | Segmentation |
| PRIORITY | birth_year | int | Age cohort |
| PRIORITY | city, region | string | Geographic features |
| OPTIONAL | email | hashed | Email campaigns |
| OPTIONAL | loyalty_tier | enum | VIP segmentation |
| OPTIONAL | referral_source | string | Acquisition analysis |

### Transaction table

| Tier | Column | Type | Why critical |
|---|---|---|---|
| ESSENTIAL | txn_id | string unique | Dedup |
| ESSENTIAL | customer_id | FK | Link |
| ESSENTIAL | txn_ts | timestamp | RFM core |
| ESSENTIAL | amount | numeric | Monetary |
| PRIORITY | items | JSONB | Cross-sell, basket analysis |
| PRIORITY | category | string | Affinity features |
| PRIORITY | channel | enum | Channel preference |
| PRIORITY | payment_method | enum | Behavioral signal |
| OPTIONAL | discount_applied | numeric | Price sensitivity |
| OPTIONAL | store_id | string | Geographic features |
| OPTIONAL | staff_id | string | Operational signals |
| OPTIONAL | review_score | int 1-5 | Satisfaction signal |

### Auto-derived KPIs (Gold layer)

| KPI | Formula | Update freq |
|---|---|---|
| LTV | sum(amount) over customer | Daily |
| RFM scores | Recency/Frequency/Monetary deciles | Daily |
| Churn probability | Trained model output | Daily |
| Revenue at risk | E[ltv \| churn=true] × P(churn) | Daily |
| Segment | Rule-based on RFM + LTV | Daily |
| Average basket | sum(amount) / count(txn) | Daily |
| Cross-sell propensity | embedding similarity to top buyers | Weekly |

## 6.2 E-commerce (online native)
Wedge canonical: Cart abandonment recovery
Similar to Retail nhưng extra columns:

| Tier | Column | Type |
|---|---|---|
| PRIORITY | session_id | string |
| PRIORITY | traffic_source | enum (organic/paid/email/direct/social) |
| PRIORITY | device_type | enum |
| PRIORITY | cart_abandonment | boolean |
| OPTIONAL | search_query | string |
| OPTIONAL | product_view_sequence | array |

## 6.3 Logistics / Supply Chain
Wedge canonical: On-time delivery prediction
### Shipment table

| Tier | Column | Type |
|---|---|---|
| ESSENTIAL | shipment_id | string |
| ESSENTIAL | order_id | string |
| ESSENTIAL | origin | string/geo |
| ESSENTIAL | destination | string/geo |
| ESSENTIAL | created_at | timestamp |
| ESSENTIAL | promised_delivery_date | date |
| PRIORITY | weight_kg, volume_m3 | numeric |
| PRIORITY | actual_delivery_date | date |
| PRIORITY | carrier_id | string |
| PRIORITY | route | string |
| PRIORITY | status_history | JSONB array |
| OPTIONAL | weather_at_destination | string |
| OPTIONAL | traffic_index | numeric |

### Auto-derived KPIs
On-time delivery rate
Delivery time variance
Cost per shipment
Route efficiency
Carrier performance score
## 6.4 Manufacturing
Wedge canonical: Defect prediction OR Predictive maintenance
### Production batch table

| Tier | Column | Type |
|---|---|---|
| ESSENTIAL | batch_id | string |
| ESSENTIAL | product_id | string |
| ESSENTIAL | quantity_planned | int |
| ESSENTIAL | quantity_actual | int |
| ESSENTIAL | start_ts, end_ts | timestamp |
| PRIORITY | machine_id | string |
| PRIORITY | operator_id | string |
| PRIORITY | defect_count | int |
| PRIORITY | downtime_minutes | numeric |
| OPTIONAL | raw_material_lot | string |
| OPTIONAL | quality_score | numeric |

### Auto-derived KPIs
Yield rate (good / total)
OEE (Overall Equipment Effectiveness)
Defect rate trend
Predicted maintenance need
## 6.5 Education
Wedge canonical: Dropout risk prediction
### Student enrollment table

| Tier | Column | Type |
|---|---|---|
| ESSENTIAL | student_id | string |
| ESSENTIAL | course_id | string |
| ESSENTIAL | enrollment_date | date |
| PRIORITY | grade | numeric |
| PRIORITY | attendance_rate | numeric |
| PRIORITY | tuition_status | enum |
| OPTIONAL | extracurricular | JSONB |

### Auto-derived KPIs
Pass rate
Dropout risk score
Tuition collection rate
Course satisfaction score
## 6.6 Real Estate
Wedge canonical: Lead scoring
### Property listing table

| Tier | Column | Type |
|---|---|---|
| ESSENTIAL | property_id | string |
| ESSENTIAL | listing_type | enum (rent/sale) |
| ESSENTIAL | price | numeric |
| ESSENTIAL | location | geo + address |
| ESSENTIAL | size_m2 | numeric |
| PRIORITY | bedrooms, bathrooms | int |
| PRIORITY | year_built | int |
| PRIORITY | property_type | enum |
| OPTIONAL | amenities | JSONB array |
| OPTIONAL | listing_views | int |

## 6.7 Special Domains (Brief — see Phần 14 for full)
### Finance / Banking → Phần 14.1
Wedge canonical: Credit risk scoring OR Fraud detection Note: Heavy compliance overlay (Basel III, AML)
### Healthcare → Phần 14.2
Wedge canonical: No-show prediction OR Readmission risk Note: Extreme PII protection (HIPAA equivalent)
### Government / Public → Phần 14.3
Wedge canonical: Service request triage Note: Procurement processes + transparency requirements

# Phần 7. AI Quality & Calibration Framework
## 7.1 AI Accuracy Lifecycle (Cold Start → Mature)

| Stage | Time period | Data status | Expected accuracy | Confidence threshold | What user sees |
|---|---|---|---|---|---|
| Cold Start | D1-D30 | <30 days customer data + industry baseline | 60-65% | 0.5 (low gate) | “AI đang học data của bạn — kết quả ban đầu chỉ tham khảo” |
| Warm Up | D31-D60 | 1-2 months tenant data + transfer learning | 65-72% | 0.6 | “AI bắt đầu hiểu pattern riêng. Khuyến nghị verify trước action” |
| Active Learning | D61-D90 | 2-3 months + active feedback loop | 72-78% | 0.65 | “AI có hiểu biết tốt về business của bạn” |
| Personalized | D91-D180 | 3-6 months + multiple retrains | 78-85% | 0.7 | “AI personalized cho doanh nghiệp bạn” |
| Mature | D180+ | 6+ months + continuous learning | 85-92% | 0.75 | “AI ở performance tối ưu” |

Critical: Data quality matters MORE than time. Bad data + time = plateau forever (~65%). Good data + time → 90%+.
## 7.2 Confidence vs Calibration
Vấn đề: Confidence ≠ correctness. Một model có thể self-report confidence 0.85 mà thực tế chỉ 60% đúng. Đây là silent killer của AI products.
### Required Calibration Metrics (track daily)

| Metric | Formula | Target Phase 1 | Target Phase 3 |
|---|---|---|---|
| Brier Score | mean((pred_prob - actual)²) | <0.20 | <0.10 |
| Expected Calibration Error (ECE) | Weighted avg of \|conf - acc\| per bin | <0.10 | <0.03 |
| Maximum Calibration Error (MCE) | Max \|conf - acc\| across bins | <0.15 | <0.05 |

### Calibration Techniques

| Technique | When to use | Implementation phase |
|---|---|---|
| Platt scaling | Binary classification, simple | Phase 1 M3 |
| Isotonic regression | More flexible, larger calibration set | Phase 2 M5 |
| Temperature scaling | LLM confidence outputs | Phase 1 M4 |
| Beta calibration | Heavy class imbalance | Phase 2 |

### Confidence-Based Action Policy
Confidence ≥ 0.85 + ECE < 0.05 → "TRUSTED" badge, action button prominent
                                  Auto-execute OK for ENT MAX với policy

Confidence ≥ 0.85 + ECE > 0.10 → "OVER-CONFIDENT WARNING" 
                                  → require manual verify

Confidence 0.65 - 0.84       → "REVIEW NEEDED" badge
                                  → mandatory verification step
                                  → show top 3 SHAP factors

Confidence 0.40 - 0.64       → "AI UNCERTAIN" warning
                                  → recommend manual investigation
                                  → show alternative scenarios

Confidence < 0.40            → No actionable display
                                  → log "AI insufficient confidence"
                                  → trigger fallback hierarchy
### Calibration UI Display Phase 1 → Phase 3
Phase 1: Simple “Confidence: 73%” với badge color
Phase 2: Confidence + reliability indicator: “Confidence 73% (calibrated within ±5%)”
Phase 3: Confidence + similar-historical-accuracy: “Confidence 73%. Last 100 predictions at this level were 71% correct”
## 7.3 Fallback Hierarchy (When AI Cannot Predict)
5-level priority order:
### Level 1: Domain Expert Rules (always available)
Pre-built rules cho mỗi vertical (curated by Kaori):

Retail rule examples:
  - if recency > 60 days AND frequency_lifetime > 5 → "Possibly churning, contact"
  - if first_purchase < 7 days ago AND amount > 5x avg → "VIP onboarding"
  - if return_rate_30d > 30% → "Investigate satisfaction issue"

Finance rule examples:
  - if days_past_due > 30 → "Collection priority HIGH"
  - if 3+ failed login → "Security review"
### Level 2: Cohort/Peer Comparison
Even if can’t predict 1 customer, compare to cohort: - “Khách này thuộc cohort X. Cohort X có 23% churn rate” - “Khách top spender 3 tháng → cohort ‘3M-VIP’. Cohort retention 87%”
### Level 3: Trend Analysis (aggregate level)
When individual prediction fails, aggregate signals work: - Department-level KPI trend - Cohort retention curves - Channel/segment shifts - Anomaly detection on totals
### Level 4: Crowd-sourced patterns (Phase 3+)
Patterns learned across tenants in same vertical (anonymized + consent): - “Doanh nghiệp tương tự ngành bạn thường thấy churn spike Q1” - “Cohort behavior này thường indicate competitor entry”
### Level 5: Studio Manual Investigation (last resort)
Customer’s data team manually investigates: - AI surfaces “I don’t know about these 50 customers” → human reviews - Custom feature engineering for edge cases - Update model với new patterns
## 7.4 Domain-Specific Metrics Priority
### Retail / F&B

| Priority | Metric | Why |
|---|---|---|
| 1 | Recency (days since last purchase) | Strongest churn signal |
| 2 | Frequency (purchase count) | Loyalty signal |
| 3 | LTV / Customer Lifetime Value | Revenue impact |
| 4 | Average Basket Size | Up-sell potential |
| 5 | Repeat purchase rate | Stickiness |
| 6 | Return rate | Satisfaction signal |
| 7 | Channel preference | Targeting |
| 8 | Cross-category purchases | Discovery / cross-sell |

Formulas: - Churn definition: recency > 90 days AND last_recency < 90 (was active) - Revenue at Risk: LTV × P(churn) × attribution_factor (attribution = 0.3-0.5) - LTV: sum(amount) | customer + projected next 12m
### Finance / Banking

| Priority | Metric | Why |
|---|---|---|
| 1 | Probability of Default (PD) | Credit risk |
| 2 | Days past due | Operational urgency |
| 3 | Customer profitability (NIM-based) | Strategic value |
| 4 | Cross-sell propensity | Wallet share |
| 5 | Fraud risk score | Loss prevention |
| 6 | Activation rate (new customer) | Acquisition ROI |
| 7 | Account dormancy | Engagement |

### Logistics

| Priority | Metric | Why |
|---|---|---|
| 1 | On-time delivery rate | Service level |
| 2 | Cost per shipment | Margin |
| 3 | Delivery time variance | Reliability |
| 4 | Route efficiency | Operations |
| 5 | Carrier performance | Vendor mgmt |
| 6 | Volume trend | Capacity planning |

### Manufacturing

| Priority | Metric | Why |
|---|---|---|
| 1 | OEE (Overall Equipment Effectiveness) | Operational excellence |
| 2 | Yield rate | Quality |
| 3 | Defect rate | Quality control |
| 4 | Downtime % | Productivity |
| 5 | Predicted maintenance need | Preventive |

## 7.5 AI Risk Responsibility Model
Cốt lõi: “AI không chịu rủi ro nếu dự đoán hoặc làm sai.”
### 5 nguyên tắc:
AI là Co-pilot, không phải Auto-pilot. Mọi action có human approval (trừ low-risk auto-actions explicit policy).
Confidence transparency mọi nơi. User luôn thấy “AI tin x%”. Không hidden numbers.
Audit trail immutable. Every AI suggestion + every human decision logged.
Override always available. User có thể từ chối AI suggestion. Override với reason → feedback loop.
Disclaimer mọi insight. “⚠️ AI-generated, verify before action” badge. PDF reports có watermark.
### Contractual layer
Trong customer contract: - Kaori provides decision support tool, not decision-making service - Customer retains full responsibility for business decisions - Kaori liability cap = 12 months subscription fee - Indemnification carve-outs cho gross negligence
### When AI is Wrong — Incident Protocol
Customer reports: "AI dự đoán sai, tôi mất 50tr"
  →
Step 1: Investigation (CSM + Customer)
  - Reproduce: same data, same time, same result?
  - Was confidence shown? What level?
  - Was action recommended or auto-executed?
  - Was override option clearly available?

Step 2: Categorize
  - Type A: AI confidence < 0.6 + customer ignored warning → Customer's call
  - Type B: AI confidence > 0.8 but wrong → Kaori issue; investigate model bias
  - Type C: System bug (display wrong / data corruption) → Kaori SLA breach

Step 3: Resolution
  - Type A: Coaching call, no compensation
  - Type B: Apology + model fix + 1-3 month credit (case-by-case)
  - Type C: Full refund of relevant period + SLA credit

Step 4: Prevent recurrence
  - Update guardrails
  - Add to golden test set
  - Pattern check across other tenants
## 7.6 Continuous Improvement Timeline
Month 1-2: Foundation
  Goal: Don't make things worse than rule-based
  Confidence floor: 0.5 (only show high confidence)
  Heavy human-in-loop

Month 3-6: Personalization
  Goal: Beat industry baseline by 5-10pp
  Confidence floor: 0.6
  AI suggestions become primary, rules become safety net

Month 6-12: Mature operation
  Goal: 80%+ accuracy, consistent ROI
  Confidence floor: 0.65
  Auto-actions for ENT MAX with policy

Month 12+: Continuous improvement
  Goal: 85%+ accuracy, predict edge cases
  Confidence floor: 0.7
  Learn from cross-tenant patterns (anonymized)

# Phần 8. Workflow Policy & Governance Engine
Mục đích: Khi AI/workflow sai, ai chặn? Disclaimer không đủ. Cần policy engine + approval graph + blast radius + rollback.
## 8.1 Policy Engine Architecture
┌─────────────────────────────────────────────────────────┐
│   WORKFLOW EXECUTION REQUEST                            │
│            ↓                                            │
│   ┌────────────────┐                                    │
│   │ Policy Decision│  ← Policy Definition Library       │
│   │ Point (PDP)    │  ← Approval Graph Lookup           │
│   └────────┬───────┘  ← Tenant-specific Overrides       │
│            ↓                                            │
│   Decision: ALLOW / DENY / REQUIRE_APPROVE              │
│            ↓                                            │
│   if REQUIRE_APPROVE:                                   │
│     → Send to approver(s) with timeout                  │
│     → Wait for resolution                               │
│     → ALLOW or DENY based on response                   │
│            ↓                                            │
│   Execute workflow OR return blocked                    │
│            ↓                                            │
│   Audit log immutable                                   │
└─────────────────────────────────────────────────────────┘
## 8.2 Approval Graph
# Default approval graph for ENT MID
approval_graph:
  LOW:
    auto_approve: true
    log_only: true
    
  MEDIUM:
    require_approve_from:
      - role: department_manager
      - count: 1
    timeout: 24h
    timeout_action: deny
    
  HIGH:
    require_approve_from:
      - role: department_manager
      - count: 1
      - AND
      - role: enterprise_manager
      - count: 1
    timeout: 48h
    timeout_action: escalate_to_admin
    
  CRITICAL:
    require_approve_from:
      - role: department_manager
      - count: 1
      - AND
      - role: enterprise_manager
      - count: 1
      - AND
      - role: compliance_officer
      - count: 1
    timeout: 72h
    timeout_action: deny
    require_evidence: true
    require_reason: true
Per-tenant override possible (vd: financial company yêu cầu 2 approvers cho HIGH).
## 8.3 Approval UI Workflow
1. Workflow triggered → enters PENDING_APPROVAL state
2. System fans out approval request to required approvers via:
   - In-app notification
   - Email
   - Slack (if configured)
3. Each approver sees:
   - What workflow does (plain language)
   - Risk class + reasoning
   - Top 3 affected entities
   - Estimated impact (cost, count, scope)
   - Approve / Reject / Request more info buttons
   - Mandatory reason field for Reject
4. Once required approvers respond:
   - All approve → execute
   - Any reject → cancel + notify originator
   - Timeout → action per policy
## 8.4 Blast Radius Pre-Check
Before execute, run blast radius simulation:
def simulate_blast_radius(workflow_id, dry_run=True):
    """
    Returns affected entities + downstream impact estimate
    """
    affected = {
        'entities_count': N,
        'entities_sample': [...first 10 entity IDs],
        'cost_estimate_vnd': X,
        'downstream_workflows': [list of dependent workflows],
        'reversibility_score': 0-1,  # 1 = easily reversible
        'risk_score': 0-100
    }
    return affected
UI shows simulation before execute — user sees: “If you run this, 1,247 customer records will be updated. 3 downstream workflows will be triggered. Estimated cost: 15M VND voucher campaign.”
## 8.5 Rollback Capability
Per workflow, define rollback strategy at creation:
workflow:
  rollback:
    available: true
    strategy: 'inverse_action'  # generate inverse SQL/API calls
    window: 24h  # within how long can rollback
    requires_approval: same as forward (for HIGH/CRITICAL)
    audit: full inverse action log
Rollback button visible 24h after run for HIGH/CRITICAL workflows.

# Phần 9. Pricing-Based Quotas Matrix
Cốt lõi: Mọi limit phải transparent, customer thấy được trong /p2/subscription real-time. Quota workflow runs/active, KHÔNG hạn chế workflow mapped (visibility comprehensive).
## 9.1 Storage & Files

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Total storage | 5 GB | 50 GB | 500 GB | 5 TB |
| Max file size single upload | 100 MB | 500 MB | 2 GB | 10 GB |
| Max files total | 100 | 1,000 | 10,000 | Unlimited |
| Departments (folders) | 1 | 5 | 20 | Unlimited |
| Files per department | 100 | 200 | 500 | Unlimited |
| Storage retention | 6 months | 1 year | 2 years | 2+ years configurable |
| Soft-delete restore window | 7 days | 30 days | 60 days | 90 days |

## 9.2 Users & Departments

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Total users | 3 | 5 | 20 | Unlimited |
| Departments | 1 | 5 | 20 | Unlimited |
| Roles available | Manager only | M+O+V | M+O+A+V | All + custom |
| MFA optional | ✓ | ✓ | ✓ | Required |

## 9.3 Pipelines & Data Processing

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Pipelines active | 1 | 5 | 20 | Unlimited |
| Pipeline runs/month | 10 | 100 | 1,000 | Unlimited |
| Bronze→Silver scheduled | Manual only | Daily | Hourly | Real-time |
| Silver→Gold refresh | Manual | Daily | Hourly | Real-time |
| Auto Database Design | ✗ | 1 schema | 5 schemas | Unlimited |
| Schema migration wizard | ✗ | ✓ | ✓ | ✓ |
| Custom cleaning rules | 5 | 20 | 100 | Unlimited |

## 9.4 Reports

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Auto reports/month | 5 | 20 | 100 | Unlimited |
| Custom report templates | 0 | 3 | 15 | Unlimited |
| Report distribution channels | Email | Email + In-app | + Slack | + Webhook |
| Report export formats | PDF | PDF, Excel | + CSV, JSON | + Custom |
| Scheduled reports | ✗ | Weekly | Daily | Hourly |
| Multi-department aggregate | ✗ | ✗ | ✓ | ✓ |

## 9.5 Charts & Visualizations

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Chart types available | 6 (basic) | 30 | 100+ | All + custom |
| Dashboards | 1 | 3 | 10 | Unlimited |
| Real-time updates | ✗ | ✗ | ✓ | ✓ |
| Embed external | ✗ | ✗ | ✓ | ✓ |

## 9.6 AI & Insights

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Insights/month | 50 | 500 | 5,000 | Unlimited |
| Frameworks available | SWOT | + 6W2H | + Fishbone, MoM | All + custom |
| LLM tokens/month (Qwen) | 100k | 1M | 10M | Unlimited |
| LLM tokens/month (external) | ✗ | 50k | 500k | 5M (with masking) |
| Custom prompt tuning | ✗ | ✗ | ✗ | ✓ |
| Confidence threshold customizable | ✗ | ✗ | ✓ | ✓ |
| Knowledge base entries | ✗ | 10 | 100 | Unlimited |

## 9.7 Workflow

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Workflows mapped (visibility) | 5 | 20 | 100 | Unlimited |
| Workflows ACTIVE (running) | 1 | 5 | 20 | Unlimited |
| Max nodes per workflow | 5 | 10 | 30 | Unlimited |
| Max branches per workflow | 2 | 5 | 10 | Unlimited |
| Workflow runs/month | 10 | 100 | 1,000 | Unlimited |
| Parallel A/B testing | ✗ | 20% split | 50/50 | Configurable |
| Workflow versions retained | 1 | 3 | 10 | Unlimited |
| Auto rollback on regression | ✗ | ✓ | ✓ | ✓ |

Note: Visibility (mapped) khác Active (running). Customer có thể document tất cả workflow ở tier rẻ. Active workflow là gì AI thật sự đang optimize.
## 9.8 Decisions & Audit

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Decisions logged | All | All | All | All |
| Decision detail retention | 30 days | 1 year | 2 years | 2+ years |
| Override decisions | ✗ | ✓ | ✓ | ✓ |
| Audit log export | ✗ | CSV | CSV + JSON | + API access |
| Compliance evidence package | ✗ | ✗ | Quarterly | Monthly |

## 9.9 Studio (Phase 2+)

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Studio access | ✗ | ✗ | ✓ | ✓ |
| Customer data engineers | 0 | 0 | 2 | Unlimited |
| Customer data scientists | 0 | 0 | 1 | Unlimited |
| Custom model training | ✗ | ✗ | ✗ | ✓ |
| GPU compute hours/month | 0 | 0 | 0 | 100 |

## 9.10 Connectors (Integration)

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Active connectors | 1 (file upload only) | 3 | 10 | Unlimited |
| Connector sync frequency | Manual | Daily | Hourly | Real-time |
| Webhook receivers | ✗ | 1 | 5 | Unlimited |
| Custom connector | ✗ | ✗ | ✗ | ✓ |
| CDC support | ✗ | ✗ | ✗ | ✓ |

## 9.11 Quota Enforcement & Overage
Soft warning: 80% of quota → email + in-app banner
Hard warning: 95% of quota → email + in-app banner + suggest upgrade
Hit 100%:
  - Storage: Block new uploads, allow read
  - Reports: Block generation, allow view existing
  - Workflows: Block new, allow existing
  - LLM tokens: Block new generations, allow read
  - Insights: Block new, allow view existing
  
Overage (per plan, charged automatically):
  - Storage: +500,000 VND / 50GB / month
  - LLM tokens: +200,000 VND / 1M tokens
  - Workflow runs: +500,000 VND / 1,000 runs
  - Insights: +500,000 VND / 1,000 insights
  
ENT MAX: no hard cap, billed monthly với monthly review

# Phần 10. Studio Collaboration with Customer Data Team
(Phase 2+ feature, activation timing per archetype)
## 10.1 Studio Activation Timing per Archetype

| Archetype | Studio activation | Reason |
|---|---|---|
| 1. Data-Chaotic SME | Defer to month 4-5 | Họ chưa có ai dùng, sẽ overwhelm |
| 2. Ops-Driven Mid | D60+ if there’s ops analyst willing | Optional based on ops capability |
| 3. Data-Curious Growing | D30-45 | Họ wait cho này, accelerate |
| 4. Data-Mature Enterprise | D14 | Move up significantly — họ là power users từ đầu |
| 5. Compliance-Heavy Regulated | D76+ với compliance audit pass | Cannot bypass governance |

## 10.2 Studio Capabilities (per Plan)

| Capability | STUDIO_ANALYST (MID) | STUDIO_ADMIN (MAX) |
|---|---|---|
| View all data | ✓ | ✓ |
| Propose cleaning rules | ✓ | ✓ |
| Propose features | ✓ | ✓ |
| Propose workflows | ✓ | ✓ |
| Notebook environment | ✓ Read | ✓ Read + Write |
| Custom model training | ✗ | ✓ |
| Prompt tuning | ✗ | ✓ |
| GPU compute access | ✗ | 100h/month |
| Project ownership | ✗ | ✓ |

## 10.3 Cleaning Rule Collaboration Workflow
[Customer's data engineer] notices issue trong silver data:
  "Phone numbers có format không nhất quán - cần normalize"
  → Studio: New cleaning rule proposal
  → Define rule (regex hoặc LLM-assisted)
  → Test on sample 1000 records
  → See Before/After
  → Submit for approval

[Auto/Manual review]:
  Confidence ≥ 0.9 + low risk: auto-approve
  Otherwise: Kaori Studio Analyst review (24h SLA)

[Approved]: 
  - Rule active in next pipeline run
  - Audit log: who proposed, who approved, what changed
  - Reversible: rollback within 7 days

[Rejected]:
  - Reason logged
  - Customer can iterate or escalate
## 10.4 Workflow Proposal Workflow
[Customer Data Scientist] proposes new workflow:
  - Hypothesis: "If we add lead scoring before retention campaign..."
  - Build in Studio sandbox
  - Test on historical data (backtest)
  - Document: input, output, expected impact
  - Submit for approval

[Review by Manager + Kaori Studio Analyst]:
  - Validate methodology
  - Check resource cost
  - Approve for parallel test

[Deploy in EXPERIMENTAL_NEW status]:
  - Run parallel với existing workflow
  - 14 days minimum
  - Statistical significance check
  - Promote / Rollback
## 10.5 AI Co-pilot in Studio
Qwen-powered chat assistant trong Studio sidebar handles:

| Query type | Example |
|---|---|
| Data exploration | “Top 10 khách mua nhiều nhất Q1” → SQL + result |
| Feature suggestion | “Suggest features cho churn model F&B” → 15 ranked features |
| Code assist | “Tại sao đoạn này throw error?” → Debug + fix |
| Domain knowledge | “Best practice retention F&B Việt Nam?” → KB answer |
| SHAP explanation | “Tại sao customer X bị classify HIGH?” → Top factors VI |
| Hypothesis test | “Cohort A higher LTV than B?” → Statistical test result |


# Phần 11. Data Volume Management & Sync Architecture
## 11.1 Volume Forecasting per Tenant
Estimate cho retail SME điển hình ENT MID:

| Component | Volume/month | After 12 months |
|---|---|---|
| Bronze raw | 12-15 GB | 144-180 GB |
| Silver cleaned | 2-3 GB | 24-36 GB |
| Gold MV + cache | 200-500 MB | 2.4-6 GB |
| Indexes (KG, embeddings) | 500 MB - 1 GB | 6-12 GB |
| Audit + decision log | 1 GB | 12 GB |
| Total | ~20 GB/month | ~240 GB/year |

ENT MID quota = 500GB → đủ ~2 năm trước khi cần upgrade hoặc tier-out.
## 11.2 Storage Tiering Automatic
Bronze:
  hot      (0-90 ngày)    : S3 Standard
  warm     (90-365 ngày)  : S3 Standard-IA (52% cheaper)
  cold     (1-2 năm)      : S3 Glacier Instant (83% cheaper)
  archive  (>2 năm)       : S3 Glacier Deep (96% cheaper)
  delete   (>retention)   : Per tenant config

Silver:
  hot      (0-180 ngày)   : ClickHouse SSD
  cold     (>180 ngày)    : ClickHouse cold partitions on S3
  
Gold:
  Always hot (refresh daily)
  Old MVs dropped after 30 days
  
Embeddings:
  Always hot (small, fast retrieval critical)
## 11.3 Sync Architecture (4 Patterns)
### Pattern A: Push (webhook receiver)
[Khách POS hỗ trợ webhook] 
  → POST https://api.kaori.ai/v1/enterprise/{tenant_id}/ingest/event
     Headers: Authorization Bearer {ingest_token}
     Body: {event payload}
  → Kaori Ingest Service validate + write Bronze
  → Emit Kafka event
  → Real-time sync (≤1 second lag)
Phù hợp: HubSpot CRM, Shopify, Haravan, payment webhooks
### Pattern B: Pull (scheduled connector)
Cron: every 15 minutes / hourly / daily
  → Kaori Connector Worker call source API
  → Cursor-based incremental: WHERE modified_date > last_sync
  → Validate + transform to Bronze envelope
  → Write Bronze + emit event
Phù hợp: KiotViet, Sapo, MISA, Shopee, Lazada
### Pattern C: CDC (Change Data Capture)
[Khách's DB SQL Server / MySQL / Postgres]
  → Debezium CDC slot
  → Kafka Connect bridge to Kaori Kafka
  → Real-time stream Bronze
Phù hợp: ENT MID/MAX với DB on-premise (Bravo, Fast, custom systems)
### Pattern D: Batch File (CSV/SFTP)
[Customer drops file vào SFTP folder hoặc upload UI]
  → Kaori scheduled scanner
  → Write Bronze + emit event
Phù hợp: Legacy systems, weekly export
## 11.4 Initial Backfill Strategy
D5-D14: Initial data load. Cần chạy 2 chế độ song song:
Backfill mode: Pull historical data 6-24 months (size depends on plan)
Incremental mode: Start from D7, real-time sync going forward
### Backfill Sizing

| Plan | Max backfill window | Max backfill size |
|---|---|---|
| PILOT | 3 months | 5 GB |
| ENT BASIC | 6 months | 30 GB |
| ENT MID | 12 months | 200 GB |
| ENT MAX | 24+ months | 1 TB |

Backfill chạy theo priority queue, không impact production.
## 11.5 Schema Evolution Handling
Detection (auto):
  - Diff trên 100 records gần nhất
  - Detect: column added / removed / type changed / renamed

Severity classification:
  - Add column: LOW (auto-include in Bronze raw_payload)
  - Remove column: MEDIUM (alert if used in Silver/Gold)
  - Type change: HIGH (potential data loss)
  - Rename column: HIGH (need re-mapping)

Workflow:
  LOW → auto-handle, log
  MEDIUM/HIGH → alert customer Manager
                Open Schema Migration Wizard (Module 2.5b)
                Customer approves changes
                Apply with rollback option

# Phần 12. Enterprise Health State Machine
## 12.1 9 States Overview
PROSPECT → ONBOARDING → ACTIVATING → PROVING → EXPANDING → HEALTHY
              ↓              ↓           ↓          ↓
           STALLED       AT-RISK ←──────────────────┘
              ↓              ↓
          ABANDONED      CHURNING
## 12.2 Daily Health Computation
Cron daily 02:00 UTC+7:
def compute_health_score(enterprise_id):
    usage = compute_usage_score(enterprise_id)        # 25%
    value = compute_value_score(enterprise_id)        # 25%
    data = compute_data_score(enterprise_id)          # 20%
    support = compute_support_score(enterprise_id)    # 15%
    billing = compute_billing_score(enterprise_id)    # 15%
    
    total = (
        0.25 * usage + 
        0.25 * value + 
        0.20 * data + 
        0.15 * support + 
        0.15 * billing
    ) * 100
    
    # Determine state based on score + history
    new_state = determine_state(enterprise_id, total)
    
    # Update DB + trigger CSM if state changed
    update_health(enterprise_id, total, new_state)
## 12.3 Sub-Score Formulas
### Usage Score (0-1, weight 25%)
def compute_usage_score(eid):
    active_users_7d = count_distinct_users_with_login(eid, days=7)
    total_users = count_total_users(eid)
    user_active_rate = active_users_7d / total_users
    
    manager_logins_7d = count_manager_logins(eid, days=7)
    manager_score = min(1, manager_logins_7d / 3)
    
    active_days_30d = count_distinct_active_days(eid, days=30)
    active_days_score = active_days_30d / 30
    
    return 0.4 * user_active_rate + 0.3 * manager_score + 0.3 * active_days_score
### Value Score (0-1, weight 25%)
def compute_value_score(eid):
    total_predictions = count_predictions(eid, days=30)
    actioned = count_actioned_predictions(eid, days=30)
    is_actioned_rate = actioned / max(total_predictions, 1)
    
    rev_at_risk_actioned = sum_revenue_at_risk_actioned(eid, days=30)
    rev_score = min(1, rev_at_risk_actioned / 10_000_000)  # 10M VND target
    
    insights_generated = count_insights(eid, days=30)
    insights_viewed = count_insights_viewed(eid, days=30)
    view_rate = insights_viewed / max(insights_generated, 1)
    
    return 0.5 * is_actioned_rate + 0.3 * rev_score + 0.2 * view_rate
### Data Score (0-1, weight 20%)
def compute_data_score(eid):
    pipeline_runs = count_pipeline_runs(eid, days=30)
    pipeline_success = count_successful_runs(eid, days=30)
    success_rate = pipeline_success / max(pipeline_runs, 1)
    
    last_data_upload = days_since_last_upload(eid)
    staleness_score = max(0, 1 - last_data_upload / 14)
    
    quality_score = avg_data_quality_score(eid, days=30) / 100
    
    return 0.5 * success_rate + 0.3 * staleness_score + 0.2 * quality_score
### Support Score (0-1, weight 15%)
def compute_support_score(eid):
    p1_tickets = count_p1_tickets(eid, days=30)
    ticket_score = max(0, 1 - p1_tickets / 5)
    
    nps = latest_nps(eid)
    nps_score = nps / 10 if nps else 0.7
    
    avg_response = avg_csm_response_hours(eid, days=30)
    response_score = max(0, 1 - avg_response / 24)
    
    return 0.5 * ticket_score + 0.3 * nps_score + 0.2 * response_score
### Billing Score (0-1, weight 15%)
def compute_billing_score(eid):
    days_until_breach = estimate_days_until_quota_breach(eid)
    quota_score = min(1, days_until_breach / 30)
    
    payment_on_time = payment_on_time_rate(eid, months=6)
    
    overage_volatility = std_dev(monthly_overage(eid, months=6))
    overage_score = 1 - min(1, overage_volatility / mean_overage(eid))
    
    return 0.5 * quota_score + 0.3 * payment_on_time + 0.2 * overage_score
## 12.4 State Transition Thresholds
>= 80 trong 30 ngày liên tiếp → HEALTHY
60-79 → EXPANDING/PROVING (theo thời gian)
40-59 → AT-RISK
< 40 14 ngày → CHURNING risk
Per-archetype adjustment: - Archetype 1 (Chaotic SME): Lower bar — ≥70 là HEALTHY - Archetype 4 (Enterprise): Higher bar — ≥85 là HEALTHY - Archetype 5 (Regulated): Different weight — governance metrics weighted higher
## 12.5 State Definitions + Transitions

| State | Definition | Trigger to next state | CSM Intervention |
|---|---|---|---|
| PROSPECT | Pre-contract | Sign contract → ONBOARDING | Sales-led |
| ONBOARDING | D1-7 | Pipeline run successful → ACTIVATING; D7 failure → STALLED | CSM intensive |
| STALLED | Stuck >7d in onboarding | Recover → ACTIVATING; >21d → ABANDONED | Personal call mandatory |
| ABANDONED | >21d no activity | Customer-initiated re-engagement → ACTIVATING | Quarterly outreach only |
| ACTIVATING | D8-30 | First “Đã xử lý” → PROVING; D30 zero action → AT-RISK | First Win playbook |
| PROVING | D31-60 | ≥10 actions/month → EXPANDING; action <5/mo → AT-RISK | Weekly business review |
| EXPANDING | D61-90 | All 4 health checks 30d → HEALTHY; drop <60 → AT-RISK | Upsell preparation |
| HEALTHY | D90+ | Drop <60 14d → AT-RISK | Quarterly QBR |
| AT-RISK | Health drop signs | Recover 30d → HEALTHY; cancel/30d zero login → CHURNING | Executive escalation |
| CHURNING | Cancel request OR 30d inactive | Reactivate <60d → ACTIVATING (recovered tag); >60d → off-platform | Exit interview mandatory |

## 12.6 Customer-facing Health Dashboard (Module 2.3a)
Health score trend (90 day chart)
5 sub-scores radar chart
Action items để improve score
Comparison to similar customers (anonymized)
Trajectory prediction
## 12.7 Kaori-side Platform Admin View (Module 1.9)
All enterprises listed với current state + health score
Filter: by state, by health trend, by plan
Alerts: state transitions, health drops, ticket surges
CSM workflow: which to call today, intervention playbook
Cohort analysis: signup month vs retention curve

# Phần 13. Economic Model & Cost-to-Serve
Mục đích: v1 + v2 đã establish customer success. Phần này establish business viability. Without unit economics, scale → death.
## 13.1 Per-Tenant Cost Components

| Cost component | Driver | Phase 1 estimate (ENT MID) | Phase 3 estimate |
|---|---|---|---|
| CSM hours | Onboarding + ongoing support | 60h × 500K = 30M | 25h × 500K = 12.5M |
| Implementation Eng hours | Data setup, custom cleaning | 40h × 800K = 32M | 12h × 800K = 9.6M |
| AI inference cost | LLM tokens (Qwen + external) | ~3M VND/tháng | ~2M/tháng |
| Storage cost | Bronze + Silver + Gold + indexes | ~500K/tháng | ~300K/tháng (with tiering) |
| Compute (non-AI) | Pipeline runs, MV refresh | ~1M/tháng | ~500K/tháng |
| Support cost | P1/P2 tickets resolution | ~2M/tháng | ~500K/tháng |

## 13.2 Onboarding Cost vs Subscription Math
ENT MID at 5M VND/month subscription:

| Period | Revenue | Cost | Margin |
|---|---|---|---|
| Month 1 (heavy onboarding) | 5M | 30M (CSM) + 32M (Impl) + 6M (infra) = 68M | -63M |
| Month 2 | 5M | 12M (still onboarding) + 6M = 18M | -13M |
| Month 3 | 5M | 6M (steady state) + 6M = 12M | -7M |
| Month 4 | 5M | 6M | -1M |
| Month 5+ | 5M | 6M | -1M ⚠️ |
| Month 12 | 5M | 4M (efficiency) | +1M |

Implication: ENT MID không profitable Phase 1. Profitable từ tháng 12+ với operational efficiency.
Decision matrix: - Phase 1: Subsidize ENT MID acceptable (acquiring logos) - Phase 2: Must reach +5M margin/tenant/month, else raise prices or cut costs - Phase 3: Target +10M margin/tenant/month for ENT MID
## 13.3 CSM Capacity Planning

| CSM seniority | Max concurrent tenants | Revenue managed | Capacity at full load |
|---|---|---|---|
| Junior CSM (year 1) | 5 | ~25M MRR | Onboarding new only |
| Mid CSM (year 2-3) | 12 | ~80M MRR | Mix new + steady |
| Senior CSM (year 3+) | 20 | ~150M MRR | Strategic accounts only |

Phase 1 staffing math: - Target 25 paying enterprises by end of Phase 2 - Mix: 5 in onboarding (Junior load), 20 in steady (Mid load × 2 CSMs) - Total CSM headcount: 1 Junior + 2 Mid = 3 FTE - Cost: ~1B VND/year fully loaded
## 13.4 Unit Economics KPIs (track from Phase 1)

| KPI | Definition | Target Phase 1 | Target Phase 3 |
|---|---|---|---|
| CAC (Customer Acquisition Cost) | Sales + marketing / new customer | <30M VND | <15M |
| LTV (Lifetime Value) | Avg monthly revenue × avg lifetime months | >100M | >300M |
| LTV:CAC ratio | LTV / CAC | >3:1 | >5:1 |
| Payback period | Months until cumulative GM = CAC | <18 months | <9 months |
| Net Revenue Retention | (Start MRR + expansion - churn) / Start MRR | >100% | >120% |
| Gross Margin per tenant | (Revenue - direct cost) / Revenue | >40% | >65% |
| CSM:tenant ratio | # tenants / # CSMs | 5:1 | 20:1 |

## 13.5 Per-Archetype Pricing Implications

| Archetype | Best plan match | Margin profile | Decision |
|---|---|---|---|
| 1 SME | PILOT → ENT BASIC | Negative early, breakeven 12+ months | Subsidize Phase 1, premium pricing or kept lean |
| 2 Mid-market | ENT BASIC → MID | +20-30% margin | Sweet spot, scale |
| 3 Growing | ENT MID | +40% margin (best) | Self-service efficient |
| 4 Enterprise | ENT MAX → ROI Hybrid | +50% margin if priced right | Custom needs |
| 5 Regulated | ENT MAX + custom | +30% margin (high cost-to-serve) | Premium for compliance |

Implication: Sales should NOT push ENT MAX to Archetype 1. Cost-to-serve will exceed revenue.

# Phần 14. Special Domain Supplements
Mục đích: 90-day playbook generic fits Archetype 1-4 + Retail/Logistics/Manufacturing/E-com/Real Estate/Education. Special domains (Bank, Healthcare, Government) cần additional supplements ON TOP of baseline.
## 14.1 Banking / Financial Services Supplement
### What’s different from baseline

| Aspect | Baseline | Banking Supplement |
|---|---|---|
| Pre-launch | D-7 to D0 | D-21 to D0 — 2-week legal/compliance review |
| Data residency | Configurable | Mandatory VN-only Phase 1; dedicated cluster Phase 2-3 |
| First data | Production data | Sandbox/anonymized data only until D45 |
| AI auto-action | Allowed for ENT MAX | Never — all decisions require human approval |
| Audit retention | 2 years | 7 years minimum (Basel III) |
| Approval graph | 3-tier max | 4-tier (add Compliance Officer + Risk Committee) |
| PII handling | Standard masking | Tokenization mandatory + strong cryptography |
| Audit log | Standard | Regulator-accessible audit trail |
| Studio access | D75+ | After compliance audit pass (D90+) |

### Additional modules required

| Module | Purpose |
|---|---|
| 14.1.1 Basel III Compliance Pack | Documentation tự động cho Pillar 1/2/3 |
| 14.1.2 AML/KYC Integration | Real-time fraud + sanctions screening |
| 14.1.3 Credit Decisioning Audit | Every credit decision có full reasoning trace |
| 14.1.4 Regulatory Reporting | Automated reports cho NHNN |

### Wedge canonical
Credit risk scoring OR Fraud detection — both are revenue + compliance positive
### Pricing
Minimum plan: ENT MAX
Implementation fee separate (50-200M VND one-time)
Annual contract minimum
### Discovery questionnaire additions
Q: Which regulator(s)? (NHNN, BIS, SEC equivalent)
Q: Production timeline target post-implementation?
Q: Data localization requirement?
Q: Existing core banking system?
Q: Audit firm & timeline?
## 14.2 Healthcare Supplement
### What’s different from baseline

| Aspect | Baseline | Healthcare Supplement |
|---|---|---|
| Pre-launch | D-7 to D0 | D-30 to D0 — 4-week patient privacy assessment |
| Data residency | Configurable | Mandatory VN-only, no cross-border ever |
| First data | Production data | De-identified data only until ethics approval |
| AI auto-action | Allowed | Never for clinical decisions; admin OK |
| Audit retention | 2 years | 6+ years (medical records standard) |
| Approval graph | 3-tier max | 5-tier (add Medical Director + Privacy Officer) |
| PII handling | Standard masking | De-identification + ethics review per use case |
| Patient consent | Implicit | Explicit per data use required |

### Additional modules required

| Module | Purpose |
|---|---|
| 14.2.1 Patient Privacy Engine | De-identification + re-identification risk scoring |
| 14.2.2 Clinical Decision Support Audit | Every clinical recommendation logged + reviewed |
| 14.2.3 Ethics Review Workflow | Per-use-case approval before data access |
| 14.2.4 Medical Coding | ICD-10, CPT, SNOMED CT integration |

### Wedge canonical
No-show prediction OR Readmission risk — operational, lower clinical risk
### Specific schemas
healthcare.patient_encounter
  patient_id_hashed     STRING (NEVER raw, always hashed)
  encounter_id          STRING
  encounter_date        date  
  encounter_type        enum
  diagnosis_code        ICD-10
  procedure_code        CPT
  provider_id           string
  age_bucket            string (NEVER exact age)
  gender                enum (M/F/O)
  outcome_code          ICD-10 outcome
### Pricing
Minimum plan: ENT MAX
Ethics review setup fee (50-150M VND)
Per-clinical-use-case approval fee
Slower deployment timeline expected
### Discovery additions
Q: Patient consent mechanism existing?
Q: IRB/Ethics committee?
Q: De-identification already done?
Q: HIS/EHR system integration?
Q: Clinical vs administrative use cases?
## 14.3 Government / Public Sector Supplement
### What’s different from baseline

| Aspect | Baseline | Government Supplement |
|---|---|---|
| Procurement | Direct sales | Public procurement process (often months) |
| Pre-launch | D-7 to D0 | D-60 to D0 — security clearance + procurement |
| Data residency | Configurable | Always VN-only, often dedicated infrastructure |
| Transparency | Internal | Public reporting requirements in many cases |
| AI auto-action | Allowed | Subject to public administration laws |
| Audit retention | 2 years | Per government archive policy (often 10+ years) |
| Approval graph | 3-tier max | Mapped to government org structure |

### Additional modules required

| Module | Purpose |
|---|---|
| 14.3.1 Public Procurement Compliance | Documentation matching Luật Đấu thầu |
| 14.3.2 Public Records Integration | If applicable |
| 14.3.3 Transparency Report Builder | Public reporting where required |
| 14.3.4 Citizen Privacy Pack | Stricter than business PII |

### Wedge canonical (varies by agency type)
Tax authority: Tax compliance scoring
Customs: Risk-based inspection routing
Health ministry: Service request triage
Education ministry: School performance analytics
### Pricing
Government rate cards (often standardized)
Procurement timeline: 3-12 months
Implementation fee separate
## 14.4 Framework: Adding More Special Domains
Các domain mới có thể cần supplement nếu match ≥2 criteria sau:
Regulatory specific (Basel, HIPAA, FERPA, SOX, etc.)
Mandatory data residency beyond commercial standard
Auto-action restrictions (clinical, legal, financial decisions)
Audit retention beyond 2-year standard
Approval workflow beyond 3-tier
Procurement process beyond direct sales
### Template per new domain supplement:
## 14.X [Domain Name] Supplement

### What's different from baseline
[Table comparing baseline vs special]

### Additional modules required
[List with purposes]

### Wedge canonical
[The 1 use case to focus on]

### Specific schemas
[Domain-specific table structures]

### Pricing
[Plan minimum + implementation fee]

### Discovery additions
[Domain-specific questions]

### State machine adjustments
[How health score changes weights]

### Timeline adjustments  
[Specific phase extensions]

# Phần 15. Templates Library
## 15.1 Welcome Email Template (D1)
Subject: Chào mừng [Customer Name] đến với Kaori AI! 🎉

Xin chào [Customer Manager],

Hành trình 90 ngày với Kaori bắt đầu từ hôm nay!

🔑 THÔNG TIN ĐĂNG NHẬP
Workspace: https://[subdomain].kaori.ai
Username: [email]
Temporary password: [auto-gen]
Private Key: [KAORI-XXXX-XXXX-XXXX] (đã gửi qua SMS)

📅 LỊCH HẸN ĐÃ ĐẶT
Hôm nay (D1): Onboarding call 60 phút - 14:00
Tuần này: Setup workspace + upload dữ liệu đầu tiên
D7: Check-in - first pipeline run
D30: Review tháng 1 - first insights & ROI

🎯 WEDGE FOCUS 90 NGÀY
Trong 90 ngày, focus chính sẽ là [WEDGE]. Còn lại sẽ map để
quan sát và optimize sau. Tham khảo tài liệu Wedge Brief
attached để hiểu cụ thể.

📚 TÀI LIỆU
- Welcome PDF: [link]
- Video onboarding 15 phút: [link]
- Knowledge Base: https://help.kaori.ai

🚀 CSM của bạn
Tên: [CSM Name]
Email: [email]
Mobile: [phone] / Zalo
Slack channel: #[customer-name]-kaori

Có câu hỏi? Reply email hoặc nhắn Zalo trực tiếp.

Best,
[CSM Name]
Customer Success Manager, Kaori AI
## 15.2 D1 Onboarding Call Agenda (60 phút)
0-5  | Welcome + tự giới thiệu (CSM)
5-10 | Mục tiêu cuộc gọi + 90 ngày tổng quan
10-25| Walk through P2 dashboard
     - Login first time
     - Branding setup
     - Department concept demo
25-40| Department setup workshop
     - Confirm list từ discovery
     - Assign Manager mỗi department
     - Allocate quotas
40-50| Data upload preview + Wedge brief
     - Demo wizard 5 bước
     - Discuss what data they'll upload first
     - Why wedge focus matters
50-55| Q&A
55-60| Next steps + action items
## 15.3 D30 Review Template
KAORI 30-DAY REVIEW — [Customer Name]
Date: [date]
Attendees: [list]

📊 HEALTH SCORE: [score]/100 — State: [state]

🎯 GOALS HIT (out of D30 targets):
□ Workspace + departments setup
□ ≥1 data source connected
□ Bronze→Silver→Gold pipeline E2E
□ ≥1 insight generated với confidence ≥0.6
□ ≥1 "Đã xử lý" action

💡 KEY INSIGHTS GENERATED:
1. [Insight 1] — Customer reaction: [actioned/dismissed]
2. [Insight 2] — ...

📈 ROI INDICATORS:
- Revenue at risk identified: [VND]
- Revenue actioned: [VND]
- Time saved on reporting: [hours]

⚠️ ISSUES:
- [Issue 1] — Mitigation: [...]

🎯 NEXT 30 DAYS PLAN:
- Workflow mapping (all depts visibility)
- Wedge workflow optimization analysis
- [Other actions]

Owner sign-off: ___________
## 15.4 D60 Mid-Cycle Review Agenda (90 phút)
0-15 | Health score & state recap (CSM)
15-30| ROI realized 60 days vs projected (CSM + Customer PM)
30-50| AI insights performance:
     - Accuracy on labeled outcomes
     - Action conversion rate
     - Calibration drift check
     - User satisfaction (NPS)
50-70| Workflow optimization recommendations
     - Walk through AI suggestions
     - Discuss feasibility
70-85| Decisions:
     - Approve which experimental workflows to test parallel?
     - Studio activation timing? (per archetype)
     - Plan upgrade/maintain?
85-90| Action items + next 30 days
## 15.5 D90 Final Review Agenda (2 giờ)
0-15 | 90-day metrics deep dive (CSM)
15-30| Health score journey + state transitions
30-50| Workflow optimization results:
     - Win/loss/draw per workflow tested
     - Statistical significance
50-70| Studio adoption (if activated)
     - Customer team capability assessment
     - Continued support needed?
70-90| Pain points & feedback (open mic)
     - What worked
     - What didn't
     - Wishes for product roadmap
90-110| Next 90 days plan
     - Quarterly Business Review cadence
     - Goals & KPIs
     - Resource needs
     - Wedge expansion (next workflow target)
110-120| Pricing review (AE)
       - Maintain / upgrade / downgrade decision
       - Annual commitment discussion
## 15.6 Domain Data Upload Checklist (Retail example)
PRE-UPLOAD CHECKLIST — Retail
□ Đã export từ POS chính (KiotViet/Sapo/...)
□ Format: CSV UTF-8 (KHÔNG dùng Excel default Win-1258)
□ Bao gồm cột:
  ☑ customer_id (mã KH cố định)
  ☑ transaction_id  
  ☑ transaction_date (yyyy-mm-dd hoặc dd/mm/yyyy)
  ☑ amount (VND, không dấu phẩy)
  ☑ product_name hoặc product_id
  ☑ store_id hoặc channel
□ ≥500 records
□ ≥3 tháng history
□ File size: <500MB (BASIC), <2GB (MID), <10GB (MAX)

OPTIONAL (cho better insights):
□ payment_method
□ promotion_code
□ staff_id (nếu in-store)
□ customer phone (sẽ được masked auto)
□ city/region
□ review_score
□ return information
## 15.7 CSM Daily Playbook Checklist
Each morning, CSM reviews:
□ Health Dashboard cho tất cả assigned enterprises
□ Identify state changes overnight
□ Identify health score drops >10pp
□ Check support ticket queue
□ Review scheduled calls today
□ Check workflow approvals pending (CSM may need to nudge)

For each enterprise in concerning state:
□ Read latest activity log
□ Check last login
□ Check last action taken
□ Determine intervention type:
  - Slack ping (low touch)
  - Email check-in (medium touch)
  - Schedule call (high touch)
  - Escalate to AE (executive level)
## 15.8 Wedge Brief Template (1 page, given to customer D1)
═══════════════════════════════════════════════════════
  WEDGE FOCUS 90 NGÀY — [Customer Name]
═══════════════════════════════════════════════════════

🎯 WEDGE: [e.g., "Churn retention cho khách VIP"]

WHY THIS WEDGE:
[2-3 sentences explaining ROI rationale, why this 
specific use case]

EXPECTED OUTCOMES (90 days):
- [Metric 1, e.g., "Phát hiện ≥200 khách HIGH risk/tháng"]
- [Metric 2, e.g., "Recover ≥50M VND revenue at risk"]
- [Metric 3, e.g., "1 retention workflow optimized"]

WHAT WE'LL ALSO DO (visibility, not active):
- Map all departments + their workflows
- Bronze/Silver/Gold cho all data sources
- Insights generated cho all departments

NEXT WEDGES (Quarter 2+):
- [e.g., Inventory optimization]
- [e.g., Cross-sell campaigns]
- [...]

90-DAY MILESTONES YOU'LL SEE:
- D7: First pipeline run on your data
- D30: First "Đã xử lý" action proven
- D60: Workflow optimization recommended
- D90: New workflow validated, expansion plan

CSM: [Name] | [Contact]
═══════════════════════════════════════════════════════

# Phần 16. Critical Success Factors & Anti-patterns
## 16.1 What Works (Do This)
✅ D1 onboarding call mandatory — không được skip. Customer setup mà không guidance D1 → 47% fail by D14.
✅ Department-by-department rollout for Archetype 1-2 — không phải all-at-once. Pick 1-2 critical departments first, prove value, then expand.
✅ First “Đã xử lý” by D30 — push hard. Đây là single most predictive metric của 90-day success.
✅ Mid-cycle review D60 mandatory — even if customer says “not needed”. This is reset point.
✅ Studio onboarding timing per archetype — Data-Mature D14, Data-Curious D30, Mid-market D60, Chaotic SME defer to month 4-5.
✅ Comprehensive visibility, incremental change — map all workflows, optimize 1 wedge per quarter.
✅ Wedge canonical per domain — sales pitch specific use case, not “platform”. Customer can’t visualize “platform”; they can visualize “stop losing 234 VIP customers/month”.
✅ Calibration UI display — show “Confidence 73% (calibrated within ±5%)” not just “73%”. Earn trust through transparency.
## 16.2 What Doesn’t Work (Avoid)
❌ Pushing analytical breadth — “wow look at all 100 chart types” → overwhelms. Show 3-5 essential charts that solve their problem first.
❌ All workflows AI-suggested at once D60 — pick 1 most impactful, prove ROI, expand later.
❌ Treating all customers same playbook — adjust for archetype. Retail SME 50 staff khác Finance enterprise 500 staff.
❌ Hiding confidence numbers — customers think AI is 100% if you don’t show. Always display.
❌ Promising auto-pilot Phase 1 — over-promise → under-deliver. Phase 1 = co-pilot with human-in-loop.
❌ Skip data quality investment D7-14 — biggest single point of failure. Bad data = bad outputs forever.
❌ Pushing ENT MAX to Archetype 1 (Chaotic SME) — cost-to-serve will exceed revenue. They need PILOT or ENT BASIC.
❌ Replacing workflows instead of running parallel — change management capacity is finite. Old + New parallel mandatory until proven.
❌ Ignoring approval graph for HIGH/CRITICAL workflows — when AI is wrong, “who blocks?” is the question. Disclaimer alone is insufficient.
## 16.3 Red Flags During Deployment

| Red flag | Day | Action |
|---|---|---|
| No login >3 days post D1 | D4 | Personal call mandatory |
| Data quality score <40 D14 | D14 | Implementation Eng dedicated session |
| 0 actions D30 | D30 | Executive escalation |
| Health score drop >15pp in 7d | Anytime | Same-day call |
| Manager hasn’t logged in 14d | D45+ | Sponsor escalation |
| Workflow proposals rejected 3x | D60+ | Methodology review |
| Tenant cost > revenue 3 months in row | Anytime | Pricing review or operational efficiency sprint |
| Calibration drift ECE > 0.15 | Anytime | ML team alert + recalibration |

## 16.4 90-Day Success Definition
Mỗi tuần có 1 mục tiêu chính:
W1: Họ login & tin tưởng platform
W2: Họ thấy data của mình "sạch" — first time
W3: Họ thấy insight đầu tiên — "ồ thực ra business như vậy"
W4: Họ làm action đầu tiên — first ROI realized
W5-6: Họ map workflow current — hiểu rõ "as-is" của business
W7-8: Họ thấy AI suggest improvement — "có thể tốt hơn"
W9-10: Họ thử workflow mới — risk taking với confidence  
W11: Họ so sánh kết quả — data-driven decision
W12: Họ tự lái — Studio active (per archetype), team có quyền propose
90 ngày sau, customer có 3 thay đổi căn bản:
Habit thay đổi: từ “report 2 tuần 1 lần” → “dashboard mở mỗi sáng”
Decision style thay đổi: từ “intuition” → “intuition + data verification”
Team capability thay đổi: từ “dependent on Kaori” → “self-service với Kaori support”
Đây là organizational transformation thật. Không phải tool sale.

# Tóm tắt — Hành trình 1 Customer
PROSPECT (D-7)
    ↓ archetype detected, wedge canonical chosen
ONBOARDING (D1)
    ↓ workspace + departments + first upload
ACTIVATING (D8-30)
    ↓ Bronze→Silver→Gold + first insight + first action
PROVING (D31-60)
    ↓ all workflows mapped (visibility) + wedge analyzed (active)
EXPANDING (D61-90)
    ↓ parallel run + Studio activated (per archetype) + new workflow validated
HEALTHY (D90+)
    ↓ QBR cadence, expansion to 2nd wedge planned
90 ngày = wedge proven + platform operational + team activated. Sau đó: - Quarter 2: Expand to 2nd wedge - Quarter 3-4: 3rd wedge, deeper Studio adoption - Year 2: Mature operation, possible ROI Hybrid pricing - Year 3+: Strategic partner, multi-vertical expansion possible

Tài liệu này là Playbook v3.0 — comprehensive baseline cho mọi doanh nghiệp. Special domains (Bank, Healthcare, Government) có supplements ở Phần 14. Bất kỳ vertical mới nào cũng có thể add supplement theo template Phần 14.4.
Sẽ iterate sau mỗi 5 customer onboarding hoàn thành — measure what works, what fails, refine.