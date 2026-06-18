# UAT-EN-029 · Analysis Intermediate

| | |
|---|---|
| **Mã test** | UAT-EN-029 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/analysis/intermediate` |
| **Source FE** | `frontend/components/p2/templates/37-analysis-intermediate.tsx` |
| **Endpoint** | `POST /api/v1/analysis/intermediate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Intermediate analysis: correlation, regression linear, cohort retention.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có dataset với ≥ 2 numeric cols. |

## Test cases

### TC-1 · Correlation matrix

**Expected**
- ✅ Select 2+ cols → matrix heatmap render.

### TC-2 · Linear regression

**Expected**
- ✅ Select target + features → coefficients + R² + p-value.

### TC-3 · Cohort retention

**Expected**
- ✅ Cohort grid render (rows: signup month, cols: months later, cells: % retained).

### TC-4 · Loading / error

**Expected**
- ✅ Standard.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-030** advance.
