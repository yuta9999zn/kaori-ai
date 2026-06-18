# UAT-PL-015 · Reset Password Admin

| | |
|---|---|
| **Mã test** | UAT-PL-015 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/admins/[id]/reset-password` |
| **Source FE** | `frontend/app/platform/admins/[id]/reset-password/page.tsx` |
| **Endpoint** | `POST /api/v1/platform/admins/{id}/reset-password` |
| **Auth required** | Có (SUPER_ADMIN) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `9eebe01` (2026-05-18) |

---

## Mục tiêu test

Trigger gửi email đặt lại mật khẩu cho admin (BE tạo reset token, gửi email link). Trang confirm thay vì action ngay để tránh accidental click.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN. |
| P2 | Admin target tồn tại. |
| P3 | SMTP service (notification-service) reachable nếu muốn verify email thật. |

## Test cases

### TC-1 · Render confirm screen

**Steps**
1. Vào `/platform/admins/<id>/reset-password` (từ UAT-PL-014 TC-5).

**Expected**
- ✅ Back link "← Quay lại chi tiết".
- ✅ PageHeader "Đặt lại mật khẩu" + description "<full_name> · <email>".
- ✅ Section warning banner vàng:
  - Icon ShieldAlert + heading "Hành động này:"
  - Bullet list:
    1. Gửi email tới <email> với liên kết đặt lại mật khẩu.
    2. Vô hiệu hóa các phiên đăng nhập hiện tại của tài khoản này.
    3. (Nếu MFA enabled) "Giữ nguyên thiết lập MFA — người dùng vẫn cần TOTP để đăng nhập." HOẶC (MFA disabled) "KHÔNG bật MFA — bạn nên yêu cầu người dùng bật MFA sau khi đặt lại.".
    4. Ghi nhận trong nhật ký kiểm toán dưới dạng `admin.password_reset_requested`.
- ✅ Footer buttons: Hủy / "🔑 Gửi email đặt lại mật khẩu".

### TC-2 · Submit thành công

**Steps**
1. Click "Gửi email đặt lại mật khẩu".

**Expected**
- ✅ Button spinner.
- ✅ `POST /admins/{id}/reset-password` 200 với body `{data: {reset_token_sent_to: "<email>"}}`.
- ✅ Page body thay thành success card xanh:
  - Icon CheckCircle2 + heading "Đã gửi email"
  - Text: "Liên kết đặt lại mật khẩu đã được gửi tới <email>. Token có hiệu lực trong 60 phút."
  - Button "Quay lại chi tiết" (secondary).

### TC-3 · Click "Quay lại chi tiết" sau success

**Steps**
1. Sau TC-2, click button "Quay lại chi tiết".

**Expected**
- ✅ Navigate `/platform/admins/<id>` (UAT-PL-014).

### TC-4 · Cancel

**Steps**
1. Trên confirm screen, click "Hủy".

**Expected**
- ✅ Navigate `/platform/admins/<id>` (back to detail).

### TC-5 · Back link

**Steps**
1. Click "← Quay lại chi tiết".

**Expected**
- ✅ Navigate `/platform/admins/<id>`.

### TC-6 · BE error

**Steps**
1. Stop notification-service hoặc SMTP fail.
2. Click submit.

**Expected**
- ✅ `POST` 500 hoặc 503 RFC 7807.
- ✅ ErrorBanner trên đầu section warning.
- ✅ Confirm screen vẫn ở trạng thái pre-submit (không success card).

### TC-7 · MFA-enabled vs disabled copy

**Steps**
1. Reset password cho admin MFA-enabled.
2. Reset password cho admin MFA-disabled.

**Expected**
- ✅ MFA-enabled: bullet 3 hiện "Giữ nguyên thiết lập MFA...".
- ✅ MFA-disabled: bullet 3 hiện "KHÔNG bật MFA — bạn nên...".

### TC-8 · Audit log entry

**Steps**
1. Sau TC-2 success, vào `/platform/workspaces/<any-ws-id>/audit` hoặc admin audit endpoint.

**Expected**
- ✅ Mới có event `admin.password_reset_requested` với actor = SUPER_ADMIN đang login, target = admin được reset.

### TC-9 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ Skeleton `h-72 animate-pulse` thay cho page body.

### TC-10 · BE 404 (admin không tồn tại)

**Steps**
1. Nav direct với invalid id.

**Expected**
- ✅ ErrorBanner: "Không thể tải quản trị viên.".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-014** /admins/{id} — return path.
