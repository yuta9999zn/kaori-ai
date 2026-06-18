# UAT-PL-004 · Workspaces List (Danh sách)

| | |
|---|---|
| **Mã test** | UAT-PL-004 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces` |
| **Source FE** | `frontend/app/platform/workspaces/page.tsx` |
| **Endpoint** | `GET /api/v1/platform/workspaces?cursor=&limit=` |
| **Auth required** | Có (mọi platform role thấy; nút "Tạo" gated SUPER_ADMIN) |
| **Phase** | Phase 1 ✅ (F-008) |
| **Re-skin commit** | `2b0d164` (2026-05-18) |

---

## Mục tiêu test

Liệt kê toàn bộ enterprise workspaces. Filter client-side (search + status + plan), cursor pagination server-side, link sang detail. SUPER_ADMIN có quick action "Tạo workspace mới".

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN (qua UAT-PL-001 TC-2). |
| P2 | Ít nhất 1 workspace tồn tại trong DB (từ `seed-pilot-olist.py` hoặc test data). |

## Test cases

### TC-1 · Render khi có data

**Steps**
1. Click "Workspaces → Danh sách" trong sidebar.

**Expected**
- ✅ HTTP 200.
- ✅ PageHeader: "Workspaces" + description "Quản lý workspace của các enterprise đang dùng nền tảng. Tổng N workspace."
- ✅ Action button "+ Tạo workspace mới" (chỉ SUPER_ADMIN — verify hide cho ADMIN/SUPPORT).
- ✅ Filter row: search input (placeholder "Tìm theo tên hoặc workspace ID") + status select + plan select.
- ✅ Table headers: Workspace · Ngành · Gói cước · Trạng thái · Tạo lúc · Hành động.
- ✅ ≥ 1 row visible với data từ seed.
- ✅ Mỗi row: name (font-medium) + UUID monospace (text-xs muted) ở cột 1.
- ✅ Plan badge variant `current` (gold tint).
- ✅ Status badge variant theo status: active → operational (green), suspended → warning, inactive → degraded.
- ✅ Pagination bar dưới: "Trang 1 · Hiển thị N / N" + buttons "← Trước" (disabled), "Sau →" (disabled nếu chỉ 1 page).

### TC-2 · Search filter

**Steps**
1. Type "olist" vào search input.

**Expected**
- ✅ Row count giảm xuống chỉ rows có `name` hoặc `workspace_id` chứa "olist" (case-insensitive).
- ✅ Bottom bar update "Hiển thị X / N" (X = matches).
- ✅ Clear input → reset về full list.

### TC-3 · Status filter

**Steps**
1. Chọn dropdown "Trạng thái" = "Đang hoạt động".

**Expected**
- ✅ Chỉ rows `status = "active"` hiện.
- ✅ Combined với search OK.

### TC-4 · Plan filter

**Steps**
1. Quan sát dropdown "Gói cước".

**Expected**
- ✅ Options auto-populate từ unique plans trong data (chỉ plans có ít nhất 1 workspace dùng).
- ✅ Plan label localized: PILOT → "Pilot", ENT_BASIC → "Basic", ENT_MID → "Mid", ENT_MAX → "Max", ENT_ROI → "ROI Share".
- ✅ Chọn 1 plan → filter rows.

### TC-5 · Click row → detail

**Steps**
1. Click trên tên workspace (link gold hover).

**Expected**
- ✅ Navigate `/platform/workspaces/{uuid}` (UAT-PL-006).

### TC-6 · Eye icon action

**Steps**
1. Click icon Eye ở cột Hành động.

**Expected**
- ✅ Same behavior TC-5 — navigate detail.

### TC-7 · Edit icon (SUPER_ADMIN only)

**Steps**
1. Quan sát cột Hành động.

**Expected**
- ✅ Icon Edit2 (pencil) chỉ hiện khi `canCreate = true` (SUPER_ADMIN).
- ✅ Click → navigate `/platform/workspaces/{uuid}/edit` (UAT-PL-011).

### TC-8 · Suspend icon (SUPER_ADMIN + active)

**Steps**
1. Quan sát cột Hành động.

**Expected**
- ✅ Icon Ban hiện ONLY khi SUPER_ADMIN VÀ `status = "active"`.
- ✅ Click → currently no-op (Known K-001 dưới).

### TC-9 · Empty state

**Steps**
1. Empty DB workspaces (xoá toàn bộ rows).
2. Refresh.

**Expected**
- ✅ Table body 1 row colspan=6: "Chưa có workspace nào.".
- ✅ Pagination bar không hiện.

### TC-10 · Filter no match

**Steps**
1. Type random string không tồn tại vào search.

**Expected**
- ✅ Table body 1 row: "Không có workspace nào khớp bộ lọc hiện tại.".

### TC-11 · Cursor pagination

**Pre-condition**: > 50 workspaces tồn tại (PAGE_SIZE=50).

**Steps**
1. Quan sát bottom bar: "Sau →" enabled.
2. Click "Sau →".

**Expected**
- ✅ React-query refetch với `cursor=<meta.cursor>` từ response trước.
- ✅ Page number tăng: "Trang 2".
- ✅ "← Trước" enabled.
- ✅ Click "← Trước" → quay về page 1.

### TC-12 · BE error

**Steps**
1. Stop auth-service.
2. Refresh.

**Expected**
- ✅ ErrorBanner xuất hiện trên đầu table với RFC 7807 detail.
- ✅ Table body: "Đang tải workspace…" (vì isLoading false sau error).

### TC-13 · ADMIN / SUPPORT role check

**Steps**
1. Login as ADMIN role admin.
2. Navigate `/platform/workspaces`.

**Expected**
- ✅ Table render bình thường (mọi platform role thấy list).
- ✅ Button "+ Tạo workspace mới" KHÔNG hiện.
- ✅ Cột Hành động chỉ có Eye icon (không Edit, không Ban).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Click Ban icon là no-op (handler TODO). | Suspend qua `/platform/workspaces/{id}/edit` đổi status. |

## Related screens

- **UAT-PL-005** `/platform/workspaces/new` — TC nút "Tạo" navigate.
- **UAT-PL-006** `/platform/workspaces/{id}` — TC-5, TC-6 navigate.
- **UAT-PL-011** `/platform/workspaces/{id}/edit` — TC-7 navigate.
