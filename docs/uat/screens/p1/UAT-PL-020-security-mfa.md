# UAT-PL-020 · Security MFA Enrolment

| | |
|---|---|
| **Mã test** | UAT-PL-020 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/security/mfa` (`/platform/security` redirect tới đây) |
| **Source FE** | `frontend/app/platform/security/mfa/page.tsx` + `/security/layout.tsx` |
| **Endpoints** | `POST /api/v1/platform/security/mfa/enable` · `POST /api/v1/platform/security/mfa/verify` |
| **Auth required** | Có (admin tự enrol cho chính mình) |
| **Phase** | Phase 1 ✅ (P2-S25 TOTP) |
| **Re-skin commit** | `c72a5de` (2026-05-18) |

---

## Mục tiêu test

Enrol TOTP cho admin đang login. 3 states: idle → pending (QR + verify) → verified.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role với `mfa_enabled = false` (default cho seed admin). |
| P2 | Có ứng dụng authenticator (Google Authenticator / 1Password / Authy / Aegis). |
| P3 | Đồng hồ máy + điện thoại đúng giờ. |

## Test cases

### TC-1 · Render layout (tab bar)

**Steps**
1. Click "Bảo mật → MFA" trong sidebar.

**Expected**
- ✅ Header section: icon ShieldCheck halo gold + heading "Bảo mật tài khoản" + description.
- ✅ Tab bar: Xác thực 2 lớp (active) · Phiên đăng nhập.

### TC-2 · Render idle state

**Steps**
1. Vào `/platform/security/mfa` (chưa enrol).

**Expected**
- ✅ Section status card:
  - Icon ShieldOff (halo grey neutral)
  - Heading "Xác thực 2 lớp (TOTP)"
  - Badge default "Chưa bật"
  - Description về Google Authenticator + AES-256-GCM lưu trữ
- ✅ Button "🛡 Bật MFA" (gold) ở phải.

### TC-3 · Click "Bật MFA" → pending state

**Steps**
1. Click button.

**Expected**
- ✅ Button spinner.
- ✅ `POST /api/v1/platform/security/mfa/enable` 200 body `{secret: "BASE32...", otpauth_url: "otpauth://totp/...", issuer, account}`.
- ✅ Status card vẫn hiện (top), nhưng có section thứ 2 mới appear bên dưới.
- ✅ Section "pending":
  - Yellow warning banner top: "Khoá bí mật chỉ hiển thị MỘT LẦN. Quét bằng ứng dụng xác thực hoặc lưu lại trước khi đóng trang."
  - 2-col grid:
    - **Bước 1: Quét QR** — heading + description + canvas 200×200 (QR rendered) + note "Không quét được? Dùng cách nhập thủ công bên cạnh."
    - **Hoặc nhập thủ công** — Input "Khoá bí mật (Base32)" readonly font-mono + Copy button; Input "otpauth URL" readonly font-mono text-xs + Copy button; line "Tài khoản: <issuer>: <account>"
  - Divider border-top + section "Bước 2: Nhập mã 6 chữ số" với Input font-mono text-xl text-center tracking-[0.4em] + button "✓ Xác thực" (disabled khi chưa đủ 6 chữ số)

### TC-4 · Copy secret

**Steps**
1. Click Copy button cạnh secret.

**Expected**
- ✅ `navigator.clipboard.writeText(secret)`.
- ✅ Icon Copy đổi thành Check 2s.

### TC-5 · Copy otpauth URL

**Steps**
1. Click Copy button cạnh URL.

**Expected**
- ✅ Tương tự TC-4 cho URL.

### TC-6 · Verify code thành công

**Steps**
1. Mở app authenticator → scan QR (hoặc nhập secret thủ công).
2. Lấy 6-digit code hiện tại.
3. Type vào Input → click "Xác thực".

**Expected**
- ✅ Button spinner.
- ✅ `POST /api/v1/platform/security/mfa/verify` 200.
- ✅ Section pending biến mất.
- ✅ Section status card top update:
  - Icon ShieldCheck (halo green `--state-success/15`)
  - Badge operational "Đã bật"
- ✅ Section thứ 3 appear bên dưới (success):
  - Border `--state-success/40`, bg tint green
  - Icon Check + heading "MFA đã được bật."
  - Text "Lần đăng nhập tiếp theo bạn sẽ cần nhập mã 6 chữ số từ ứng dụng xác thực."

### TC-7 · Verify code sai

**Steps**
1. Type 6-digit code sai (vd "000000").
2. Click "Xác thực".

**Expected**
- ✅ `POST /verify` 401.
- ✅ ErrorBanner xuất hiện trong section pending: "Không thể xác thực. Hãy chắc chắn đồng hồ điện thoại đúng giờ.".
- ✅ Section status card top KHÔNG đổi state (vẫn "Chưa bật").

### TC-8 · QR canvas render

**Steps**
1. DevTools Elements inspect `<canvas>` element.

**Expected**
- ✅ Canvas 200×200 px, render QR code đen-trắng.
- ✅ Background trắng `#FFFFFF`, foreground `#2F2F2F`.
- ✅ Error correction level M (margin 2px).

### TC-9 · Input only digits

**Steps**
1. Type "abc" vào Input verify.

**Expected**
- ✅ Input bị reject (regex `/\D/` strip).
- ✅ Field empty.

### TC-10 · Input maxLength 6 + auto-trim

**Steps**
1. Type "1234567890".

**Expected**
- ✅ Field chỉ giữ "123456" (slice(0, 6)).

### TC-11 · MFA đã enrol — UI rendered idempotent

**Steps**
1. Admin đã enrol MFA xong (state verified).
2. Refresh page.

**Expected**
- ⚠️ Hiện implementation: page reset về state `idle` (vì state local, không persist). Status badge sẽ "Chưa bật" sai.
- TODO: GET `/security/mfa/status` để fetch persistent state, hoặc gate enrol button khi BE confirm enabled.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Page không fetch persistent MFA state khi load — state chỉ enrol mới hiện. | Manually check qua DB hoặc trên detail admin (UAT-PL-014 fact "MFA: Đã bật"). |
| K-002 | QR fallback (nếu QR render fail) chỉ là manual entry block — không có error feedback explicit. | Acceptable Phase 1. |

## Related screens

- **UAT-PL-002** /platform/login/mfa — sử dụng TOTP đã enrol.
- **UAT-PL-021** /platform/security/sessions — tab kế.
- **UAT-PL-014** /platform/admins/{id} — verify MFA badge sau enrol.
