# UAT-PL-016 · Billing Overview (Doanh thu nền tảng)

| | |
|---|---|
| **Mã test** | UAT-PL-016 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/billing/overview` (`/platform/billing` redirect tới đây) |
| **Source FE** | `frontend/app/platform/billing/overview/page.tsx` + `/billing/layout.tsx` |
| **Endpoint** | `GET /api/v1/platform/billing/overview` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ (F-031 cron) |
| **Re-skin commit** | `c0b272d` (2026-05-18) |

---

## Mục tiêu test

Tổng quan doanh thu platform tháng hiện tại: 4 KPI cards + status distribution bar + cron health card + revenue breakdown.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | BE cron `F-031` đã chạy ít nhất 1 lần để có aggregate data trong `enterprise_monthly_billing`. |

## Test cases

### TC-1 · Redirect `/platform/billing` → `/platform/billing/overview`

**Steps**
1. Nav `/platform/billing`.

**Expected**
- ✅ Server-side redirect.
- ✅ URL bar đổi thành `/platform/billing/overview`.

### TC-2 · Render layout (tab bar)

**Steps**
1. Vào `/platform/billing/overview`.

**Expected**
- ✅ Header section: icon Wallet halo gold + heading serif "Thanh toán & Hạn mức" + description.
- ✅ Tab bar: Tổng quan (gold underline active) · Hạn mức · Xuất CSV.
- ✅ Body padding `px-6 lg:px-8 py-6`.

### TC-3 · Render KPI grid

**Steps**
1. Quan sát top body.

**Expected**
- ✅ 4 KPI cards (grid 2 cols mobile, 4 cols xl):
  - **Doanh thu tháng này** — value `fmtVNDShort(total_revenue_vnd)` (e.g. "2,5M ₫"), hint `fmtVND(total_revenue_vnd)` ("2.500.000 ₫"), halo gold
  - **Doanh nghiệp đang hoạt động** — value `fmtInt(enterprise_count)`, hint "Kỳ thanh toán YYYY-MM", halo gold
  - **Khách hàng độc nhất** — value `fmtInt(total_unique_customers)`, hint "X% trên tổng hạn mức N", halo info (blue)
  - **Cần chú ý** — value `fmtInt(warn + critical + overage)`, hint "Doanh nghiệp ≥80% hạn mức hoặc đã vượt", halo: warning nếu >0, success nếu = 0
- ✅ Mỗi KPI: label uppercase + serif numeral lớn + hint text-xs muted.

### TC-4 · Render status distribution bar

**Steps**
1. Section "Phân bố theo trạng thái".

**Expected**
- ✅ Heading + subtitle "Ngưỡng cảnh báo: 80% · Ngưỡng nguy hiểm: 95% · Vượt hạn mức ngay khi có overage." + icon Gauge ở phải.
- ✅ Bar h-3 rounded-full bg-app, segments stacked theo proportion:
  - normal → green `--state-success`
  - warn → yellow `--state-warning`
  - critical → coral `#D97C7C`
  - overage → red `#C26B6B`
- ✅ Legend grid 4 cols: mỗi dot + label + count tabular-nums.
- ✅ Empty state (enterprise_count = 0): "Chưa có doanh nghiệp đang hoạt động.".

### TC-5 · Cron health card (F-031)

**Steps**
1. Section "Sức khoẻ tác vụ tổng hợp (F-031)".

**Expected**
- ✅ Heading + subtitle "Cron chạy hằng ngày 02:00 ICT — cập nhật last_aggregated_at trên mỗi doanh nghiệp." + icon Clock.
- ✅ Status banner box:
  - **ok**: green bg + icon CheckCircle2 + "Bình thường" (last_aggregated_at < 25h AND stale_count = 0)
  - **warn**: yellow bg + icon AlertTriangle + "Cảnh báo — có doanh nghiệp chưa cập nhật" (stale_count > 0 OR last > 25h)
  - **critical**: red bg + icon XCircle + "Sự cố — cron có thể đang dừng" (last null OR stale_count = total)
- ✅ Detail line: "Lần chạy gần nhất: <datetime>. Doanh nghiệp chưa cập nhật trong 25h: N/M.".

### TC-6 · Render revenue breakdown

**Steps**
1. Section "Chi tiết doanh thu".

**Expected**
- ✅ 6-field grid:
  - Doanh thu cơ sở: fmtVND(total_base_amount_vnd)
  - Doanh thu vượt hạn mức: fmtVND(total_overage_amount_vnd) + note "Phụ phí theo đơn giá sẽ áp dụng từ F-059 (hiện tạm tính 0)."
  - Tổng doanh thu: fmtVND(total_revenue_vnd) — text gold `--primary-gold-dark`
  - Đơn vị vượt hạn mức: fmtInt(total_overage_units)
  - Kỳ thanh toán tiếp theo: fmtDate(next_invoice_date)
  - Xu hướng: "Cập nhật theo ngày" + icon TrendingUp (green).

### TC-7 · React-query 60s refetch

**Steps**
1. Network tab → filter "overview".
2. Đứng yên 60-65s.

**Expected**
- ✅ Re-poll `GET /platform/billing/overview` mỗi 60s.

### TC-8 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 4 skeleton cards `h-28 animate-pulse`.

### TC-9 · BE error / empty

**Steps**
1. Stop auth-service.

**Expected**
- ✅ ErrorBanner: "Không thể tải tổng quan thanh toán.".

### TC-10 · VND formatting

**Steps**
1. Quan sát giá trị tiền.

**Expected**
- ✅ Format Vietnamese: dấu chấm thousand separator + ₫ suffix.
- ✅ Short form chỉ dùng ở KPI title (e.g. "2,5M ₫"); full form ở hint.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-017** /billing/quota — tab kế.
- **UAT-PL-018** /billing/export — tab Xuất CSV.
- **UAT-PL-019** /billing/enterprises/{id} — drill-down detail.
