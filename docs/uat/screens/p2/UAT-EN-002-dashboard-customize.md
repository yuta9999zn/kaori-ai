# UAT-EN-002 · Dashboard Customize

| | |
|---|---|
| **Mã test** | UAT-EN-002 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/dashboard/customize` |
| **Source FE** | `frontend/components/p2/templates/10-dashboard-customize.tsx` |
| **Endpoint** | `GET/PATCH /api/v1/dashboard/layout` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ (F-028) |

---

## Mục tiêu test

Cho MANAGER drag-drop widgets trên dashboard layout, ẩn/hiện sections, lưu preference cho workspace.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |
| P2 | Workspace có data (KPIs renderable). |

## Test cases

### TC-1 · Render trang

**Steps**
1. Vào `/p2/dashboard/customize`.

**Expected**
- ✅ PageHeader "Tuỳ chỉnh dashboard".
- ✅ List widgets có toggle on/off + drag handle.
- ✅ Preview pane bên phải hiển thị dashboard với layout đang edit.
- ✅ Footer button "Lưu" + "Khôi phục mặc định".

### TC-2 · Toggle widget visibility

**Steps**
1. Toggle off widget "Open alerts".

**Expected**
- ✅ Preview pane ẩn widget.

### TC-3 · Drag-drop reorder

**Steps**
1. Drag handle widget thứ 1 xuống vị trí thứ 3.

**Expected**
- ✅ Preview re-order ngay.

### TC-4 · Save layout

**Steps**
1. Click "Lưu".

**Expected**
- ✅ `PATCH /dashboard/layout` 200 body `{visible_widgets, order}`.
- ✅ Toast "Đã lưu layout".

### TC-5 · Restore default

**Steps**
1. Click "Khôi phục mặc định".

**Expected**
- ✅ Confirm modal.
- ✅ Confirm → `DELETE /dashboard/layout` → restore stock layout.

### TC-6 · VIEWER không có quyền

**Steps**
1. Login VIEWER → nav `/p2/dashboard/customize`.

**Expected**
- ✅ BE 403, FE ErrorBanner "Bạn không có quyền truy cập".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-001** /p2/dashboard/overview — preview target.
