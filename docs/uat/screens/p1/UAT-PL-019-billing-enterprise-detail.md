# UAT-PL-019 · Enterprise Billing Detail

| | |
|---|---|
| **Mã test** | UAT-PL-019 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/billing/enterprises/[id]` |
| **Source FE** | `frontend/app/platform/billing/enterprises/[id]/page.tsx` |
| **Endpoint** | `GET /api/v1/platform/billing/enterprises/{id}` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `c0b272d` (2026-05-18) |

---

## Mục tiêu test

Drill-down detail của 1 enterprise: big counter (unique customers / quota %) + bar + revenue breakdown + link sang workspace gốc.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Enterprise tồn tại với billing data. |
| P3 | Vào từ UAT-PL-017 TC-5 hoặc direct nav. |

## Test cases

### TC-1 · Render khi có data

**Steps**
1. Vào `/platform/billing/enterprises/<enterprise_id>`.

**Expected**
- ✅ Note: page nằm trong `/platform/billing/` nên billing layout tab bar vẫn render trên đầu (tab "Hạn mức" có thể active vì pathname startsWith match).
- ✅ Back link "← Quay lại danh sách hạn mức".
- ✅ Header: icon Building2 halo gold + enterprise_name (serif text-2xl) + Badge status + enterprise_id monospace + link "Xem workspace gốc →" (icon ExternalLink).
- ✅ Section "Sử dụng" lớn:
  - Label uppercase "Sử dụng"
  - Big numeral `font-serif text-3xl tabular-nums`: "N / M" (M smaller)
  - Subtitle "X% hạn mức tháng — Ngưỡng cảnh báo Y%"
  - Plan Badge `current` ở phải
- ✅ Progress bar `h-2 rounded-full bg-app` với fill color theo status.
- ✅ Nếu overage_units > 0: red warning banner "Đã vượt hạn mức N đơn vị. Phụ phí sẽ áp dụng từ F-059 (hiện tạm tính 0).".
- ✅ Section "Doanh thu kỳ YYYY-MM":
  - 4-field grid: Phí cơ sở / Phí vượt hạn mức / Tổng kỳ này / Kỳ thanh toán tiếp theo
  - Tổng kỳ này text gold `--primary-gold-dark`.

### TC-2 · Click "Xem workspace gốc"

**Steps**
1. Click link icon ExternalLink.

**Expected**
- ✅ Navigate `/platform/workspaces/<workspace_id>` (UAT-PL-006).

### TC-3 · Back link

**Steps**
1. Click "← Quay lại danh sách hạn mức".

**Expected**
- ✅ Navigate `/platform/billing/quota` (UAT-PL-017).

### TC-4 · Progress bar color logic

**Steps**
1. Quan sát bar fill.

**Expected**
- ✅ status overage → bar `#C26B6B` (red).
- ✅ status critical → bar `#D97C7C` (coral).
- ✅ status warn → bar `--state-warning` (yellow).
- ✅ status normal → bar `--state-success` (green).

### TC-5 · Overage warning banner

**Steps**
1. Enterprise có `overage_units > 0`.

**Expected**
- ✅ Red banner sau progress bar với icon AlertTriangle + text "Đã vượt hạn mức <N> đơn vị. Phụ phí sẽ áp dụng từ F-059 (hiện tạm tính 0).".

**Steps khác**
2. Enterprise có overage_units = 0.

**Expected**
- ✅ Banner KHÔNG hiện.

### TC-6 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ Skeleton h-8 w-64 + h-32 animate-pulse cho header + section.

### TC-7 · BE 404

**Steps**
1. Direct nav với invalid enterprise_id.

**Expected**
- ✅ Back link vẫn render.
- ✅ ErrorBanner: "Không tìm thấy doanh nghiệp <id>.".

### TC-8 · BE 500

**Steps**
1. Stop auth-service.

**Expected**
- ✅ ErrorBanner generic.

### TC-9 · VND formatting + percentage

**Steps**
1. Quan sát giá trị.

**Expected**
- ✅ VND: `1.000.000₫` dot-separator + ₫.
- ✅ Percentage: `fmtPct(usage_pct/100)` ví dụ "85,3%" với dấu phẩy thập phân vi-VN.

### TC-10 · Plan badge

**Steps**
1. Quan sát badge plan_code bên cạnh section "Sử dụng".

**Expected**
- ✅ Variant `current` (gold tint).
- ✅ Label raw plan_code (e.g. "ENT_MID").

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-017** /billing/quota — return path.
- **UAT-PL-006** /workspaces/{workspace_id} — TC-2.
