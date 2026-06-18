# UAT-EN-038 · MoM/YoY Analysis Framework

| | |
|---|---|
| **Mã test** | UAT-EN-038 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks/mom-yoy-analysis` |
| **Source FE** | `frontend/components/p2/templates/44-frameworks-mom-yoy.tsx` |
| **Endpoint** | `POST /api/v1/frameworks/mom-yoy/generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

MoM (Month over Month) + YoY (Year over Year) comparison cho 1 metric: chart 2 lines + delta % + commentary.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Data có time series ≥ 13 tháng. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ Select metric (revenue / orders / customers) + Select dataset.
- ✅ Toggle MoM / YoY / cả 2.

### TC-2 · Generate

**Expected**
- ✅ Chart line 2 series + bar delta.
- ✅ Table summary: MoM avg % / YoY avg % / Best/worst month.
- ✅ AI commentary section.

### TC-3 · Highlight outlier

**Expected**
- ✅ Auto-flag tháng có spike/dip > 2σ.

### TC-4 · Export

**Expected**
- ✅ Export chart PNG + CSV.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-033** hub.
