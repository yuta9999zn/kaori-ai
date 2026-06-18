# UAT-PL-009 · Workspace Billing

| | |
|---|---|
| **Mã test** | UAT-PL-009 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/[id]/billing` |
| **Source FE** | `frontend/app/platform/workspaces/[id]/billing/page.tsx` |
| **Endpoint** | `GET /workspaces/{id}/billing` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

Thanh toán + hạn mức của 1 workspace theo kỳ tháng: 3 KPI cards (unique customers / total revenue / overage units) + QuotaBar + next invoice date.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Workspace có billing data trong kỳ hiện tại (`enterprise_monthly_billing` row). |

## Test cases

### TC-1 · Render khi có data

**Steps**
1. Vào `/platform/workspaces/<uuid>/billing`.

**Expected**
- ✅ Grid 3 KPI cards:
  - **Khách hàng duy nhất tháng này** — value `fmtInt(unique_customers)`, hint "Hạn mức: M (gói X)", halo gold/warning/error theo usage %
  - **Tổng cước tháng này** — value `fmtVND(total_amount_vnd)`, hint "Cơ bản X + vượt mức Y", halo gold
  - **Đơn vị vượt mức** — value `fmtInt(overage_units)`, hint "Đã tính cước vượt" hoặc "Trong hạn mức", halo warning nếu >0
- ✅ Section "Kỳ thanh toán YYYY-MM" với title + status Badge.
- ✅ QuotaBar component: progress bar + percentage text + threshold markers (80% warn, 95% critical).
- ✅ Nếu có `next_invoice_date`: line "Ngày phát hành hóa đơn kế tiếp: DD/MM/YYYY" với icon Calendar.

### TC-2 · KPI halo color logic

**Steps**
1. Quan sát KPI tile "Khách hàng duy nhất".

**Expected**
- ✅ usage < 80% → halo gold (`--primary-gold/15`).
- ✅ 80% ≤ usage < 95% → halo warning (`--state-warning/15` text `#9E814D`).
- ✅ unique_customers > quota (overage) → halo error (`--state-error/15` text `#9B5050`).

### TC-3 · Status badge

**Steps**
1. Quan sát Badge cạnh section title.

**Expected**
- ✅ status `normal` → operational "Bình thường".
- ✅ status `warn` → warning "Cảnh báo (≥80%)".
- ✅ status `critical` → warning "Nghiêm trọng (≥95%)".
- ✅ status `overage` → error "Vượt hạn mức".

### TC-4 · QuotaBar render

**Steps**
1. Quan sát QuotaBar.

**Expected**
- ✅ Bar background `--bg-app`.
- ✅ Bar fill color: green nếu < 80%, yellow 80-95%, red ≥ 95%.
- ✅ Text format "N khách hàng duy nhất" (theo `unit` prop).
- ✅ Percentage display (top-right hoặc inline).

### TC-5 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 3 skeleton cards `h-28 animate-pulse`.

### TC-6 · BE error (404 / 500)

**Steps**
1. Workspace không có billing row, hoặc stop auth-service.

**Expected**
- ✅ ErrorBanner: "Backend billing cho workspace <id> chưa sẵn sàng.".

### TC-7 · Overage warning banner

**Steps**
1. Workspace có `overage_units > 0`.

**Expected**
- ✅ KPI "Đơn vị vượt mức" tile có halo warning + hint "Đã tính cước vượt".
- ✅ Section main KPI "Khách hàng duy nhất" tile có halo error (vì isOver = true).

### TC-8 · VND formatting

**Steps**
1. Quan sát các giá trị tiền.

**Expected**
- ✅ Format `1.000.000₫` (dấu chấm thousand separator + ₫ suffix).
- ✅ KHÔNG dùng "1M" hay "1,000,000".

### TC-9 · Status badge cho status không lường trước

**Steps**
1. BE trả status string lạ (e.g. "unknown").

**Expected**
- ✅ Badge fallback variant `operational` (default), label hiển thị raw string.

### TC-10 · Next invoice line conditional

**Steps**
1. Backend trả `next_invoice_date = null`.

**Expected**
- ✅ Line "Ngày phát hành hóa đơn kế tiếp" KHÔNG render.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-016** `/platform/billing/overview` — platform-level aggregate.
- **UAT-PL-019** `/platform/billing/enterprises/{id}` — per-enterprise detail.
