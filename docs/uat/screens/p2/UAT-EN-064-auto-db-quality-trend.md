# UAT-EN-064 · Auto DB Quality Trend

| | |
|---|---|
| **Mã test** | UAT-EN-064 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/auto-db/quality-trend` |
| **Source FE** | `frontend/components/p2/templates/64-auto-db-quality-trend.tsx` |
| **Endpoint** | `GET /api/v1/auto-db/quality-trend?dataset_id=&period=` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Trend 7-dim quality scorecard over time (mig 065): line chart mỗi dimension theo ngày/tuần/tháng.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Dataset có ≥ 7 ngày quality history. |

## Test cases

### TC-1 · Render chart

**Expected**
- ✅ Select dataset + period (7d/30d/90d).
- ✅ Line chart 7 lines (Completeness / Accuracy / Consistency / Timeliness / Validity / Uniqueness / Integrity).
- ✅ Y-axis 0-100 score.

### TC-2 · Toggle dimension

**Expected**
- ✅ Legend click → hide/show line.

### TC-3 · Drilldown date

**Expected**
- ✅ Click point → drawer hiện rule violations cho ngày đó.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-005** /p2/data/silver — current quality.
