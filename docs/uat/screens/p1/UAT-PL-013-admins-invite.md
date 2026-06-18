# UAT-PL-013 · Mời Platform Admin mới

| | |
|---|---|
| **Mã test** | UAT-PL-013 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/admins/invite` |
| **Source FE** | `frontend/app/platform/admins/invite/page.tsx` |
| **Endpoint** | `POST /api/v1/platform/admins` |
| **Auth required** | Có (SUPER_ADMIN) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `9eebe01` (2026-05-18) |

---

## Mục tiêu test

Form invite Kaori staff mới với 3 fields (Họ tên + Email + Vai trò) + info banner mô tả role.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN. |

## Test cases

### TC-1 · Render form

**Steps**
1. Vào `/platform/admins/invite`.

**Expected**
- ✅ Back link "← Tất cả quản trị viên".
- ✅ PageHeader "Mời quản trị viên" + description.
- ✅ Section card chứa form:
  - Label "Họ tên" + Input (required, autofocus, placeholder "VD: Nguyễn Văn A")
  - Label "Email" + Input type=email (required, placeholder "ten@kaori.io")
  - Label "Vai trò" + native `<select>`:
    - SUPPORT (default selected) — "Hỗ trợ kỹ thuật (SUPPORT)"
    - ADMIN — "Quản trị viên (ADMIN)"
    - SUPER_ADMIN — "Super Admin (SUPER_ADMIN — yêu cầu MFA)"
  - Info banner xanh: icon Headphones (cho SUPPORT default) + description "Chỉ đọc — hỗ trợ kỹ thuật và xử lý yêu cầu khách hàng."
- ✅ Footer buttons: Hủy / "📧 Gửi lời mời" (disabled khi email hoặc fullName empty).

### TC-2 · Role description đổi theo select

**Steps**
1. Đổi role select sang ADMIN.

**Expected**
- ✅ Info banner đổi icon → UserCog + description: "Quản trị workspace, thành viên, billing. Không thể tạo SUPER_ADMIN.".

**Steps**
2. Đổi role select sang SUPER_ADMIN.

**Expected**
- ✅ Icon → ShieldCheck.
- ✅ Description: "Toàn quyền vận hành nền tảng. Bắt buộc bật MFA.".

### TC-3 · Submit thành công

**Steps**
1. Fill Họ tên "Test Admin".
2. Fill Email "newadmin@kaori.io".
3. Chọn role SUPPORT.
4. Click "Gửi lời mời".

**Expected**
- ✅ Button spinner.
- ✅ `POST /api/v1/platform/admins` 200 với body `{email, full_name, role}`.
- ✅ Response: `{data: {id: <uuid>, email, full_name, role, is_active: true, mfa_enabled: false, ...}}`.
- ✅ React-query invalidate `['platform-admins']`.
- ✅ URL navigate `/platform/admins/<new id>` (UAT-PL-014).

### TC-4 · Submit thất bại (email duplicate)

**Steps**
1. Fill email đã exist trong DB.
2. Submit.

**Expected**
- ✅ `POST` 409 RFC 7807.
- ✅ ErrorBanner appears với detail.

### TC-5 · Validate empty submit

**Steps**
1. Để email + fullName empty.

**Expected**
- ✅ Button "Gửi lời mời" disabled (HTML attribute, không clickable).

### TC-6 · Cancel

**Steps**
1. Click "Hủy".

**Expected**
- ✅ Navigate `/platform/admins`.

### TC-7 · Back link

**Steps**
1. Click "← Tất cả quản trị viên".

**Expected**
- ✅ Navigate `/platform/admins`.

### TC-8 · Cream/gold tokens

**Steps**
1. Quan sát button "Gửi lời mời".

**Expected**
- ✅ Background gold `#D4B88A` (variant primary).
- ✅ Disabled state: opacity 50%, pointer-events-none.

### TC-9 · Email format validate

**Steps**
1. Fill email "abc" (không format email).
2. Click submit.

**Expected**
- ✅ Native HTML5 type=email validator block submit + bubble error.

### TC-10 · Network failure

**Steps**
1. Stop auth-service.
2. Submit.

**Expected**
- ✅ ErrorBanner generic error.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-012** /admins — return path.
- **UAT-PL-014** /admins/{id} — success destination.
