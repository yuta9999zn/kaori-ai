# UAT-EN-005 · Data Silver Tier

| | |
|---|---|
| **Mã test** | UAT-EN-005 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/data/silver` |
| **Source FE** | `frontend/components/p2/templates/fnew3v1-silver.tsx` |
| **Endpoint** | `GET /api/v1/data/silver` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Liệt kê Silver datasets (cleaned + typed + PII-masked, ClickHouse Phase 1.5+). Mỗi dataset: schema, row count, quality scorecard 7-dim, partition info.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Pipeline ≥ 1 đã chạy qua stage 3 Silver. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Silver — Dữ liệu đã làm sạch".
- ✅ Table columns: Tên dataset · Domain · Rows · Quality score · Partitions · Updated.

### TC-2 · Quality score badge

**Expected**
- ✅ Score ≥ 80 → green badge.
- ✅ 60-79 → yellow.
- ✅ < 60 → red.

### TC-3 · Click dataset → drill-down

**Expected**
- ✅ Modal/drawer: 7-dim scorecard breakdown (Completeness, Accuracy, Consistency, etc.).
- ✅ Preview 10 rows.

### TC-4 · Empty + loading

**Expected**
- ✅ Skeleton + empty state.

### TC-5 · Domain filter

**Expected**
- ✅ Dropdown filter theo domain (customer / order / product / ...).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-006** /p2/data/gold.
