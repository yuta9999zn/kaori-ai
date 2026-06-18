# REVIEW NOTES — Code Repo `D:\Kaori System\`
## Danh sách chỉnh sửa cho dev-facing artefacts để đồng bộ với BA Documentation v2

| Hạng mục | Thông tin |
|---|---|
| Tài liệu | Review Notes for Code Repo |
| Phiên bản | 1.0 (2026-05-20) |
| Audience | Tech Lead · Engineering · QA Lead · UX |
| Mục đích | Liệt kê **file dev-facing trong code repo cần chỉnh sửa** sau khi BA docs đã update v2 + Feature Tree v4.1 |
| Phạm vi | `D:\Kaori System\docs\` và các artefact spec-quality liên quan |
| Nguồn phát hiện | (a) Đối chiếu chéo BA docs v2 ↔ pointer files 3.3/3.4/3.5/3.6 (b) Review 3 HTML files: feature-screens, feature-workflows, workflow-builder-ux (c) Excel v4.1 Issues Found sheet |

---

## 0. Tóm tắt — 7 nhóm fix cần làm

| # | Nhóm | File chính | Ưu tiên | Effort ước |
|---|---|---|---|---|
| 1 | UI Screens Inventory — title/portal/CS gap | `docs/specs/UI_SCREENS_INVENTORY.md` + 3 HTML | 🔴 HIGH | 4–6h |
| 2 | OpenAPI snapshot regen + SLA per endpoint | `docs/api-specs/*.openapi.json` + `API_CATALOG_V4.md` | 🔴 HIGH | 1–2 ngày |
| 3 | Medallion Contract — làm rõ Silver | `docs/specs/MEDALLION_CONTRACT.md` | 🟠 MED | 2h |
| 4 | UAT scripts thiếu Phase 2.5/2.6/2.7 | `docs/uat/` | 🟠 MED | 1 tuần |
| 5 | Validation rules per field — chưa đầy đủ | `docs/specs/VALIDATION_RULES.md` | 🟡 LOW | 3 ngày |
| 6 | Message Definitions — tiếng Việt + RFC 7807 | `docs/specs/MESSAGE_DEFINITIONS.md` | 🟡 LOW | 2 ngày |
| 7 | Chat Tool Registry — đồng bộ MCP | `docs/specs/CHAT_TOOL_REGISTRY_V4.md` | 🟡 LOW | 4h |

Tổng effort ước: **~2–3 tuần dev/QA/UX combined**.

---

## 1. 🔴 HIGH — `docs/specs/UI_SCREENS_INVENTORY.md` + 3 HTML file

### 1.1 Bối cảnh
Khi review `feature-screens.html`, `feature-workflows.html`, `workflow-builder-ux.html` đã phát hiện:
- **Title "72 màn hình · 6 portals"** không khớp Navigation IA (chỉ liệt kê **62 màn / 4 portal**: P1=16, P2=32, P3=8, P4=6).
- **P5 Shared, P6 Billing không có screen ID format P5-/P6-** — chỉ là section.
- **Customer Service vertical**: workflows có 5 CS workflow (D.1–D.5), feature-screens chỉ 4 mention CS (gần như không có screen CS-specific).
- **Cross-link asymmetric**: `feature-screens` link tới `workflow-builder-ux` 7 lần nhưng **0 link** tới `feature-workflows`.
- **3-Mode UI (SIMPLE/ADVANCED/DEVELOPER)** dùng 18× trong `workflow-builder-ux`, 5× trong `feature-screens`, **0× trong `feature-workflows`**.
- **Card format 7-field chuẩn** (Owner/Input/Required docs/AI action/Branch/Output/SLA — chốt 2026-05-20) không apply đồng đều trong workflows catalog.
- **CSS `--shadow` token lệch nhẹ** giữa wf-builder và 2 file kia.
- **Date inconsistency**: feature-screens có cả 2026-05-15 và 2026-05-20.
- **workflow-builder-ux** bắt đầu từ `<h2>` (không có `<h1>`) — accessibility issue.
- **Glossary**: chỉ feature-workflows có (~12 từ, quá ngắn). 2 file kia không có.

### 1.2 Action cần làm

**A. `docs/specs/UI_SCREENS_INVENTORY.md`** (canonical):
- [ ] Verify đúng số screen thực tế và đồng bộ với 3 HTML. Nếu là 70 screen (per 3.3 pointer hiện tại), cần thêm:
  - 5 screen P5 Shared (vd P5-01 LLM Gateway · P5-02 PII Masker Config · P5-03 Event Stream · P5-04 Workflow Engine Console · P5-05 Audit Log)
  - 5 screen P6 Billing (vd P6-01 Subscription · P6-02 Invoice History · P6-03 Payment Methods · P6-04 e-Invoice Settings · P6-05 Quota Usage)
- [ ] Bổ sung Customer Service vertical screens (vd P2-29 CS Inbox · P2-30 Ticket Detail · P2-31 NPS Dashboard) để khớp 5 workflow D.1–D.5.
- [ ] Mỗi screen gắn metadata: `mode: SIMPLE | ADVANCED | DEVELOPER`, `plan_gate: PILOT | BASIC | MID | MAX`, `audience: Business | Internal`.

**B. `feature-screens.html`**:
- [ ] Sửa title: `"72 màn hình · 6 portals"` → đúng số thực (hoặc bổ sung đủ 72).
- [ ] Thêm 7 link tới `feature-workflows.html#X.Y` từ các screen P2-26 (Workflow Builder), P2-27 (Workflow Testing), P2-28 (Process Mining).
- [ ] Thống nhất date: chỉ giữ `2026-05-20 EOD`; tham chiếu `2026-05-15` đánh dấu `(history)`.
- [ ] Bổ sung 3-Mode UI badge cho từng screen — match với UI_SCREENS_INVENTORY.

**C. `feature-workflows.html`**:
- [ ] Thêm cột `mode` và `plan_gate` per workflow → khớp 3-Mode taxonomy.
- [ ] Mở rộng Glossary (~12 từ hiện tại → 30–50 từ) cho thuật ngữ chung: bootstrap, template, card, branch, mode, region, vertical, wedge.
- [ ] Áp dụng card format 7-field hoặc tách rõ "workflow-level fields" (Trigger/SLA/Owner workflow) vs "card-level fields" (7-field).
- [ ] Thêm cross-link tới `workflow-builder-ux.html` per workflow.

**D. `workflow-builder-ux.html`**:
- [ ] Thêm `<h1>Kaori AI — Workflow Builder UX Mockup</h1>` ở đầu (hiện bắt đầu từ `<h2>`).
- [ ] Thêm 4 dòng metadata header: `File · Version 2026-05-20 · Phase 2.8 · Audience: FE team · Depends on: feature-screens, feature-workflows · Last review: ...`.
- [ ] Sửa 5 anchor không có `href` → đổi sang `<button>` hoặc `<span>` cho semantic đúng.
- [ ] Bổ sung Phase token (hiện 0 mention).

**E. CSS tokens — tách thành file chung**:
- [ ] Tạo `docs/specs/kaori-design-tokens.css` chứa các token nhất quán (`--accent`, `--bg`, `--text`, `--border`, `--text-soft`, `--bg-card`, `--shadow`).
- [ ] 3 HTML file import file này thay vì khai báo riêng → tránh drift.
- [ ] Đồng bộ `--shadow`: chọn 1 trong 2 phiên bản (`0 1px 3px rgba(0,0,0,.04), 0 1px 2px rgba(0,0,0,.06)` vs `0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04)`).

**F. Machine-readable metadata** cho `feature-workflows.html` (vì title nói rõ "for dev/AI agent"):
- [ ] Thêm `<script type="application/json" id="workflows-index">…</script>` ở cuối file chứa structured index `{id, name, vertical, mode, plan_gate, trigger, sla, ...}` cho từng workflow.

---

## 2. 🔴 HIGH — `docs/api-specs/*.openapi.json` + `API_CATALOG_V4.md`

### 2.1 Bối cảnh
Per 3.4 API Contract pointer:
- `API_CATALOG_V4.md` claim 169 endpoint
- `orchestrator.openapi.json` snapshot tại P15-S10 có 46 path (đã có nhiều hơn ở rev hiện tại)
- `pipeline.openapi.json` snapshot tại P15-S10 có 21 path (cũng đã có nhiều hơn)
- **Chưa có per-endpoint SLA, rate-limit, error code**, đặc biệt CR-0008 báo 10 nguồn Process Mining đã ship nhưng catalog chỉ note "Phase 1 = 4 nguồn".

### 2.2 Action cần làm

**A. Regenerate OpenAPI snapshot**:
```bash
cd D:\Kaori System
python scripts/dump_openapi.py --service ai-orchestrator --out docs/api-specs/orchestrator.openapi.json
python scripts/dump_openapi.py --service data-pipeline --out docs/api-specs/pipeline.openapi.json
```
- [ ] Chạy lệnh trên ở rev hiện tại (2026-05-20).
- [ ] Verify số path = số endpoint count trong `API_CATALOG_V4.md` (nếu lệch, có endpoint nào đó trong code chưa được export hoặc ngược lại).

**B. `API_CATALOG_V4.md` — bổ sung per-endpoint metadata**:
- [ ] Thêm cột **SLA P50/P99** (vd 50ms/200ms) per endpoint — đối chiếu NFRS 3.2 §2 Performance.
- [ ] Thêm cột **Rate limit** per endpoint (vd 100 req/min/tenant) — đối chiếu Phase 2.7 `tenant_quotas` (mig 099).
- [ ] Thêm cột **Error codes** liệt kê HTTP status + RFC 7807 problem type.
- [ ] Cập nhật Process Mining: 4 nguồn Phase 1 → **10 nguồn** đã ship (Postgres CDC, Excel, Zalo, Gmail, Outlook, Calendar, Slack, Teams, SharePoint, webhook). Đánh dấu rõ phase ship per nguồn.

**C. FE TypeScript types**:
- [ ] Regen `pipeline.d.ts` và `orchestrator.d.ts` từ OpenAPI snapshot mới.
- [ ] Verify FE compile pass với types mới.

**D. API versioning policy**:
- [ ] Định nghĩa chính thức policy `/api/v1/` → `/api/v2/{portal}/` với deprecation window (đề xuất 6 tháng).
- [ ] Document trong `CLAUDE.md` §6 + bổ sung dòng trong API_CATALOG_V4.md header.

**E. Webhook contract outbound**:
- [ ] Document chính thức outbound webhook (FR-NOT-* notification, alert, NOV digest) — request schema + retry policy + signature verification.

### 2.3 Pointer file BA cần update sau khi xong
- 3.4 API Contract: bump §3 endpoint count + ngày; gỡ "Phần còn thiếu §4" mục SLA per endpoint + rate limit per endpoint + webhook contract.

---

## 3. 🟠 MED — `docs/specs/MEDALLION_CONTRACT.md`

### 3.1 Bối cảnh
BA SRS §2 đã làm rõ lớp Silver (Bạc): 8 bước transformation (validate, type cast, null handling, dedup, PII masking tiếng Việt, normalize, outlier flag, lineage tag) + gate ≥80%. Cần đồng bộ ngược về code repo doc.

### 3.2 Action
- [ ] Mở `MEDALLION_CONTRACT.md` và verify section Silver có đủ 8 bước transformation như SRS §2.
- [ ] Nếu thiếu, thêm; nếu khác, hoà giải với SRS (BA = source of truth cho semantic, code repo = source of truth cho implementation).
- [ ] Add invariant: **quality gate ≥80% pass to Gold** — chặn tự động Silver→Gold nếu fail.
- [ ] Đối chiếu với mig SQL: schema Silver phải có cột `lineage_bronze_id`, `silver_quality_score`, `pii_masked_fields`, `tenant_id` (RLS).

---

## 4. 🟠 MED — UAT scripts thiếu Phase 2.5/2.6/2.7

### 4.1 Bối cảnh
Per 3.6 UAT pointer §3 status table:
- ✅ Phase 1 v4 — Round 1 Olist pilot
- 🟡 Phase 1.5 — partial (SSO Google PASS)
- ❌ **Phase 2.5 (MinerU + 9 AI nodes shipped 10/10 BE)** — chưa UAT
- ❌ **Phase 2.6 (orchestration hardening, event sourcing, ontology gov)** — chưa UAT replay + DLQ console
- ❌ **Phase 2.7 (governance wiring, lineage edges, ai_decision_audit, policy engine)** — chưa UAT
- ❌ Workflow Execution Closeout 45/45 + 25/25 templates LIVE — chưa UAT end-to-end approval + saga
- ❌ Pilot Round 2 scheduled chưa execute
- ❌ Cross-portal flow UAT — chưa viết
- ❌ K-rule UAT (K-4 consent / K-12 anti-IDOR / K-13 idempotency / K-17 side-effect / K-18 Vault) — chưa
- ❌ Performance UAT (NFR-P-01..12) — chưa

### 4.2 Action — viết per feature shipped

**Priority 1 (Phase 2.5):**
- [ ] `F-CLASSIFY.md` — AI node Classify (Vietnamese doc)
- [ ] `F-EXTRACT.md` — AI node Extract (key-value)
- [ ] `F-SUMMARISE.md` — AI node Summarise
- [ ] `F-SENTIMENT.md` — AI node Sentiment
- [ ] `F-DEDUP.md` — AI node Dedup
- [ ] `F-COMPARE.md` — AI node Compare
- [ ] `F-MINERU.md` — MinerU OCR pipeline
- [ ] `F-WORKFLOW-EXEC-CLOSEOUT.md` — 45 node + 25 template end-to-end

**Priority 2 (Phase 2.6):**
- [ ] `F-WORKFLOW-EVENTS.md` — event sourcing replay
- [ ] `F-IDEMPOTENCY-LEDGER.md` — K-13 ledger persistence
- [ ] `F-DLQ-CONSOLE.md` — DLQ unified 5-source console
- [ ] `F-ONTOLOGY-GOV.md` — lifecycle FSM + edge taxonomy

**Priority 3 (Phase 2.7):**
- [ ] `F-LINEAGE-WALK.md` — 12 ObjectKind traversal
- [ ] `F-AI-DECISION-AUDIT.md` — immutable per LLM call
- [ ] `F-POLICY-ENGINE.md` — policy_rules + quota override + fail-open
- [ ] `F-QUOTA-429.md` — tenant_quota_usage + 429 + Retry-After

**Priority 4 (cross-portal + K-rule + Performance):**
- [ ] `CROSS_PORTAL_FLOW.md` — Studio Analyst → Enterprise Manager → CSM hand-off
- [ ] `K_RULE_INVARIANTS.md` — K-4/K-12/K-13/K-17/K-18 dedicated test
- [ ] `PERFORMANCE_NFR.md` — P50/P99 cho NFR-P-01..12 trên CI
- [ ] `PILOT_ROUND_2.md` execute — đã có template, chỉ cần chạy

### 4.3 Pointer file BA cần update
- 3.6 UAT: bump §3 status table; gỡ "Phần còn thiếu §4".

---

## 5. 🟡 LOW — `docs/specs/VALIDATION_RULES.md`

### 5.1 Bối cảnh
NFRS 3.2 §13.3 mandate mỗi US có 4 negative scenario (Happy / Validation / Permission / Dependency). URD v2.0 đã apply. Code repo `VALIDATION_RULES.md` cần đầy đủ rule per field để dev impl đúng error message.

### 5.2 Action
- [ ] Verify mỗi field input trong UI screens có rule: required/optional, format (regex/enum), range (min/max/length), depend-on (field A required khi field B = X).
- [ ] Error message tiếng Việt cụ thể, không generic ("Lỗi nhập liệu").
- [ ] Đồng bộ với `MESSAGE_DEFINITIONS.md`.

---

## 6. 🟡 LOW — `docs/specs/MESSAGE_DEFINITIONS.md`

### 6.1 Action
- [ ] Verify catalog SYS-ERR* (system error) + USR-ERR* (user error) đầy đủ tiếng Việt.
- [ ] Mỗi error code wire RFC 7807 Problem Details: `type`, `title`, `status`, `detail`, `instance`.
- [ ] Đảm bảo PII không leak vào error message (NFR-O-08).

---

## 7. 🟡 LOW — `docs/specs/CHAT_TOOL_REGISTRY_V4.md`

### 7.1 Bối cảnh
EPIC-10 MCP Server (Phase 2) expose tools qua JSON-RPC 2.0. Cần đồng bộ tool registry với MCP standard + scope auth per tenant.

### 7.2 Action
- [ ] Verify tool definition đúng schema MCP JSON-RPC 2.0.
- [ ] Mỗi tool có `tenant_scope: required`, `permission: [...]`, `rate_limit: ...`.
- [ ] Bổ sung tool cho EPIC-12 (Process Mining query), EPIC-13 (Adoption health), EPIC-14 (NOV query) — để AI client ngoài (Claude/Cursor) gọi được.

---

## 8. Governance gap đã phát hiện

### 8.1 CR submit miss trong code repo
Per 4.2 v2.0, **CR-0009 (Workflow Events) và CR-0010 (Lineage Edges + AI Decision Audit + Policy Engine) đã shipped Phase 2.6/2.7 mà không qua CR Review Board formal**. Engineering đẩy thẳng vào sprint.

**Action process tightening:**
- [ ] PR merge cho feature module mới phải gắn `CR-####` trong commit message.
- [ ] CI block nếu commit không có CR ID (cho path `migrations/`, `routers/`, `services/` thêm file mới).
- [ ] `scripts/check_cr_compliance.py` chạy trong CI.

### 8.2 BA-code drift detection
- [ ] Tạo script `scripts/check_ba_sync.py` chạy weekly: so sánh module list trong Feature Tree v4.1 vs migrations + endpoints. Output report nếu lệch >5%.

### 8.3 OpenAPI snapshot stale
- [ ] Pre-commit hook regen `*.openapi.json` khi router file thay đổi.
- [ ] CI fail nếu snapshot lệch với router code.

---

## 9. Excel Feature Tree v4.1 — items chưa fill (chuyển sang dev/PO)

Per Excel `Issues Found` sheet:
- **ISS-001 (HIGH)**: 266 feature module 2.28 tag "Phase 1.5" nhưng sprint code "P3-S25" — cần PO chốt intent.
- **ISS-004 (MED)**: 1.143 feature có cột Owner trống — Eng Leads cần phân công.

**Action:**
- [ ] CR Review Board sprint kế: PO + Eng Leads dành 1h fill Owner cho top 200 feature P0 trước.
- [ ] PO chốt module 2.28 thuộc Phase nào trong tuần này.

---

## 10. Sequence ưu tiên đề xuất (cho Sprint Planning kế)

| Sprint | Việc cần làm | Owner |
|---|---|---|
| Sprint hiện tại (closeout) | Fix HIGH #1 (UI Screens + 3 HTML) + HIGH #2 (OpenAPI regen) | FE Lead + TL |
| Sprint kế (P2-S26) | UAT script Phase 2.5 (Priority 1 list) + Medallion Contract sync | QA + TL |
| Sprint +2 (P2-S27) | UAT Phase 2.6 + 2.7 + Validation Rules + Message Definitions | QA + BE Eng |
| Sprint +3 | Chat Tool Registry sync + CR governance tightening (CI scripts) | TL + SRE |
| Q2 ongoing | BA-code drift detection automation + monthly review | PM + TL |

---

*— Hết Review Notes for Code Repo —*
