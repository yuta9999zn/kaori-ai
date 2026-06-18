# UAT-PL-011 · Workspace Edit + Soft Delete

| | |
|---|---|
| **Mã test** | UAT-PL-011 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/[id]/edit` |
| **Source FE** | `frontend/app/platform/workspaces/[id]/edit/page.tsx` |
| **Endpoints** | `GET /workspaces/{id}` · `PATCH /workspaces/{id}` · `DELETE /workspaces/{id}` |
| **Auth required** | Có (SUPER_ADMIN gate ở BE) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

Edit form workspace (Tên + Mã gói + Trạng thái) + vùng nguy hiểm để soft-delete (chuyển status → inactive).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN. |
| P2 | Workspace tồn tại. |

## Test cases

### TC-1 · Render form pre-populated

**Steps**
1. Vào `/platform/workspaces/<uuid>/edit`.

**Expected**
- ✅ Section "Thông tin chung":
  - Label "Tên workspace" + Input pre-filled (minLength=2, maxLength=200)
  - Label "Mã gói" + Input pre-filled, auto-uppercase, pattern `^[A-Za-z0-9_-]{2,20}$`
  - Helper text: "2–20 ký tự chữ/số, gạch dưới hoặc gạch ngang. Ví dụ: PILOT, ENT_BASIC, ENT_MID, ENT_MAX."
  - Label "Trạng thái" + native `<select>` pre-selected current status
    - Options: Đang hoạt động / Ngừng hoạt động / Tạm ngưng
- ✅ Footer buttons: Hủy / "💾 Lưu thay đổi".
- ✅ Section "Vùng nguy hiểm" (border đỏ `--state-error/30`):
  - Heading "⚠️ Vùng nguy hiểm" (icon AlertTriangle)
  - Text explanation về soft-delete
  - Button "🗑 Xóa mềm workspace" (variant destructive).

### TC-2 · Edit + lưu

**Steps**
1. Đổi Tên thành "Test ABC v2".
2. Đổi Mã gói "ENT_MID".
3. Chọn Trạng thái "Đang hoạt động".
4. Click "💾 Lưu thay đổi".

**Expected**
- ✅ Button spinner.
- ✅ `PATCH /workspaces/{id}` 200 với body `{name, plan_code, status}`.
- ✅ React-query invalidate `['platform-workspace', id]` + `['platform-workspaces']`.
- ✅ URL navigate `/platform/workspaces/{id}` (overview, UAT-PL-006) với data mới.

### TC-3 · Validate mã gói pattern

**Steps**
1. Đổi mã gói thành "ab" (2 chars OK) → submit → pass.
2. Đổi mã gói thành "x" (1 char) → submit → native pattern validation block (regex `{2,20}`).
3. Đổi mã gói thành "abc@123" → submit → block (chứa ký tự không cho phép).

**Expected**
- ✅ Native HTML5 pattern validator activate khi submit.
- ✅ Browser bubble error tự popup.

### TC-4 · Auto-uppercase

**Steps**
1. Type "pilot" vào field Mã gói.

**Expected**
- ✅ Field hiện "PILOT" (uppercase ngay khi gõ qua `onChange` handler).

### TC-5 · Cancel

**Steps**
1. Click "Hủy".

**Expected**
- ✅ Navigate `/platform/workspaces/{id}` (overview), không PATCH gì.

### TC-6 · BE error

**Steps**
1. PATCH với mã gói trùng hoặc validation BE fail.

**Expected**
- ✅ `PATCH` 400 RFC 7807.
- ✅ ErrorBanner xuất hiện trên đầu form với detail message.

### TC-7 · Open soft-delete confirm

**Steps**
1. Click "🗑 Xóa mềm workspace".

**Expected**
- ✅ Modal nhỏ confirm:
  - Header serif "Xác nhận xóa mềm"
  - Text: `Workspace "${name}" sẽ chuyển sang trạng thái Ngừng hoạt động. Người dùng sẽ không truy cập được cho đến khi kích hoạt lại.`
  - Buttons: Hủy / "Xóa mềm" (red destructive).

### TC-8 · Confirm soft-delete

**Steps**
1. Trong modal, click "Xóa mềm".

**Expected**
- ✅ Button spinner.
- ✅ `DELETE /workspaces/{id}` 200 với body response `{workspace_id, status: "inactive"}`.
- ✅ React-query invalidate `['platform-workspaces']`.
- ✅ Modal close.
- ✅ URL navigate `/platform/workspaces` (list).
- ✅ Trong list workspace bị xóa mềm hiển thị status badge "Ngừng hoạt động".

### TC-9 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ Skeleton lớn `h-96 animate-pulse` thay cho form + danger section.

### TC-10 · BE 404 (workspace không tồn tại)

**Steps**
1. Nav direct `/platform/workspaces/00000000-0000-0000-0000-000000000999/edit`.

**Expected**
- ✅ ErrorBanner: "Không thể tải workspace để chỉnh sửa.".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-006** /workspaces/{id} — return path TC-2 / TC-5.
- **UAT-PL-004** /workspaces — return path TC-8.
