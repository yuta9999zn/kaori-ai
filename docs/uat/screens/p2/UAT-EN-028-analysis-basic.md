# UAT-EN-028 · Analysis Basic

| | |
|---|---|
| **Mã test** | UAT-EN-028 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/analysis/basic` |
| **Source FE** | `frontend/components/p2/templates/36-analyst-basic.tsx` |
| **Endpoint** | `POST /api/v1/analysis/basic` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Basic analysis: descriptive statistics (mean / median / mode / std / min / max). Chọn dataset + column → submit.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có Silver/Gold dataset. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ Dataset select + column multi-select + Submit.

### TC-2 · Submit

**Expected**
- ✅ Results table: column · count · mean · median · std · min · max.

### TC-3 · Empty / loading / error

**Expected**
- ✅ Standard states.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-027** hub.
