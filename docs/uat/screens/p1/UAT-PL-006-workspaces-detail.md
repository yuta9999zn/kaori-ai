# UAT-PL-006 · Workspace Detail (Tổng quan)

| | |
|---|---|
| **Mã test** | UAT-PL-006 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/[id]` |
| **Source FE** | `frontend/app/platform/workspaces/[id]/page.tsx` + `[id]/layout.tsx` |
| **Endpoint** | `GET /api/v1/platform/workspaces/{id}` |
| **Auth required** | Có (mọi platform role) |
| **Phase** | Phase 1 ✅ (F-008) |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

Trang tổng quan workspace: header card (name + status badge + UUID), tab bar 6 tab, body có 4-fact grid + 2-column quick actions.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Workspace tồn tại với valid UUID. |
| P3 | Vào từ UAT-PL-004 (click row) hoặc direct nav `/platform/workspaces/<uuid>`. |

## Test cases

### TC-1 · Render header (layout)

**Steps**
1. Navigate `/platform/workspaces/<uuid>`.

**Expected**
- ✅ HTTP 200.
- ✅ Top section (từ `[id]/layout.tsx`): back link "← Tất cả workspaces" + workspace card 
  - Gold halo Building2 icon (w-12 h-12)
  - Name (serif text-2xl)
  - Status Badge (operational / warning / degraded)
  - UUID monospace dưới (text-xs muted)
- ✅ Tab bar dưới header: Tổng quan (gold underline active) · Thành viên · Khoá API · Thanh toán · Nhật ký kiểm toán · Chỉnh sửa.
- ✅ Body wrap padding `px-6 lg:px-8 py-6`.

### TC-2 · Render body — facts grid

**Steps**
1. Quan sát phần body.

**Expected**
- ✅ Section card đầu tiên: 4-fact grid (2 cols mobile, 4 cols md+):
  - **Mã gói** (icon Tag) — plan_code text
  - **Ngành** (icon Briefcase) — industry hoặc "—"
  - **Tạo lúc** (icon Calendar) — fmtDateTime(created_at)
  - **Cập nhật** (icon RefreshCw) — fmtDateTime(updated_at)
- ✅ Mỗi fact: label `text-[10px] uppercase tracking-wider` + value `font-medium text-sm`.

### TC-3 · Render body — quick actions

**Steps**
1. Cuộn xuống.

**Expected**
- ✅ 2-column grid (1 col mobile, 1:2 = 2/3 + 1/3 lg):
  - **Hoạt động gần đây** (2/3) — placeholder text + button link "Xem nhật ký kiểm toán".
  - **Tác vụ nhanh** (1/3) — 4 link cards:
    - Quản lý thành viên (icon Users) → /members
    - Xem thanh toán (icon Receipt) → /billing
    - Nhật ký kiểm toán (icon FileClock) → /audit
    - Chỉnh sửa workspace (icon Pencil) → /edit

### TC-4 · Quick action hover

**Steps**
1. Hover vào link "Quản lý thành viên".

**Expected**
- ✅ Background đổi `bg-[var(--bg-app)]`.
- ✅ Border đổi `border-[var(--primary-gold)]/40` (gold accent).

### TC-5 · Tab click

**Steps**
1. Click tab "Thành viên".

**Expected**
- ✅ URL navigate `/platform/workspaces/<uuid>/members` (UAT-PL-007).
- ✅ Tab "Tổng quan" mất gold underline, tab "Thành viên" có gold underline.
- ✅ Body content đổi (Members table thay overview).
- ✅ Header card NOT re-render (`layout.tsx` shared).

### TC-6 · Back link

**Steps**
1. Click "← Tất cả workspaces".

**Expected**
- ✅ Navigate `/platform/workspaces` (list).

### TC-7 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ Header: 2 skeleton bars `h-7 w-64` + `h-4 w-40` animate-pulse.
- ✅ Body: 2 skeleton sections `h-32` + `h-40` animate-pulse.

### TC-8 · ID không tồn tại

**Steps**
1. Manual nav `/platform/workspaces/00000000-0000-0000-0000-000000000999`.

**Expected**
- ✅ `GET /workspaces/{id}` 404 RFC 7807.
- ✅ Header card cũ vẫn render nhưng h1 = "Workspace không tồn tại" + UUID muted.
- ✅ Body ErrorBanner: "Không thể tải workspace <id>. Endpoint GET /api/v1/platform/workspaces/{id} có thể chưa được triển khai.".

### TC-9 · Direct nav (hydration)

**Steps**
1. Logout.
2. Manual nav `/platform/workspaces/<uuid>`.

**Expected**
- ✅ Wait hydration ~50ms.
- ✅ Layout `/platform/layout.tsx` auth gate redirect `/platform/login`.
- ❌ KHÔNG có flash empty page giữa hydration → redirect (fix hydration gate `0a3ee1e`).

### TC-10 · Cream/gold tokens

**Steps**
1. DevTools elements `:root`.

**Expected**
- ✅ Mọi token `--primary-gold`, `--bg-app`, `--text-primary`, ... defined.
- ✅ Workspace card border `--border-color`, halo `--primary-gold/15`.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | "Hoạt động gần đây" hiện placeholder text, audit log BE chưa wire fully. | Xem `/audit` tab cho audit thực. |

## Related screens

- **UAT-PL-004** `/platform/workspaces` — return path.
- **UAT-PL-007..011** sub-tabs Members/Keys/Billing/Audit/Edit.
