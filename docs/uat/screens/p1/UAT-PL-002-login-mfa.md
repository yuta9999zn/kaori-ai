# UAT-PL-002 · MFA Verification (Platform Admin)

| | |
|---|---|
| **Mã test** | UAT-PL-002 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/login/mfa` |
| **Source FE** | `frontend/app/platform/login/mfa/page.tsx` |
| **Source BE** | `auth-service` `PlatformAuthController.verifyMfa()` |
| **Endpoint** | `POST /auth/platform/mfa/verify` |
| **Auth required** | Không (public) — gated by sessionStorage challenge |
| **Roles target** | Admin với `mfa_enabled = true` |
| **Phase** | Phase 1 ✅ (B3 PR #8) |
| **Re-skin commit** | `89371fd` (2026-05-18) |

---

## Mục tiêu test

Bước 2 của 2-step gate: xác minh mã 6 chữ số TOTP từ ứng dụng authenticator (Google Authenticator / 1Password / Authy / Aegis). Đổi `mfa_challenge_token` lấy session đầy đủ rồi redirect `/platform`.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Đã hoàn thành UAT-PL-001 TC-3 — `sessionStorage` chứa `kaori.mfa_challenge_token`, `kaori.mfa_challenge_email`, `kaori.mfa_challenge_expires_at`. |
| P2 | Có ứng dụng authenticator setup với secret của admin (qua UAT-PL-020 enrol). |
| P3 | Đồng hồ máy đúng giờ (TOTP nhạy clock skew ±30s). |

## Test cases

### TC-1 · Render trang

**Steps**
1. Sau UAT-PL-001 TC-3, anh đã được redirect `/platform/login/mfa`.

**Expected**
- ✅ HTTP 200. Split-screen với `AuthBrandPanel` (cream gradient, headline "Một bước nữa," italic "xác minh danh tính.").
- ✅ Card phải: icon ShieldCheck halo + heading "Xác minh danh tính" + description chứa email masked dạng `a***@kaori.io`.
- ✅ Grid 6 input ô vuông `w-12 h-14 sm:w-14 sm:h-16`, mỗi ô border cream, tabular numerals.
- ✅ Line status dưới: "Mã làm mới sau 00:NN — phiên hết hạn sau M:SS".
- ✅ Submit button "Xác minh" — gold background, disabled khi chưa đủ 6 ký tự.
- ✅ Link "← Quay lại đăng nhập" dưới card.

### TC-2 · Verify thành công

**Steps**
1. Mở app authenticator → lấy 6-digit code hiện tại của admin.
2. Type code vào ô đầu tiên — auto advance ô tiếp.
3. Sau khi gõ ký tự thứ 6, auto-submit fires (không cần click button).

**Expected**
- ✅ `POST /auth/platform/mfa/verify` 200 với body `{access_token, refresh_token, session_id, admin_id, role}`.
- ✅ `sessionStorage.kaori.mfa_challenge_token` cleared.
- ✅ `sessionStorage.kaori.mfa_challenge_email` cleared.
- ✅ `sessionStorage.kaori.mfa_challenge_expires_at` cleared.
- ✅ `localStorage.kaori.access_token` set với token mới.
- ✅ `localStorage.kaori.auth` cập nhật `user.role` đúng từ response.
- ✅ URL navigate `/platform`.

### TC-3 · Mã sai (`AUTH.MFA_INVALID_CODE`)

**Steps**
1. Type 6 chữ số ngẫu nhiên (không phải code hợp lệ).

**Expected**
- ✅ Auto-submit fires.
- ✅ `POST /auth/platform/mfa/verify` 401 RFC 7807 với `code: "AUTH.MFA_INVALID_CODE"`.
- ✅ 6 input box **animate shake** (class `animate-shake`), border đổi sang red `--state-error/40`.
- ✅ Tất cả 6 input bị clear.
- ✅ Focus trở về input đầu tiên.
- ✅ Line status đổi thành red text: "Mã xác thực không đúng. Vui lòng thử lại."
- ✅ Animation shake kéo ~400ms rồi style border quay về normal (sau khi user gõ ký tự đầu).

### TC-4 · Challenge expired (`AUTH.MFA_CHALLENGE_EXPIRED`)

**Steps**
1. Đợi 5+ phút (challenge JWT exp = 300s).
2. Hoặc manually sửa `sessionStorage.kaori.mfa_challenge_expires_at` thành timestamp < now để force auto-redirect.

**Expected (cách 1 — đợi tự nhiên)**
- ✅ Khi countdown chạm 0:00, page auto-redirect `/platform/login?mfa_expired=1` (không gọi `verify` endpoint).
- ✅ `sessionStorage` 3 keys cleared.

**Expected (cách 2 — submit code khi BE từ chối)**
- ✅ `POST /auth/platform/mfa/verify` 401 `code: "AUTH.MFA_CHALLENGE_EXPIRED"` hoặc `AUTH.MFA_CHALLENGE_INVALID`.
- ✅ `sessionStorage` cleared.
- ✅ Auto-redirect `/platform/login?mfa_expired=1`.

### TC-5 · Paste 6-digit code

**Steps**
1. Copy 6-digit code "123456" vào clipboard.
2. Click ô đầu tiên → Ctrl+V (paste).

**Expected**
- ✅ Cả 6 ô đều fill ngay lần paste, mỗi ô 1 chữ số.
- ✅ Focus chuyển về ô thứ 6 (cuối).
- ✅ Auto-submit fires (vì đã đủ 6 ký tự).

### TC-6 · Keyboard nav

**Steps**
1. Click ô thứ 3.
2. Nhấn ←  → → → để di chuyển giữa các ô.
3. Type "5" ở ô 3.
4. Backspace ở ô 4 (empty) → focus chuyển ngược về ô 3.
5. Backspace tiếp ở ô 3 → clear ô 3.

**Expected**
- ✅ Arrow keys chuyển focus đúng (left/right giới hạn 0-5).
- ✅ Backspace trên empty box chuyển focus về box trước + clear box đó.
- ✅ Backspace trên filled box clear box hiện tại, focus đứng yên.

### TC-7 · Disable input khi loading

**Steps**
1. Type 6-digit code → auto-submit fires.
2. Trong khi pending (`POST /verify` đang chờ response), thử type thêm.

**Expected**
- ✅ Mọi input có `disabled` attribute, opacity 0.5.
- ✅ Type không có hiệu lực.
- ✅ Submit button cũng disabled + spinner Loader2.

### TC-8 · Countdown 2 cấp

**Steps**
1. Quan sát line status "Mã làm mới sau 00:NN — phiên hết hạn sau M:SS".

**Expected**
- ✅ **Step countdown** (TOTP 30s) chạy từ 00:30 → 00:00 → 00:30 (loop, vì TOTP rolls mỗi 30s).
- ✅ **Challenge countdown** chạy giảm dần từ ~5:00 → 0:00 (1 chiều, không loop).
- ✅ Khi challenge countdown đạt 0, redirect TC-4 cách 1.

### TC-9 · Back link

**Steps**
1. Click "← Quay lại đăng nhập".

**Expected**
- ✅ URL navigate `/platform/login`.
- ✅ `sessionStorage` 3 keys vẫn còn (NOT cleared by back link — user có thể quay lại submit).

### TC-10 · Missing challenge (deep link)

**Steps**
1. Browser console: `sessionStorage.clear();`
2. Navigate trực tiếp `/platform/login/mfa`.

**Expected**
- ✅ `useEffect` hydrate phát hiện missing token + expires_at → `router.replace('/platform/login')`.
- ✅ Không request `verify` endpoint.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-001** `/platform/login` — flow vào đây từ TC-3.
- **UAT-PL-003** `/platform` — TC-2 chuyển sang đây.
- **UAT-PL-020** `/platform/security/mfa` — enrol TOTP để có MFA-enabled account.
