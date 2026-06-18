# UAT-EN-006 · Data Gold Tier

| | |
|---|---|
| **Mã test** | UAT-EN-006 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/data/gold` |
| **Source FE** | `frontend/components/p2/templates/fnew3v1-gold.tsx` |
| **Endpoint** | `GET /api/v1/data/gold` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Liệt kê Gold views (Postgres MV + Redis cache, feature-engineered cho dashboard). Mỗi view: source Silver datasets, formula, last refresh, cache hit rate.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Workspace có ≥ 1 Gold view (auto-create từ template registry). |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Gold — Bảng tổng hợp".
- ✅ Table columns: View name · Loại (KPI / Trend / Segment) · Sources · Last refresh · Cache.

### TC-2 · Refresh view manually

**Steps**
1. Click icon RefreshCw ở row view.

**Expected**
- ✅ `POST /data/gold/{view}/refresh` 200 → "Last refresh" cập nhật.

### TC-3 · View formula

**Expected**
- ✅ Click row → drawer hiện SQL/formula definition.

### TC-4 · Empty / loading

**Expected**
- ✅ Skeleton + empty state.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-003** /p2/data — hub.
