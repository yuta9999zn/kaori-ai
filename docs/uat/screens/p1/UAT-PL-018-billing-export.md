# UAT-PL-018 · Billing Export CSV

| | |
|---|---|
| **Mã test** | UAT-PL-018 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/billing/export` |
| **Source FE** | `frontend/app/platform/billing/export/page.tsx` |
| **Endpoint** | `GET /api/v1/platform/billing/export?month=&plan=&status=` (returns CSV blob) |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `c0b272d` (2026-05-18) |

---

## Mục tiêu test

Xuất CSV billing data của 1 kỳ + filter optional plan/status. Browser tự download file UTF-8 BOM, Excel mở không lỗi tiếng Việt.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Browser cho phép auto-download (no popup blocker). |

## Test cases

### TC-1 · Render form

**Steps**
1. Click tab "Xuất CSV".

**Expected**
- ✅ Section card chứa form:
  - Icon FileText halo gold + heading "Xuất báo cáo CSV" + description về UTF-8 BOM.
  - 3-col grid:
    - Label "Kỳ thanh toán" + Input pattern `\d{4}-\d{2}` placeholder "YYYY-MM" pre-filled current month
    - Label "Gói (tuỳ chọn)" + select (Tất cả gói default + 5 plans)
    - Label "Trạng thái (tuỳ chọn)" + select (Tất cả trạng thái + 4 statuses)
  - (Conditional) Yellow warning nếu month format invalid.
  - (Conditional) ErrorBanner nếu mutation error.
  - (Conditional) Green success "Đã tải <filename>." nếu lastDownload set.
  - Button "📥 Tải xuống CSV" (disabled khi month invalid).
- ✅ Section thứ 2: "Cột trong file" + `<code>` block liệt kê columns + note "Tối đa 5,000 dòng mỗi lần xuất. Nếu vượt, header X-Truncated sẽ trả về true.".

### TC-2 · Submit happy path

**Steps**
1. Để month = "2026-05" (current).
2. Plan = Tất cả. Status = Tất cả.
3. Click "Tải xuống CSV".

**Expected**
- ✅ Button spinner.
- ✅ `GET /api/v1/platform/billing/export?month=2026-05` → response `text/csv` blob + header `Content-Disposition: attachment; filename="kaori-billing-2026-05.csv"`.
- ✅ Browser auto-download file.
- ✅ Green success banner: "Đã tải kaori-billing-2026-05.csv.".

### TC-3 · Filter trước khi export

**Steps**
1. Chọn Plan = ENT_MAX, Status = warn.
2. Submit.

**Expected**
- ✅ `GET ?month=...&plan=ENT_MAX&status=warn` → filtered CSV.

### TC-4 · Invalid month format

**Steps**
1. Đổi month thành "abc" (không match YYYY-MM).

**Expected**
- ✅ Yellow warning xuất hiện: "Định dạng kỳ phải là YYYY-MM, ví dụ 2026-04.".
- ✅ Button "Tải xuống CSV" disabled.

### TC-5 · Empty month

**Steps**
1. Clear month input.

**Expected**
- ✅ Warning NOT shown (empty = current month, BE handles).
- ✅ Button enabled.
- ✅ Submit → BE dùng current month.

### TC-6 · BE error

**Steps**
1. Stop auth-service.
2. Submit.

**Expected**
- ✅ ErrorBanner: detail từ response RFC 7807.
- ✅ Success banner KHÔNG xuất hiện.

### TC-7 · CSV UTF-8 BOM

**Steps**
1. Download file.
2. Mở bằng notepad (Windows): xem byte đầu file.
3. Mở bằng Excel: verify tiếng Việt không vỡ.

**Expected**
- ✅ Byte 0-2 file = `0xEF 0xBB 0xBF` (BOM).
- ✅ Excel hiển thị column "Doanh nghiệp" đúng dấu (vd "Olist Store" thay vì "Olist Stáº¥t").

### TC-8 · Filename theo month

**Steps**
1. Submit month = "2026-04".

**Expected**
- ✅ Filename `kaori-billing-2026-04.csv` (BE generate filename theo query param).

### TC-9 · Truncation header

**Steps**
1. Submit kỳ có > 5000 enterprises (test edge).

**Expected**
- ✅ Response header `X-Truncated: true`.
- ⚠️ FE hiện không surface header — TODO UX cải thiện.

### TC-10 · Column legend

**Steps**
1. Quan sát section "Cột trong file".

**Expected**
- ✅ `<code>` block liệt kê 12 columns: `enterprise_id, enterprise_name, plan_code, billing_month, unique_customers, quota, usage_pct, overage_units, base_amount_vnd, overage_amount_vnd, total_amount_vnd, status`.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | FE không surface `X-Truncated` header (TODO). | Check Network tab manually. |

## Related screens

- **UAT-PL-016** /billing/overview.
- **UAT-PL-017** /billing/quota.
