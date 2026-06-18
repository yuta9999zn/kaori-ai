# UAT-PL-003 · Dashboard (Tổng quan nền tảng)

| | |
|---|---|
| **Mã test** | UAT-PL-003 |
| **Portal** | P1 Platform Manager |
| **Route** | `/platform` |
| **Source FE** | `frontend/app/platform/page.tsx` |
| **Endpoint** | `GET /api/v1/platform/stats` |
| **Auth required** | Có (SUPER_ADMIN / ADMIN / SUPPORT) |
| **Phase** | Phase 1 ✅ |
| **Re-skin commit** | `065324a` (2026-05-18) |

---

## Mục tiêu test

Landing page sau khi login. Render counters (workspaces, users, runs) + hạ tầng health (Ollama, Kafka lag, P95 latency). React-query refetch mỗi 60s.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login thành công qua UAT-PL-001 TC-2 hoặc UAT-PL-002 TC-2. |
| P2 | `localStorage.kaori.access_token` set, `user.role ∈ {SUPER_ADMIN, ADMIN, SUPPORT}`. |
| P3 | BE `auth-service` + endpoint `/platform/stats` reachable. |
| P4 | (Optional) Ollama service đang chạy để Status "Online". |

## Test cases

### TC-1 · Render khi BE OK

**Steps**
1. Navigate `/platform` (hoặc click "Tổng quan → Bảng điều khiển" trong sidebar).

**Expected**
- ✅ HTTP 200.
- ✅ PageHeader: title serif "Tổng quan nền tảng" + description "Sức khoẻ hạ tầng + đếm tăng trưởng workspace, người dùng, pipeline runs.".
- ✅ Grid 4 KPI cards (2×2 mobile, 1×4 desktop):
  - **Tổng workspaces** (icon Building2, halo gold)
  - **Đang hoạt động** (icon Activity, halo **green** vì `accent="success"`)
  - **Tổng người dùng** (icon Users, halo gold)
  - **Runs hôm nay** (icon PlayCircle, halo gold)
- ✅ Mỗi KPI: label uppercase nhỏ, serif numeral lớn (`font-serif text-3xl tabular-nums`), số format `vi-VN` (dấu chấm separator).
- ✅ Section "Trạng thái hạ tầng" với 3 cells (`grid-cols-1 sm:grid-cols-3`):
  - Ollama (Qwen2.5)
  - Kafka consumer lag
  - P95 latency
- ✅ Mỗi infra cell: icon halo (green nếu OK, yellow warn, red error), label, detail text, Badge ở phải.
- ✅ Bottom line: "Tổng pipeline runs tất cả thời gian: NN.NNN" (số format vi-VN).

### TC-2 · React-query 60s refetch

**Steps**
1. Mở DevTools → Network tab → filter `stats`.
2. Đứng yên ở trang 60-65s.

**Expected**
- ✅ Request `GET /api/v1/platform/stats` re-poll mỗi 60s.
- ✅ Mỗi request 200 với data update (nếu BE có thay đổi).

### TC-3 · KPI card hover

**Steps**
1. Hover vào 1 KPI card.

**Expected**
- ✅ `shadow-soft-sm` upgrade lên `shadow-soft-md` (smooth transition).

### TC-4 · Infra status badges

**Steps**
1. Quan sát 3 infra cells.

**Expected**
- ✅ Ollama `online: true` → green halo + Badge `operational` "OK" + icon CheckCircle2.
- ✅ Ollama `online: false` → red halo + Badge `error` "Lỗi" + icon XCircle.
- ✅ Kafka lag ≤ 1000 → green Badge "OK".
- ✅ Kafka lag > 1000 → yellow halo + Badge `warning` "Chú ý" + icon AlertTriangle.
- ✅ P95 ≤ 2000ms → green.
- ✅ P95 > 2000ms → yellow "Chú ý".

### TC-5 · Loading state

**Steps**
1. Hard refresh `Ctrl+F5`.
2. Quan sát ngay khi page load (trước khi response về).

**Expected**
- ✅ Grid 4 KPI placeholder cards với `animate-pulse` (`h-28 rounded-md-custom border bg-card`).
- ✅ Section infra chưa render (chỉ render khi `stats` data về).

### TC-6 · BE 500 / network error

**Steps**
1. `docker compose stop auth-service`.
2. Refresh page.

**Expected**
- ✅ Sau timeout, KPI grid + infra section ẩn.
- ✅ ErrorBanner xuất hiện ở đầu page body với RFC 7807 title từ response (hoặc fallback "Có lỗi xảy ra").

(Restart: `docker compose start auth-service`.)

### TC-7 · Sidebar active state

**Steps**
1. Sidebar trái: group "Tổng quan" expanded by default (vì path match).

**Expected**
- ✅ Item "Bảng điều khiển" có gold accent: `bg-[var(--primary-gold)]/15 text-[var(--text-primary)] border-l-2 border-[var(--primary-gold)]`.
- ✅ Group icon LayoutDashboard color `--primary-gold-dark`.

### TC-8 · Header bar

**Steps**
1. Quan sát top header.

**Expected**
- ✅ Trái: "Kaori Platform" chip với ShieldCheck icon (gold).
- ✅ Search input giữa: placeholder "Tìm workspace, admin, key..." + kbd hint "⌘K" bên phải.
- ✅ Phải: Bell button (có red dot notification) + HelpCircle (sm hidden) + Avatar tròn gold initials.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-PL-004** `/platform/workspaces` — sidebar nav target.
- **UAT-PL-012** `/platform/admins` — sidebar nav target.
- **UAT-PL-016** `/platform/billing/overview` — sidebar nav target.
