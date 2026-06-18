# UAT-PL-010 · Workspace Audit Log

| | |
|---|---|
| **Mã test** | UAT-PL-010 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform/workspaces/[id]/audit` |
| **Source FE** | `frontend/app/platform/workspaces/[id]/audit/page.tsx` |
| **Endpoint** | `GET /workspaces/{id}/audit?cursor=&limit=` |
| **Auth required** | Có (platform role) |
| **Phase** | Phase 1 ✅ (K-6 audit log immutability) |
| **Re-skin commit** | `0c4c1c4` (2026-05-18) |

---

## Mục tiêu test

Nhật ký kiểm toán bất biến (K-6) của workspace. Mỗi quyết định/hành động quản trị đều được ghi: thời gian + event_type + actor + resource + detail + IP.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login as platform role. |
| P2 | Workspace có audit events (CRUD trên workspace hoặc admin actions). |

## Test cases

### TC-1 · Render khi có events

**Steps**
1. Vào `/platform/workspaces/<uuid>/audit`.

**Expected**
- ✅ Description paragraph: "Nhật ký kiểm toán bất biến (K-6). Mỗi quyết định tự động và hành động quản trị đều được ghi lại với confidence và alternatives.".
- ✅ Table columns: Thời gian · Sự kiện · Tác nhân · Tài nguyên · Chi tiết · IP.
- ✅ Mỗi row:
  - Thời gian: `fmtDateTime(created_at)` tabular-nums, whitespace-nowrap
  - Sự kiện: `<code>` gold tint `bg-[var(--primary-gold)]/12 text-[var(--primary-gold-dark)]`
  - Tác nhân: actor_email + actor_role (text-xs muted dưới), HOẶC Badge "Hệ thống" nếu actor_email null
  - Tài nguyên: text muted hoặc "—"
  - Chi tiết: text primary
  - IP: text xs monospace

### TC-2 · Pagination cursor

**Steps**
1. Quan sát bottom bar khi có nhiều events.

**Expected**
- ✅ "Trang N" hiện ở trái.
- ✅ "← Trước" disabled nếu page 1.
- ✅ "Sau →" enabled nếu `meta.cursor` non-null.
- ✅ Click "Sau →" → fetch next page với cursor.
- ✅ Click "← Trước" → pop cursors stack.

### TC-3 · Empty state

**Steps**
1. Workspace chưa có audit event.

**Expected**
- ✅ Table body 1 row colspan=6: "Chưa có sự kiện nào được ghi lại.".

### TC-4 · BE error (chưa wired)

**Steps**
1. BE endpoint `/audit` không exist hoặc 500.

**Expected**
- ✅ ErrorBanner: "Backend audit log cho workspace <id> chưa sẵn sàng.".

### TC-5 · System event vs user event

**Steps**
1. Quan sát rows.

**Expected**
- ✅ Event có `actor_email` → hiện email + role (vd "admin@kaori.platform" / "SUPER_ADMIN").
- ✅ Event không có actor (system-generated, e.g. cron) → Badge default "Hệ thống".

### TC-6 · Event type styling

**Steps**
1. Quan sát column Sự kiện.

**Expected**
- ✅ Event type render dạng `<code>` font-mono, padding-xs, gold tint background.
- ✅ Ví dụ: `admin.password_reset_requested`, `workspace.created`, `key.revoked`.

### TC-7 · Loading state

**Steps**
1. Hard refresh.

**Expected**
- ✅ 5 skeleton rows `h-12 animate-pulse`.

### TC-8 · Long detail truncation

**Steps**
1. Event có `detail` chuỗi dài.

**Expected**
- ✅ Text wrap trong cell, không vỡ layout.
- ⚠️ Hiện không truncate `text-ellipsis` — TODO improvement.

### TC-9 · IP column null

**Steps**
1. Event không có `ip_address` (system event).

**Expected**
- ✅ Cell IP hiện "—".

### TC-10 · Filter (chưa có)

**Steps**
1. Quan sát filter row.

**Expected**
- ⚠️ Trang hiện KHÔNG có filter (search/date range/event type) — TODO Phase 2.
- ✅ Nếu cần filter, dùng search trên column Sự kiện manual.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Không có search/filter. | TODO Phase 2. |
| K-002 | Long detail không truncate. | Acceptable Phase 1. |

## Related screens

- **UAT-PL-006** parent tab.
- **UAT-PL-014** `/platform/admins/{id}` — actor có thể link sang admin detail (future). 
