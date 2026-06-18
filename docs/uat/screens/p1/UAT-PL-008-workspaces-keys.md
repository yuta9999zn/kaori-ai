# UAT-PL-008 · Workspace API Keys

| | |
|---|---|
| **Mã test** | UAT-PL-008 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/[id]/keys` |
| **Source FE** | `frontend/app/platform/workspaces/[id]/keys/page.tsx` |
| **Endpoints** | `GET/POST /workspaces/{id}/keys` · `POST /workspaces/{id}/keys/{keyId}/revoke` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

Quản lý KAORI-API keys của workspace: list, generate (reveal once), revoke.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Workspace tồn tại. |

## Test cases

### TC-1 · Render list

**Steps**
1. Vào `/platform/workspaces/<uuid>/keys`.

**Expected**
- ✅ Header line: "N khoá đang hoạt động trên tổng số M" + button "+ Tạo khoá mới".
- ✅ Table columns: Khoá · Trạng thái · Tạo lúc · Thu hồi lúc · (trash icon).
- ✅ Mỗi row: avatar tròn gold (KeyRound icon) + label (hoặc "Không có nhãn") + key_id mask `abcd…wxyz` font-mono.
- ✅ Status badge: active → operational, revoked → default (grey).

### TC-2 · Create key — open modal

**Steps**
1. Click "+ Tạo khoá mới".

**Expected**
- ✅ Modal mở: header "Tạo khoá API mới" + description "Khoá sẽ chỉ hiển thị một lần duy nhất sau khi tạo.".
- ✅ Field: Nhãn (optional, placeholder "ví dụ: ci-runner, stg-deploy", maxLength=100).
- ✅ Info banner xanh ShieldCheck: "Khoá được sinh ngẫu nhiên 160-bit (định dạng KAORI-XXXXXXXX-…) và chỉ lưu hash SHA-256 trên máy chủ.".
- ✅ Buttons: Hủy / + Tạo khoá.

### TC-3 · Submit tạo khoá → reveal state

**Steps**
1. Fill nhãn "test-key-01".
2. Click "+ Tạo khoá".

**Expected**
- ✅ `POST /workspaces/{id}/keys` 200 body `{data: {key_id, label, raw_key: "KAORI-XXX...", ...}}`.
- ✅ Modal switch sang reveal state:
  - Yellow warning banner: "Đây là lần duy nhất khoá hiển thị đầy đủ. Hãy lưu vào kho mật khẩu hoặc biến môi trường ngay bây giờ.".
  - Readonly Input field "Khoá API" với raw_key (autoselect on focus).
  - Button "Sao chép" (icon Copy).
  - Button "Tôi đã sao chép" (icon Check) ở footer.

### TC-4 · Copy to clipboard

**Steps**
1. Ở reveal state, click "Sao chép".

**Expected**
- ✅ `navigator.clipboard.writeText(raw_key)` execute.
- ✅ Button đổi text "Sao chép" → "Đã sao" (icon Check) trong 2s.
- ✅ Sau 2s revert.

### TC-5 · Close reveal → key permanently hidden

**Steps**
1. Click "Tôi đã sao chép" hoặc backdrop.

**Expected**
- ✅ Modal close.
- ✅ Row mới appears trong table với label "test-key-01" và mask key_id.
- ✅ Click "+ Tạo khoá mới" lần nữa → state mới, KHÔNG show key cũ.
- ✅ (BE invariant K-13: raw_key chỉ trả 1 lần trong response của POST; list/get chỉ trả hash + key_id.)

### TC-6 · Revoke key

**Steps**
1. Click icon trash ở row active.

**Expected**
- ✅ Modal nhỏ confirm: "Thu hồi khoá API" + text "Thu hồi <label>? Mọi tích hợp đang dùng khoá này sẽ ngừng hoạt động ngay lập tức.".
- ✅ Buttons: Hủy / Thu hồi (red).
- ✅ Click "Thu hồi" → `POST /workspaces/{id}/keys/{keyId}/revoke` 200.
- ✅ Modal close.
- ✅ Row update: status badge đổi "Đã thu hồi" (default grey), thu hồi lúc fill thời gian, trash icon biến mất (column "Hành động" hiện "—").

### TC-7 · Empty state

**Steps**
1. Workspace chưa có key nào.

**Expected**
- ✅ Header line: "Khoá API dùng để kích hoạt workspace và xác thực tích hợp.".
- ✅ Table body 1 row: "Chưa có khoá API nào trong workspace này.".

### TC-8 · Loading + error

**Steps**
1. Hard refresh / Stop auth-service.

**Expected**
- ✅ Loading: 3 skeleton rows `h-14 animate-pulse`.
- ✅ Error: ErrorBanner "Không thể tải danh sách khoá API." trên đầu.

### TC-9 · Nhãn empty OK

**Steps**
1. Submit tạo khoá không fill nhãn.

**Expected**
- ✅ POST body KHÔNG có field `label` (`createLabel.trim() || undefined`).
- ✅ BE accept (label optional).
- ✅ Row mới hiện "Không có nhãn".

### TC-10 · Modal escape behaviors

**Steps**
1. Open create modal → press Escape.

**Expected**
- ⚠️ Modal hiện không handle Escape key (TODO).
- ✅ Click backdrop close modal.
- ✅ Click X icon close modal.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Modal chưa handle Escape key. | Click backdrop hoặc X. |

## Related screens

- **UAT-PL-006** parent tab.
- **UAT-PL-007** /members, **UAT-PL-009** /billing.
