# UAT-EN-001 · Enterprise Dashboard Overview

| | |
|---|---|
| **Mã test** | UAT-EN-001 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/dashboard/overview` |
| **Source FE** | `frontend/components/p2/templates/09-dashboard-overview.tsx` |
| **Endpoint** | `GET /api/v1/dashboard/state` |
| **Auth required** | Có (MANAGER / OPERATOR / ANALYST / VIEWER) |
| **Phase** | Phase 1 ✅ (F-028) |
| **Shell** | `app/(app)/p2/layout.tsx` wrap `<AppShell>` (commit `9d26d95`) |

---

## Mục tiêu test

Landing dashboard sau khi enterprise user login. 5-state machine driven by `/dashboard/state`:
- `empty` → no data uploaded → CTA upload
- `uploading` → file in flight → progress
- `processing` → bronze→silver→gold pipeline running → SSE stream
- `completed` → KPIs + recent runs + alerts + insights
- `error` → RFC 7807 detail + retry

Plus K-11 quota banner (DISTINCT customer_external_id) với 80%/95% thresholds.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as enterprise user (`cs@olist.local` / `Pilot@2026` từ seed-pilot-olist.py). |
| P2 | BE data-pipeline + ai-orchestrator reachable. |

## Test cases

### TC-1 · Render state `empty`

**Steps**
1. Login enterprise mới chưa upload data.
2. Navigate `/p2/dashboard/overview`.

**Expected**
- ✅ PageHeader "Bảng điều khiển" + description.
- ✅ Empty CTA card với icon UploadCloud + heading + button "Tải dữ liệu lên" → `/p2/pipelines/new/upload`.

### TC-2 · Render state `completed`

**Steps**
1. Enterprise có ít nhất 1 pipeline run thành công.

**Expected**
- ✅ Grid KPI 6 cards: Bronze files / Pipeline runs 30d / Insights 30d / Open alerts / Data processed GB / Active users.
- ✅ Section "Recent runs" với danh sách pipelines gần đây + status badges (schema_review / analyzing / analysis_complete).
- ✅ Section "Alerts" + "Insights" preview.
- ✅ QuotaBar K-11 đầu trang với plan + usage current/limit.

### TC-3 · QuotaBar threshold

**Steps**
1. Quan sát QuotaBar.

**Expected**
- ✅ usage < 80% → green.
- ✅ 80-95% → yellow Badge "warning".
- ✅ ≥ 95% → red Badge "error" + nudge upgrade plan.

### TC-4 · Render state `processing` (SSE)

**Steps**
1. Trigger upload (UAT-EN-009) đang chạy.

**Expected**
- ✅ Section "Đang xử lý" với progress bar + step indicator (Bronze → Silver → Gold).
- ✅ SSE event stream cập nhật real-time.

### TC-5 · Render state `error`

**Steps**
1. BE return state = "error" với RFC 7807 detail.

**Expected**
- ✅ ErrorBanner với title + detail.
- ✅ Button "Thử lại" → reload state.

### TC-6 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ Skeleton tiles `animate-pulse` thay grid.

### TC-7 · Sidebar nav

**Steps**
1. Quan sát sidebar trái.

**Expected**
- ✅ Group "Tổng quan" expanded by default (path match `/p2/dashboard`).
- ✅ Item "Bảng điều khiển" active gold accent.

### TC-8 · Cream/gold tokens

**Steps**
1. DevTools `:root`.

**Expected**
- ✅ Tokens `--primary-gold`, `--bg-app`, etc. defined (xem UAT-PL-001 TC-7).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | SSE reconnect logic chưa robust khi network drop. | Reload page. |

## Related screens

- **UAT-EN-002** /p2/dashboard/customize.
- **UAT-EN-007** /p2/pipelines.
- **UAT-EN-009** /p2/pipelines/new/upload.
