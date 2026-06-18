# UAT-PL-014 · Platform Admin Detail

| | |
|---|---|
| **Mã test** | UAT-PL-014 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/admins/[id]` |
| **Source FE** | `frontend/app/platform/admins/[id]/page.tsx` |
| **Endpoints** | `GET /admins/{id}` · `PATCH /admins/{id}` |
| **Auth required** | Có (SUPER_ADMIN gate ở BE) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `9eebe01` (2026-05-18) |

---

## Mục tiêu test

Chi tiết 1 admin + 3 actions: edit (modal), reset password (link), toggle active/inactive (confirm modal).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN. |
| P2 | Admin tồn tại. |

## Test cases

### TC-1 · Render header + facts

**Steps**
1. Vào `/platform/admins/<id>`.

**Expected**
- ✅ Back link "← Tất cả quản trị viên".
- ✅ Header section bg-card border-b:
  - Icon halo lớn (p-3, w-7 h-7) theo role color (đã mô tả UAT-PL-012 TC-1).
  - Heading serif `text-2xl` = `full_name ?? email`.
  - Badges sau heading: role + (Vô hiệu nếu inactive) + (MFA nếu enabled).
  - Email muted text-sm dưới.
- ✅ Section "facts" grid 2-3 cols:
  - Đăng nhập gần nhất: fmtDateTime(last_login_at)
  - Ngày tạo: fmtDateTime(created_at)
  - MFA: "Đã bật" / "Chưa bật"

### TC-2 · Render hành động

**Steps**
1. Quan sát section "Hành động".

**Expected**
- ✅ 3 buttons:
  - "Đổi vai trò / tên" (secondary, icon UserCog) — opens edit modal
  - "Đặt lại mật khẩu" (secondary, icon KeyRound) — Link sang `/platform/admins/{id}/reset-password`
  - "Vô hiệu hóa" HOẶC "Kích hoạt lại" (destructive/primary, icon Power) — opens confirm modal

### TC-3 · Open edit modal

**Steps**
1. Click "Đổi vai trò / tên".

**Expected**
- ✅ Modal mở:
  - Header serif "Cập nhật quản trị viên" + X close button.
  - Label "Họ tên" + Input pre-filled.
  - Label "Vai trò" + select pre-selected current role.
- ✅ Footer: Hủy / "💾 Lưu" (gold).

### TC-4 · Submit edit

**Steps**
1. Đổi Họ tên "Test New Name".
2. Đổi role → ADMIN.
3. Click "Lưu".

**Expected**
- ✅ Button spinner.
- ✅ `PATCH /admins/{id}` 200 body `{full_name, role}`.
- ✅ React-query invalidate `['platform-admin', id]` + `['platform-admins']`.
- ✅ Modal close.
- ✅ Header card re-render với name + role mới.

### TC-5 · Reset password link

**Steps**
1. Click "Đặt lại mật khẩu".

**Expected**
- ✅ Navigate `/platform/admins/<id>/reset-password` (UAT-PL-015).

### TC-6 · Toggle inactive (when active)

**Steps**
1. Admin đang active, click "Vô hiệu hóa".

**Expected**
- ✅ Modal small confirm:
  - Header "Xác nhận vô hiệu hóa"
  - Text "<name> sẽ không thể đăng nhập cho đến khi được kích hoạt lại."
  - Buttons: Hủy / "Vô hiệu hóa" (destructive red).
- ✅ Click "Vô hiệu hóa" → `PATCH /admins/{id}` 200 với body `{is_active: false}`.
- ✅ Modal close.
- ✅ Header card re-render với badge "Vô hiệu" + button đổi thành "Kích hoạt lại" (primary gold).

### TC-7 · Toggle active (when inactive)

**Steps**
1. Admin đang inactive, click "Kích hoạt lại".

**Expected**
- ✅ Modal small confirm:
  - Header "Xác nhận kích hoạt lại"
  - Text "<name> sẽ được phép đăng nhập trở lại."
  - Buttons: Hủy / "Kích hoạt lại" (primary gold).
- ✅ Confirm → PATCH 200 với `{is_active: true}`.
- ✅ Badge "Vô hiệu" mất, button quay về "Vô hiệu hóa" (destructive).

### TC-8 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ Skeleton `h-72 animate-pulse` thay cho cả page body.

### TC-9 · BE 404

**Steps**
1. Nav direct `/platform/admins/00000000-0000-0000-0000-999999999999`.

**Expected**
- ✅ ErrorBanner: "Không thể tải quản trị viên.".

### TC-10 · Edit modal cancel

**Steps**
1. Open edit modal.
2. Đổi tên rồi click "Hủy" hoặc X.

**Expected**
- ✅ Modal close.
- ✅ Không PATCH gì.
- ✅ Mở lại edit modal → fields pre-fill từ data hiện tại (không nhớ change).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-012** /admins — return path.
- **UAT-PL-015** /admins/{id}/reset-password — TC-5.
