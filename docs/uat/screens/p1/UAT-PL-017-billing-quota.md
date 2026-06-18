# UAT-PL-017 · Billing Quota Table

| | |
|---|---|
| **Mã test** | UAT-PL-017 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/billing/quota` |
| **Source FE** | `frontend/app/platform/billing/quota/page.tsx` |
| **Endpoint** | `GET /api/v1/platform/billing/quota?plan=&status=&cursor=&limit=` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `c0b272d` (2026-05-18) |

---

## Mục tiêu test

Bảng tất cả enterprises trong kỳ hiện tại với usage / quota / overage / revenue / status. Filter plan + status, pagination cursor, link sang per-enterprise detail.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | ≥ 1 enterprise có billing row. |

## Test cases

### TC-1 · Render table

**Steps**
1. Click tab "Hạn mức" trên billing layout.

**Expected**
- ✅ Filter row: "Lọc theo:" + select Gói + select Trạng thái + (optional) "Xoá bộ lọc" + total enterprises right-aligned.
- ✅ Table columns: Doanh nghiệp · Gói · Sử dụng · % · Vượt · Trạng thái · Doanh thu · (Chi tiết link).
- ✅ Mỗi row:
  - Doanh nghiệp: name font-medium + enterprise_id monospace dưới
  - Gói: Badge `current` plan_code
  - Sử dụng: "X / Y" tabular-nums + inline mini-bar `h-1.5 w-32` color theo status
  - % column: `fmtPct(usage_pct/100)` tabular
  - Vượt: nếu > 0 → text red "+N"; nếu = 0 → "—"
  - Trạng thái: Badge variant theo (normal=operational, warn=warning, critical=error, overage=error)
  - Doanh thu: `fmtVND(total_amount_vnd)` tabular
  - Chi tiết → link `/platform/billing/enterprises/{enterprise_id}` (UAT-PL-019)

### TC-2 · Filter plan

**Steps**
1. Chọn dropdown Gói = "ENT_MAX".

**Expected**
- ✅ React-query reset cursor + refetch `?plan=ENT_MAX`.
- ✅ Table chỉ hiện rows plan ENT_MAX.

### TC-3 · Filter status

**Steps**
1. Chọn dropdown Trạng thái = "Vượt hạn mức".

**Expected**
- ✅ Refetch `?status=overage`.
- ✅ Table chỉ rows overage.
- ✅ "Xoá bộ lọc" button visible (vì có filter active).

### TC-4 · Clear filter

**Steps**
1. Có filter active, click "✕ Xoá bộ lọc".

**Expected**
- ✅ Plan + status reset về "" (Tất cả).
- ✅ Refetch full list.

### TC-5 · Click Chi tiết

**Steps**
1. Click link "Chi tiết →" của 1 row.

**Expected**
- ✅ Navigate `/platform/billing/enterprises/<enterprise_id>` (UAT-PL-019).

### TC-6 · Mini-bar color

**Steps**
1. Quan sát column Sử dụng.

**Expected**
- ✅ Bar fill color:
  - status normal → `--state-success` (green)
  - status warn → `--state-warning` (yellow)
  - status critical → `#D97C7C` (coral)
  - status overage → `#C26B6B` (red)
- ✅ Bar width = `min(100, usage_pct)%`.

### TC-7 · Pagination "Tải thêm"

**Steps**
1. Bottom có button "Tải thêm" nếu `meta.cursor` non-null.
2. Click.

**Expected**
- ✅ React-query refetch với `cursor`.
- ✅ Page 2 data append vào table (chú ý: implementation hiện REPLACE thay vì append; cần verify).

### TC-8 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 5 skeleton rows `h-14 animate-pulse`.

### TC-9 · BE error

**Steps**
1. Stop auth-service.

**Expected**
- ✅ ErrorBanner: "Không thể tải danh sách hạn mức.".

### TC-10 · Empty state

**Steps**
1. Filter no match.

**Expected**
- ✅ Table body: "Không có doanh nghiệp khớp bộ lọc.".

**Steps khác**
2. Chưa filter, BE trả empty.

**Expected**
- ✅ Table body: "Chưa có doanh nghiệp nào trong kỳ thanh toán hiện tại.".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Pagination "Tải thêm" hiện refetch + replace; có thể nên append (infinite scroll pattern). | Acceptable Phase 1. |

## Related screens

- **UAT-PL-016** /billing/overview — tab anh em.
- **UAT-PL-018** /billing/export — tab xuất CSV cùng filter.
- **UAT-PL-019** /billing/enterprises/{id} — TC-5 destination.
