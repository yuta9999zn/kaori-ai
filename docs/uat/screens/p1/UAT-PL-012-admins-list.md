# UAT-PL-012 · Platform Admins List

| | |
|---|---|
| **Mã test** | UAT-PL-012 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/admins` |
| **Source FE** | `frontend/app/platform/admins/page.tsx` |
| **Endpoint** | `GET /api/v1/platform/admins` |
| **Auth required** | Có (SUPER_ADMIN — entry ẩn cho roles khác qua nav.ts) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `9eebe01` (2026-05-18) |

---

## Mục tiêu test

Liệt kê toàn bộ Kaori staff admins. Mỗi row: icon halo theo role, name, role + active + MFA badges, email.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as SUPER_ADMIN (nav entry chỉ visible cho role này). |
| P2 | ≥ 1 admin trong DB (`superadmin@kaori.local` từ seed). |

## Test cases

### TC-1 · Render khi có data

**Steps**
1. Click "Quản trị viên → Danh sách" trong sidebar.

**Expected**
- ✅ HTTP 200.
- ✅ PageHeader: "Quản trị viên Platform" + description "Tài khoản có quyền quản trị toàn hệ thống. Super Admin bắt buộc MFA."
- ✅ Action button "+ Mời quản trị viên".
- ✅ Stack rows (vertical, gap-2), mỗi row là Link card có hover effect (shadow + gold border).
- ✅ Mỗi row layout:
  - **Icon halo** (p-2.5, rounded-md-custom) màu theo role:
    - SUPER_ADMIN: red `bg-[var(--state-error)]/15 text-[#9B5050]` icon ShieldCheck
    - ADMIN: gold `bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]` icon UserCog
    - SUPPORT: blue `bg-[var(--state-info)]/15 text-[#52647D]` icon Headphones
  - **Name** font-medium (hoặc email fallback) + role Badge + (optional) "Vô hiệu" Badge + (optional) "MFA" Badge
  - Email muted text-xs dưới
- ✅ Cuối row: ngày tạo tabular-nums (hidden sm) + icon ChevronRight.

### TC-2 · Click row → detail

**Steps**
1. Click row admin.

**Expected**
- ✅ URL navigate `/platform/admins/<id>` (UAT-PL-014).

### TC-3 · Invite link

**Steps**
1. Click "+ Mời quản trị viên".

**Expected**
- ✅ URL navigate `/platform/admins/invite` (UAT-PL-013).

### TC-4 · MFA badge

**Steps**
1. Quan sát admin có `mfa_enabled = true`.

**Expected**
- ✅ Hiện badge `operational` "MFA" (green).

### TC-5 · Inactive badge

**Steps**
1. Quan sát admin có `is_active = false`.

**Expected**
- ✅ Hiện badge default "Vô hiệu" (grey).

### TC-6 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 3 skeleton rows `h-16 animate-pulse`.

### TC-7 · Empty state

**Steps**
1. DB không có admin nào (test edge — không reproduce được vì cần ≥ 1 admin để login).

**Expected**
- ✅ Card placeholder: "Chưa có quản trị viên nào.".

### TC-8 · BE error

**Steps**
1. Stop auth-service.

**Expected**
- ✅ ErrorBanner trên đầu list.

### TC-9 · Role gate (ADMIN/SUPPORT direct nav)

**Steps**
1. Login as ADMIN.
2. Direct nav `/platform/admins`.

**Expected**
- ✅ Page render (route không gate).
- ⚠️ Sidebar entry không hiện cho non-SUPER_ADMIN (nav.ts `role: 'SUPER_ADMIN'` gate).
- ✅ List có thể vẫn render nếu BE cho phép, hoặc 403 ErrorBanner.

### TC-10 · 60s react-query stale

**Steps**
1. Tab page đứng yên 60-65s.

**Expected**
- ✅ Re-fetch tự động (staleTime = 60_000).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-013** `/platform/admins/invite` — TC-3.
- **UAT-PL-014** `/platform/admins/{id}` — TC-2.
