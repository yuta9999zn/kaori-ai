# UAT-PL-001 · Đăng nhập Platform Admin

| | |
|---|---|
| **Mã test** | UAT-PL-001 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/login` |
| **Source FE** | `frontend/app/platform/login/page.tsx` |
| **Source BE** | `auth-service` `PlatformAuthController.login()` |
| **Endpoint** | `POST /auth/platform/login` |
| **Auth required** | Không (public) |
| **Roles target** | `SUPER_ADMIN` / `ADMIN` / `SUPPORT` |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `89371fd` (2026-05-18) |

---

## Mục tiêu test

Đăng nhập tài khoản Kaori staff (SUPER_ADMIN / ADMIN / SUPPORT) qua flow 2-step:
- **Step 1** — Email + mật khẩu → `POST /auth/platform/login`.
- **Step 2** — Nếu admin có MFA enable → redirect `/platform/login/mfa` (xem UAT-PL-002). Không MFA → set auth state + redirect `/platform`.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Stack docker đang chạy. Xem `_SETUP.md` mục 1. |
| P2 | Admin platform đã seed: `superadmin@kaori.local` / `Kaori@Admin1` (MFA off mặc định). |
| P3 | Dev server frontend chạy ở `http://localhost:3000` mode `webpack`. |
| P4 | `localStorage` và `sessionStorage` empty (browser console: `localStorage.clear(); sessionStorage.clear();`). |
| P5 | DevTools Network tab mở. |

## Test cases

### TC-1 · Render trang (happy path)

**Steps**
1. Navigate `http://localhost:3000/platform/login`.

**Expected**
- ✅ HTTP 200.
- ✅ Render split-screen: trái `AuthBrandPanel` cream gradient, phải card form trắng.
- ✅ Panel trái: dot pattern + 2 blurred gradient circles + headline serif "Khu vực vận hành," italic "dành cho đội Kaori." + subhead + footer "© 2026 Kaori Platform".
- ✅ Card phải: chip viền gold "PLATFORM ADMIN" (icon Shield trắng trên nền gold tint), heading serif "Đăng nhập quản trị", description "Tài khoản nhân sự Kaori (SUPER_ADMIN / ADMIN / SUPPORT).".
- ✅ Form fields: `Email công vụ` (type=email, placeholder "ops@kaori.io"), `Mật khẩu` (type=password, placeholder "••••••••" + eye toggle bên phải).
- ✅ Submit button **"Đăng nhập vào Platform"** — background **gold `#D4B88A`** (KHÔNG trắng / transparent).
- ✅ Footer dưới card: "Không phải nhân sự Kaori? Cổng đăng nhập doanh nghiệp" → link `/login`.

### TC-2 · Đăng nhập thành công (no MFA)

**Steps**
1. Fill email: `superadmin@kaori.local`
2. Fill password: `Kaori@Admin1`
3. Click "Đăng nhập vào Platform".

**Expected**
- ✅ Network tab: `POST /auth/platform/login` 200, response body chứa `access_token`, `refresh_token`, `admin_id`, `role: "SUPER_ADMIN"`, `mfa_required: false`, `mfa_enabled: false`, `expires_in_sec`.
- ✅ URL navigate `/platform` (dashboard).
- ✅ `localStorage.kaori.access_token` đã set (string JWT).
- ✅ `localStorage.kaori.auth` đã set, parse JSON ra `{user: {id, email, role: "SUPER_ADMIN", session_id}, accessToken, refreshToken, tokenKind: "platform"}`.
- ✅ Sidebar cream `#F5F1EA` xuất hiện bên trái + dashboard content render với KPI cards.

### TC-3 · Login MFA required (chuyển TC sang UAT-PL-002)

**Pre-condition bổ sung**: admin có `mfa_enabled = true`. Để setup, login bằng `superadmin@kaori.local`, vào `/platform/security/mfa`, enrol TOTP (UAT-PL-020), rồi logout, mở lại `/platform/login`.

**Steps**
1. Fill email + password của admin MFA-enabled.
2. Click "Đăng nhập vào Platform".

**Expected**
- ✅ `POST /auth/platform/login` 200 với `mfa_required: true`, `mfa_challenge_token`, `mfa_challenge_expires_in_sec: 300`.
- ✅ `sessionStorage.kaori.mfa_challenge_token` đã set.
- ✅ `sessionStorage.kaori.mfa_challenge_email` đã set (email từ form).
- ✅ `sessionStorage.kaori.mfa_challenge_expires_at` đã set (timestamp ms = now + 300_000).
- ✅ URL navigate `/platform/login/mfa`.

### TC-4 · Sai email/mật khẩu (401)

**Steps**
1. Fill email: `wrong@wrong.com`
2. Fill password: `wrong123`
3. Click submit.

**Expected**
- ✅ `POST /auth/platform/login` 401, response `application/problem+json`.
- ✅ Red ErrorBanner xuất hiện đầu form: **"Email hoặc mật khẩu không đúng."**.
- ✅ Form fields KHÔNG bị clear (anh sửa lại + submit tiếp được).
- ✅ URL không đổi (vẫn `/platform/login`).
- ✅ `localStorage` không thay đổi.

### TC-5 · Tài khoản bị khóa (423 lockout)

**Steps**
1. Submit wrong creds (cùng email + password sai) 5+ lần liên tiếp.

**Expected**
- ✅ Sau lần ~5 (BE config): `POST /auth/platform/login` **423** RFC 7807 với `lockout_remaining_seconds` (ví dụ 900s = 15 phút).
- ✅ ErrorBanner: **"Tài khoản bị khóa. Thử lại sau N phút."** (N = `Math.ceil(secs / 60)`).
- ✅ Dưới password field xuất hiện line text: **"Còn Ns trước khi thử lại."** (countdown, chưa decrement ở phiên bản hiện tại).
- ✅ Submit button vẫn clickable (BE tiếp tục trả 423 cho tới khi hết lockout window).

### TC-6 · Toggle show/hide password

**Steps**
1. Fill password ngẫu nhiên.
2. Click icon Eye bên phải password input.

**Expected**
- ✅ Password input type chuyển `password` → `text` (text giờ visible).
- ✅ Icon `EyeOff` hiện thay `Eye`.
- ✅ Click lại → ngược lại (`text` → `password`, `Eye` ← `EyeOff`).
- ✅ Aria-label switch giữa "Hiện mật khẩu" và "Ẩn mật khẩu".
- ✅ Toggle button `disabled` khi đang submit (`loading=true`).

### TC-7 · Cream/gold tokens defined ở `:root`

**Steps**
1. DevTools → Elements → click `<html>` element → tab Computed Styles.
2. Filter "primary-gold".

**Expected (mọi token sau phải có giá trị tương ứng):**
- ✅ `--primary-gold: #D4B88A`
- ✅ `--primary-gold-dark: #BFA88C`
- ✅ `--bg-app: #FAF7F2`
- ✅ `--bg-card: #FFFFFF`
- ✅ `--bg-sidebar: #F5F1EA`
- ✅ `--border-color: #E9E7E2`
- ✅ `--text-primary: #2F2F2F`
- ✅ `--text-secondary: #8C8173`
- ✅ `--state-success: #8FBFA0`
- ✅ `--state-warning: #E6C07B`
- ✅ `--state-error: #D97C7C`
- ✅ `--state-info: #A5B4CB`

Nếu thiếu → button background sẽ trắng. Fix landed commit `77cc281` (alias tokens vào `globals.css :root`).

### TC-8 · Validate empty submit

**Steps**
1. Để cả 2 field trống.
2. Click submit.

**Expected**
- ✅ Trình duyệt show native required-validation bubble cho field email trước (HTML5 `required` attribute).
- ✅ Không có network request gửi đi.

### TC-9 · Responsive (mobile)

**Steps**
1. DevTools → Device toolbar → chọn iPhone 14 Pro (390x844).
2. Reload `/platform/login`.

**Expected**
- ✅ Panel trái (`AuthBrandPanel`) ẩn (`hidden lg:flex`).
- ✅ Card form full width với padding `p-6 sm:p-12`.
- ✅ Mobile logo (`MobileLogo`) hiện ở góc trên-trái: "Kaori Platform" lockup nhỏ.

### TC-10 · Network failure (server unreachable)

**Steps**
1. Tạm dừng `auth-service`: `docker compose stop auth-service`.
2. Submit form với creds hợp lệ.

**Expected**
- ✅ Sau ~10-30s (timeout), ErrorBanner: **"Không thể đăng nhập. Vui lòng thử lại."**.
- ✅ Submit button quay về clickable state.

(Restart sau test: `docker compose start auth-service`.)

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Countdown "Còn Ns trước khi thử lại." không tự tick xuống — chỉ hiển thị số tĩnh từ response. | Reload trang sau N giây. Improvement defer. |
| K-002 | Show/hide password chưa lưu state qua reload. | Acceptable per spec. |

## Related screens

- **UAT-PL-002** `/platform/login/mfa` — TC-3 flow chuyển sang đây.
- **UAT-PL-003** `/platform` — TC-2 flow chuyển sang đây.
- **UAT-EN-???** `/login` — link footer "Cổng đăng nhập doanh nghiệp".
