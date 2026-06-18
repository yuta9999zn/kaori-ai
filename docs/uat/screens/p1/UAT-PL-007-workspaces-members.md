# UAT-PL-007 · Workspace Members

| | |
|---|---|
| **Mã test** | UAT-PL-007 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/[id]/members` |
| **Source FE** | `frontend/app/platform/workspaces/[id]/members/page.tsx` |
| **Endpoints** | `GET /workspaces/{id}/members` · `POST /workspaces/{id}/members` · `DELETE /workspaces/{id}/members/{userId}` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ pending BE (per platform.ts JSDoc) |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

CRUD thành viên trong 1 workspace: list, invite (open modal), remove (confirm modal).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Workspace + ≥ 1 member tồn tại. |

## Test cases

### TC-1 · Render list

**Steps**
1. Vào `/platform/workspaces/<uuid>/members`.

**Expected**
- ✅ Header line: "Tổng cộng N thành viên" + button "+ Mời thành viên".
- ✅ Table columns: Thành viên · Vai trò · Trạng thái · Đăng nhập gần nhất · Tham gia · (trash icon).
- ✅ Mỗi row: avatar tròn gold initials + full_name (hoặc email) + email muted dưới.
- ✅ Role badge variant: MANAGER → current (gold), OPERATOR → info, ANALYST → operational, VIEWER → default.
- ✅ Status badge: active → operational, pending → warning, inactive → default.

### TC-2 · Open invite modal

**Steps**
1. Click "+ Mời thành viên".

**Expected**
- ✅ Modal overlay xuất hiện (backdrop blur).
- ✅ Modal header: "Mời thành viên" + description.
- ✅ Fields: Email input (type=email, placeholder "ten@congty.com") + select Vai trò (default VIEWER).
- ✅ Info banner xanh: "Mỗi workspace cần ít nhất một người vai trò Quản lý (MANAGER) để vận hành.".
- ✅ Buttons: Hủy / Gửi lời mời (disabled khi email empty).

### TC-3 · Submit invite

**Steps**
1. Fill email "new@test.com".
2. Chọn role "ANALYST".
3. Click "Gửi lời mời".

**Expected**
- ✅ Button hiện spinner.
- ✅ `POST /workspaces/{id}/members` 200 với body `{email, role}`.
- ✅ Modal close.
- ✅ Table refresh (react-query invalidate `['workspace-members', id]`).
- ✅ Row mới appears trong table với status "pending".

### TC-4 · Invite error

**Steps**
1. Fill email không hợp lệ "abc".
2. Submit.

**Expected**
- ✅ Native browser validation block submit.
- (Nếu vượt qua FE) BE 400 → ErrorBanner trong modal.

### TC-5 · Close invite modal

**Steps**
1. Click backdrop (outside modal) hoặc click "Hủy" hoặc click X icon.

**Expected**
- ✅ Modal close.
- ✅ Form values cleared (email = "", role = VIEWER).

### TC-6 · Remove member

**Steps**
1. Click icon trash ở row member bất kỳ.

**Expected**
- ✅ Modal nhỏ confirm: "Xóa thành viên" header + text "Xóa <name>? Người dùng sẽ mất quyền truy cập ngay lập tức.".
- ✅ Buttons: Hủy / "Xóa thành viên" (red).
- ✅ Click "Xóa thành viên" → `DELETE /workspaces/{id}/members/{userId}` 200.
- ✅ Modal close + row mất khỏi table.

### TC-7 · BE pending (404)

**Steps**
1. Stop endpoint cụ thể (hoặc nếu chưa wire backend).

**Expected**
- ✅ ErrorBanner trên table: "Backend GET /workspaces/<id>/members chưa sẵn sàng.".

### TC-8 · Empty state

**Steps**
1. Workspace không có member nào.

**Expected**
- ✅ Header line: "Quản lý người dùng và quyền truy cập trong workspace.".
- ✅ Table body 1 row colspan=6: "Chưa có thành viên nào trong workspace này.".

### TC-9 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 4 skeleton row `h-14 animate-pulse` thay cho table.

### TC-10 · Tab persistence

**Steps**
1. Click tab "Khoá API" rồi quay lại "Thành viên".

**Expected**
- ✅ Members table render lại (react-query cache hit, không re-fetch).
- ✅ Header card (layout) không re-render.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | BE endpoint members có thể chưa fully wired (per `lib/api/platform.ts` JSDoc PENDING). | Test sẽ pass-with-banner thay vì pass-with-data. |

## Related screens

- **UAT-PL-006** parent tab Tổng quan.
- **UAT-PL-008** /keys, **UAT-PL-009** /billing, etc.
