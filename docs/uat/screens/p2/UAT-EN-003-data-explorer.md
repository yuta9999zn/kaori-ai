# UAT-EN-003 · Data Explorer (Hub)

| | |
|---|---|
| **Mã test** | UAT-EN-003 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/data` |
| **Source FE** | `frontend/components/p2/templates/fnew3-data-explorer.tsx` |
| **Endpoint** | `GET /api/v1/data/explorer` (F-NEW3 BE PR #142) |
| **Auth required** | Có (mọi enterprise role) |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Hub điều hướng 3 tier Medallion: Bronze / Silver / Gold. List datasets từng tier + drill-down link sang sub-page.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Workspace có ≥ 1 dataset trong ít nhất 1 tier. |

## Test cases

### TC-1 · Render hub

**Steps**
1. Vào `/p2/data` (hoặc click "Dữ liệu → Khám phá" sidebar).

**Expected**
- ✅ PageHeader "Khám phá dữ liệu".
- ✅ 3 tier cards (Bronze / Silver / Gold):
  - Mỗi card: icon halo theo tier (Bronze: nâu, Silver: bạc, Gold: vàng), count datasets, "Vào tier →" link.
- ✅ Bảng datasets gần đây toàn workspace.

### TC-2 · Click Bronze tier

**Expected**
- ✅ Navigate `/p2/data/bronze` (UAT-EN-004).

### TC-3 · Click Silver / Gold tier

**Expected**
- ✅ Navigate `/p2/data/silver` / `/p2/data/gold`.

### TC-4 · Empty workspace

**Steps**
1. Workspace chưa upload data.

**Expected**
- ✅ Empty state mỗi tier card: "0 datasets".
- ✅ CTA "Tải dữ liệu lên" → `/p2/pipelines/new/upload`.

### TC-5 · Loading + error

**Expected**
- ✅ Skeleton 3 cards `h-32`.
- ✅ BE 500 → ErrorBanner.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-004** /p2/data/bronze.
- **UAT-EN-005** /p2/data/silver.
- **UAT-EN-006** /p2/data/gold.
