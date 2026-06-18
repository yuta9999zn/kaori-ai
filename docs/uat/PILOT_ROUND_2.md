# UAT — Pilot Round 2 (2026-05-04 session)

> **Goal:** validate everything that shipped in this session before queueing the next feature batch.
> **Mode:** dev-mode browser walkthrough (MSW handlers serve canned data — no Postgres / Kafka / auth-service required).
> **Owner:** anh (test) + em (standby fix).
> **Time budget:** ~30-45 minutes for the full sweep.

---

## 0. What landed (this session)

| # | Feature | Surface | PRs |
|---|---|---|---|
| 1 | **F-039 Risk Management** — category enum extension + FE wire | `/p2/risks` + `/p2/risks/[id]` + `/p2/risks/export` | #140 #141 |
| 2 | **F-NEW3 Data Explorer hub** | `/p2/data` | #142 #143 |
| 3 | **F-040 Strategy Builder OKR** | `/p2/strategy` + `/p2/strategy/okr` | #144 #145 |
| 4 | **F-NEW3 v1 Bronze drill-down** | `/p2/data/bronze` + sample modal | #146 #147 |
| 5 | **F-NEW3 v1 Silver + Gold drill-down** | `/p2/data/silver` + `/p2/data/gold` | #148 #149 |
| 6 | **F-NEW3 v1 Lineage trace** | Modal launchable from bronze + silver rows | #150 #151 |

(Plus chore PRs #131 merged, #139 still open, #130 closed.)

---

## 1. Pre-flight

```bash
cd "D:\Kaori System\frontend"
npm run dev          # starts Next on :3000 with MSW intercepting /api/v1/*
```

Open `http://localhost:3000` and log in with the dev-mode mock credentials:

| Email | Role | Use |
|---|---|---|
| `test@demo.com` | MANAGER (P2) | Default test account |
| `locked@test.com` | (423 response) | Lockout edge case |
| `error@test.com` | (401 response) | Error envelope edge case |

Password: `password123`.

> **Browser:** Chrome / Edge dev tools open on **Network** tab so you can inspect each request's status + payload.

---

## 2. F-039 Risk Management

### 2.1 Hub `/p2/risks`

| # | Action | Expected |
|---|---|---|
| 2.1.a | Visit page | 8 fixture risks render in table; KPI tiles (total open / critical / overdue / no-owner) populated; 5×5 heat map shows hot-spot counts |
| 2.1.b | Filter status = "Mitigating" | Table shrinks; cells in heat map remain (matrix is across all open) |
| 2.1.c | Filter category = "Pháp lý" | Only 2 GDPR / tax-regulation risks remain |
| 2.1.d | Search "Ollama" | 1 row (Ollama dependency risk) |
| 2.1.e | Click "+ Thêm rủi ro" → fill modal → Submit | New row appears at top; success banner; KPI recounts |
| 2.1.f | Try submitting with blank title | Validation error from BE; modal stays open |

### 2.2 Detail `/p2/risks/[riskId]`

| # | Action | Expected |
|---|---|---|
| 2.2.a | Click any row | Detail page hydrates with all fields filled |
| 2.2.b | Drag likelihood/impact sliders | Computed score badge updates live (auto-severity tier) |
| 2.2.c | Edit category dropdown → "Tài chính" → save | Success banner; refresh shows category persisted |
| 2.2.d | Click "Xoá (soft)" → confirm | Redirects to `/p2/risks`; row gone from list |

### 2.3 Export `/p2/risks/export`

| # | Action | Expected |
|---|---|---|
| 2.3.a | Pick filter status=Open + category=Vận hành → check 5 cols → "Tải CSV" | File downloads `risks-YYYY-MM-DD.csv` |
| 2.3.b | Open in Excel-VN | Vietnamese accents render correctly (UTF-8 BOM); columns match selection |

---

## 3. F-040 Strategy Builder OKR

### 3.1 Hub `/p2/strategy`

| # | Action | Expected |
|---|---|---|
| 3.1.a | Visit page | Quarter selector defaults to current; 4 KPI tiles (Tổng / On-track / At-risk / Off-track) populated |
| 3.1.b | Toggle quarter to next | KPI counts refresh (likely all zero — no fixture for Q3) |
| 3.1.c | Click "OKR" module card | Navigates to `/p2/strategy/okr` |
| 3.1.d | Click "Lộ trình" / "Họp review" | Card is visually muted; no navigation (deferred Phase 2 v1) |

### 3.2 Editor `/p2/strategy/okr`

| # | Action | Expected |
|---|---|---|
| 3.2.a | Visit page | 3 fixture objectives render with status badges (at_risk / off_track / on_track) |
| 3.2.b | Drag KR slider on first objective → release | PATCH fires (Network tab confirms); status badge re-computes if lag crosses threshold; spinner briefly shows on the row |
| 3.2.c | "+ Thêm Objective" → quarter Q2 2026, title, 3 KRs → Submit | New row appears at top; success banner |
| 3.2.d | Click "Sửa" on an objective → change title + add 4th KR → Save | Row updates; KR set rewritten atomically |
| 3.2.e | Try submitting create with KR target=0 | BE validation error in modal |
| 3.2.f | Click trash icon → confirm | Row gone from list |

---

## 4. F-NEW3 Data Explorer

### 4.1 Hub `/p2/data`

| # | Action | Expected |
|---|---|---|
| 4.1.a | Visit page | 3 LayerCards (Bronze / Silver / Gold) with file/dataset/customer counts; recent activity strip with 5 rows; K-rule reminders |
| 4.1.b | Click "Làm mới" | Spinner appears on button; data refetches |
| 4.1.c | Click any LayerCard | Navigates to `/p2/data/{bronze,silver,gold}` |
| 4.1.d | Click "Xem pipeline đầy đủ" | Navigates to `/p2/data/pipeline-manager` |

### 4.2 Bronze drill-down `/p2/data/bronze`

| # | Action | Expected |
|---|---|---|
| 4.2.a | Visit page | 5 fixture files in table; cursor pager hidden (only 5 rows < 50/page) |
| 4.2.b | Click "Xem" on `sales-q1-2026.csv` | Modal opens; sample table shows 50 rows × 5 cols (order_id, customer, amount_vnd, paid_at, status) |
| 4.2.c | Click "CSV mẫu" | File downloads; opens in Excel-VN with no mojibake |
| 4.2.d | Click chain icon (Lineage) on `customers-export.xlsx` | Lineage modal opens — all 3 cards populated; gold shows linked_customer_count |
| 4.2.e | Click chain icon on `broken-encoding.csv` (failed run) | Silver + Gold both show "null" muted state |
| 4.2.f | Click chain icon on `inventory-march.csv` | Silver populated; Gold shows "Dataset inventory không có cột customer_external_id (per MEDALLION_CONTRACT)" |

### 4.3 Silver drill-down `/p2/data/silver`

| # | Action | Expected |
|---|---|---|
| 4.3.a | Visit page | ~4 datasets in table (failed file excluded); quality bar colored green/yellow per threshold; top-3 rule pills |
| 4.3.b | Click "Xem" on `customers-export.xlsx` row | Modal shows clean_data with `<EMAIL_N>` / `<PHONE_N>` placeholders (K-5 demo) + `applied_rules` pills + quality_score column |
| 4.3.c | Click "CSV mẫu" | CSV includes the `applied_rules` and `quality_score` columns appended |
| 4.3.d | Click chain icon | Same lineage modal as on bronze, populated with full chain |

### 4.4 Gold drill-down `/p2/data/gold`

| # | Action | Expected |
|---|---|---|
| 4.4.a | Visit page | 12 customers in table; revenue_at_risk shown red when > 0 |
| 4.4.b | Click "Chỉ chưa xử lý" filter | Customers with `is_actioned=true` disappear |
| 4.4.c | Click "Khách hàng rủi ro (F-060)" header button | Navigates to `/p2/customers/at-risk` (the F-060 action workflow) |
| 4.4.d | (No chain icon — gold rows are aggregated across files; lineage doesn't apply) | — |

---

## 5. F-060 North Star (verify nothing regressed)

| # | Action | Expected |
|---|---|---|
| 5.1 | Visit `/p2/customers/at-risk` | Tile shows total at-risk VND + resolution rate; customer table renders |
| 5.2 | Click "Đánh dấu đã xử lý" on a pending row → fill notes → confirm | Toggle persists; tile recounts; success banner |
| 5.3 | Click "Bỏ đánh dấu" on an actioned row | Reverts; tile recounts |

---

## 6. Cross-cutting checks

| # | Check | Expected |
|---|---|---|
| 6.a | Open dev tools → Network → filter `/api/v1/` | Every request returns 200/201/204; no 500s; RFC 7807 envelopes on the few intentional 4xx triggers (2.1.f, 3.2.e) |
| 6.b | Open Console tab | No red errors. Yellow warnings about MSW are normal |
| 6.c | Refresh any page mid-modal | Modal closes cleanly; page reloads without state leak |
| 6.d | Resize window to mobile width (~400px) | Tables scroll horizontally; modals stay usable; nav collapses |
| 6.e | Switch tabs (visibilitychange) and back | No spurious refetches; data still in place |

---

## 7. Bug report template

If anything misbehaves, paste this into a new chat turn:

```
**Surface:** /p2/...
**Step:** 4.x.y from PILOT_ROUND_2.md
**Expected:** ...
**Actual:** ...
**Network tab:** {METHOD} {URL} → {status} {body excerpt}
**Console:** {error if any, otherwise "no errors"}
**Repro:** 1. ... 2. ... 3. ...
```

Em sẽ vào file relevant + fix + open a follow-up PR.

---

## 8. Sign-off

When all sections pass cleanly:

- [ ] 2.x F-039 Risks
- [ ] 3.x F-040 Strategy OKR
- [ ] 4.x F-NEW3 Data Explorer (hub + 3 drill-downs + lineage)
- [ ] 5.x F-060 North Star regression
- [ ] 6.x Cross-cutting

Then anh chooses next track:

| Option | Description |
|---|---|
| **A** | F-040 v1 Timeline (template 54) — new entity `okr_milestones` + Gantt page |
| **B** | F-040 v1 Review Meetings (template 55) — new entity `meetings` + agenda items |
| **C** | F-NEW3 v1 saved-query CRUD — pin frequent filters across drill-down pages |
| **D** | Phase 2 next feature from BACKLOG (F-041 Explainability, F-057 Auto DB, F-061 Workflow, etc.) |
| **E** | Pause coding, address Dependabot Monday batch arriving 2026-05-11 |

---

*Generated 2026-05-04 by the session that shipped PRs #140 → #151.*
