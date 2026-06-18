# UAT-PL-021 · Active Sessions

| | |
|---|---|
| **Mã test** | UAT-PL-021 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/security/sessions` |
| **Source FE** | `frontend/app/platform/security/sessions/page.tsx` |
| **Endpoints** | `GET /security/sessions` · `POST /security/sessions/{id}/revoke` · `POST /security/sessions/revoke-others` |
| **Auth required** | Có (admin tự xem phiên của chính mình) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `c72a5de` (2026-05-18) |

---

## Mục tiêu test

Liệt kê các phiên (sessions) đang active của admin đang login. Revoke 1 phiên cụ thể hoặc revoke-all-other.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | (Optional) Login đồng thời từ 2+ browser/device khác để có nhiều sessions. |

## Test cases

### TC-1 · Render khi có 1 session (current only)

**Steps**
1. Click tab "Phiên đăng nhập".

**Expected**
- ✅ Header line: "1 phiên đang hoạt động" (NO "Thu hồi tất cả phiên khác" button vì otherCount = 0).
- ✅ 1 session card với border + bg gold tint `--primary-gold/8` (current session highlight):
  - Icon device (Monitor cho desktop, Smartphone cho mobile UA) trong square halo bg-app.
  - Label device + Badge `current` "Phiên hiện tại".
  - Detail block text-xs: IP `<ip>`, UA truncate font-mono, "Hoạt động lần cuối <datetime>. Bắt đầu <datetime>.".
  - Button "Thu hồi" (variant tertiary, text red `#9B5050`).

### TC-2 · Render khi có 2+ sessions

**Pre-condition bổ sung**: login đồng thời từ browser khác (private mode hoặc browser khác).

**Steps**
1. Quan sát.

**Expected**
- ✅ Header line: "N phiên đang hoạt động" + button "🛡 Thu hồi tất cả phiên khác (M)" (M = N-1).
- ✅ Stack session cards:
  - Current session: border gold + bg gold tint.
  - Other sessions: border `--border-color` thường + bg-card trắng.

### TC-3 · Revoke non-current session

**Steps**
1. Click trash icon ở session card khác (không phải current).

**Expected**
- ✅ Modal small confirm:
  - Header "Thu hồi phiên"
  - Text "Thu hồi phiên trên <device_label>? Người dùng sẽ bị đăng xuất ngay."
  - Buttons: Hủy / "Thu hồi phiên" (red).
- ✅ Click "Thu hồi phiên" → `POST /security/sessions/{id}/revoke` 200 với `meta: {signed_out: false}`.
- ✅ Modal close.
- ✅ Session card biến mất.
- ✅ Header count giảm.

### TC-4 · Revoke current session (self)

**Steps**
1. Click trash icon ở current session card.

**Expected**
- ✅ Modal small confirm:
  - Header "Đăng xuất khỏi thiết bị này?"
  - Text "Đây là phiên bạn đang dùng. Sau khi thu hồi, token sẽ hết hạn và bạn cần đăng nhập lại."
  - Buttons: Hủy / "Thu hồi phiên" (red).
- ✅ Confirm → `POST /security/sessions/{id}/revoke` 200 với `meta: {signed_out: true}`.
- ✅ Modal close.
- ✅ Post-revoke yellow banner appears top: "Bạn vừa thu hồi phiên hiện tại. Có thể cần đăng nhập lại sau khi token hết hạn.".

### TC-5 · Revoke all other sessions

**Steps**
1. Click button "Thu hồi tất cả phiên khác (M)".

**Expected**
- ✅ Modal small confirm:
  - Header "Thu hồi tất cả phiên khác?"
  - Text "Sẽ đăng xuất M thiết bị khác đang dùng tài khoản này. Phiên hiện tại của bạn sẽ vẫn hoạt động bình thường."
  - Buttons: Hủy / "Thu hồi tất cả (M)" (red).
- ✅ Click confirm → `POST /security/sessions/revoke-others` 200 với `data: {revoked_count: M}`.
- ✅ Modal close.
- ✅ Green success banner: "Đã thu hồi M phiên khác. Phiên hiện tại của bạn vẫn hoạt động.".
- ✅ Session list re-fetch (chỉ còn current session).

### TC-6 · Revoke all when 0 others

**Steps**
1. Chỉ có current session.

**Expected**
- ✅ Button "Thu hồi tất cả phiên khác" KHÔNG xuất hiện (otherCount = 0).

### TC-7 · Device icon detection

**Steps**
1. Login từ Chrome desktop → expect icon Monitor.
2. Login từ Safari iOS / Chrome Android → expect icon Smartphone.

**Expected**
- ✅ Helper `deviceIcon(label)` check UA chứa "iphone" / "android" / "ios" → Smartphone, else Monitor.

### TC-8 · Empty state

**Steps**
1. (Edge case — không reproduce được vì cần ≥ 1 session để view page).

**Expected**
- ✅ Card placeholder: "Chưa có phiên hoạt động nào được ghi nhận.".

### TC-9 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 2 skeleton cards `h-20 animate-pulse`.

### TC-10 · BE error

**Steps**
1. Stop auth-service.

**Expected**
- ✅ ErrorBanner: "Không thể tải danh sách phiên đăng nhập.".

### TC-11 · Revoke-all error

**Steps**
1. BE 500 khi revoke-others.

**Expected**
- ✅ ErrorBanner trong modal confirm.
- ✅ Modal vẫn open để user retry.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | UA parse đơn giản, mobile/desktop detection chưa cover hết platforms. | Cập nhật helper khi cần. |

## Related screens

- **UAT-PL-020** /platform/security/mfa — tab anh em.
- **UAT-PL-001** /platform/login — quay về sau khi revoke current.
