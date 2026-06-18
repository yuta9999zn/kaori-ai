# UAT-PL-005 · Tạo Workspace mới (3-step wizard)

| | |
|---|---|
| **Mã test** | UAT-PL-005 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/new` |
| **Source FE** | `frontend/app/platform/workspaces/new/page.tsx` |
| **Endpoint** | `POST /api/v1/platform/workspaces` |
| **Auth required** | Có (SUPER_ADMIN only) |
| **Phase** | Phase 1 ✅ (F-008) |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

3-step wizard cấp phát workspace mới: Thông tin chung → Gói & ngành → Xác nhận. Submit `POST` rồi redirect detail của workspace vừa tạo.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN. |
| P2 | Vào từ UAT-PL-004 TC button "+ Tạo workspace mới", hoặc direct nav `/platform/workspaces/new`. |

## Test cases

### TC-1 · Render bước 1

**Steps**
1. Navigate `/platform/workspaces/new`.

**Expected**
- ✅ HTTP 200.
- ✅ Back link "← Tất cả workspaces" trên đầu.
- ✅ PageHeader "Tạo workspace mới" + description.
- ✅ Stepper 3 pills: "1. Thông tin chung" (active gold), "2. Gói & ngành" (neutral grey), "3. Xác nhận" (neutral grey).
- ✅ Connector lines giữa các pill (grey vì chưa done).
- ✅ Form body: heading "Thông tin chung" + Label "Tên workspace" + Input (autofocus, placeholder "VD: Acme Production", minLength=2, maxLength=200).
- ✅ Helper text dưới input: "2–200 ký tự. Sẽ hiển thị cho thành viên trong workspace.".
- ✅ Footer buttons: "← Quay lại" (disabled vì step 1), "Tiếp tục →".

### TC-2 · Validate bước 1 (tên < 2)

**Steps**
1. Để Tên empty hoặc gõ 1 ký tự.
2. Click "Tiếp tục →".

**Expected**
- ✅ Bước không advance.
- ✅ Red error banner: "Tên workspace cần ≥ 2 ký tự.".
- ✅ Stepper vẫn ở pill 1.

### TC-3 · Pass bước 1 → bước 2

**Steps**
1. Fill "Test Workspace ABC".
2. Click "Tiếp tục →".

**Expected**
- ✅ Stepper: pill 1 đổi thành **done** state (green tick + bg `--state-success/15`), connector line 1→2 green.
- ✅ Pill 2 active gold.
- ✅ Form body: heading "Gói & ngành".
- ✅ Select "Mã gói" với 4 options:
  - PILOT — 1.000.000 ₫/tháng · 500 KH duy nhất
  - ENT BASIC — 2.000.000 ₫/tháng · 1.000 KH
  - ENT MID — 5.000.000 ₫/tháng · 4.000 KH
  - ENT MAX — 8.000.000 ₫/tháng · 10.000 KH
- ✅ Default selected: PILOT.
- ✅ Helper text: "Tính cước theo COUNT(DISTINCT customer_external_id) mỗi tháng — K-11.".
- ✅ Input "Ngành (tùy chọn)" placeholder "VD: Bán lẻ, Tài chính, Sản xuất", maxLength=100.
- ✅ Buttons: "← Quay lại" (enabled), "Tiếp tục →".

### TC-4 · Quay lại từ bước 2

**Steps**
1. Đang ở bước 2, click "← Quay lại".

**Expected**
- ✅ Stepper pill 1 trở lại active gold, pill 2 neutral.
- ✅ Form values giữ nguyên (Tên còn "Test Workspace ABC").

### TC-5 · Pass bước 2 → bước 3 (Xác nhận)

**Steps**
1. Chọn plan "ENT MID".
2. Fill ngành "Bán lẻ".
3. Click "Tiếp tục →".

**Expected**
- ✅ Pill 1 + 2 done (green tick), pill 3 active.
- ✅ Form body: heading "Xác nhận".
- ✅ Confirm card 3 rows (label-value):
  - Tên: "Test Workspace ABC"
  - Gói: Badge `current` "ENT_MID"
  - Ngành: "Bán lẻ"
- ✅ Note text: "Bạn có thể mời thành viên và cấp khoá API ngay sau khi tạo xong.".
- ✅ Submit button "✓ Tạo workspace" (gold).

### TC-6 · Submit thành công

**Steps**
1. Ở bước 3, click "✓ Tạo workspace".

**Expected**
- ✅ Button hiện spinner Loader2 + text "Tạo workspace" (loading state).
- ✅ `POST /api/v1/platform/workspaces` 200 với body `{name, plan_code, industry}`.
- ✅ Response: `{data: {workspace_id: <uuid>, name, plan_code, industry, status: "active", ...}}`.
- ✅ React-query invalidate `['platform-workspaces']`.
- ✅ URL navigate `/platform/workspaces/<new uuid>` (UAT-PL-006).
- ✅ Detail page render với workspace mới.

### TC-7 · Submit thất bại (BE 400/409)

**Steps**
1. Bypass FE validation (devtools console): submit name = "x" (1 char).

**Expected**
- ✅ `POST /workspaces` 400 RFC 7807.
- ✅ ErrorBanner appears với detail message.
- ✅ User vẫn ở bước 3, có thể "← Quay lại" sửa.

### TC-8 · Empty ngành OK

**Steps**
1. Bước 2 không fill ngành.
2. Tiếp tục → submit.

**Expected**
- ✅ POST body KHÔNG có field `industry` (vì `industry.trim()` = "" → bỏ).
- ✅ BE accept (industry optional).

### TC-9 · Cancel mid-wizard

**Steps**
1. Ở bất kỳ bước nào, click back link "← Tất cả workspaces".

**Expected**
- ✅ Navigate `/platform/workspaces` (không POST gì cả).

### TC-10 · Plan dropdown navigation

**Steps**
1. Bước 2, focus select plan.
2. Press ↓ ↓ → chọn ENT_MAX.

**Expected**
- ✅ Native select behavior, ENT_MAX hiển thị.

### TC-11 · ADMIN/SUPPORT không vào được

**Steps**
1. Login as ADMIN (không có canCreate).
2. Direct nav `/platform/workspaces/new`.

**Expected**
- ✅ Page render (route không gate role).
- ⚠️ Submit sẽ 403 từ BE nếu ADMIN không có quyền tạo workspace.
- (Pattern: BE là source of truth cho action gate; FE chỉ ẩn entry buttons.)

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-004** `/platform/workspaces` — return path.
- **UAT-PL-006** `/platform/workspaces/{id}` — success destination.
