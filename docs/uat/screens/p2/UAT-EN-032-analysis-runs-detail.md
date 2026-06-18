# UAT-EN-032 · Analysis Run Detail

| | |
|---|---|
| **Mã test** | UAT-EN-032 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/analysis/runs/[id]` |
| **Source FE** | `frontend/components/p2/templates/fnew-analysis-run-detail.tsx` |
| **Endpoint** | `GET /api/v1/analysis/runs/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Detail 1 analysis run đã chạy: input scope + method + results + insights generated.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Run ID hợp lệ. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Header: run_id + status + duration + cost.
- ✅ Sections: Input (scope summary) / Method + params / Results table or chart / Insights generated.

### TC-2 · Re-run

**Expected**
- ✅ Button "Re-run" → `POST /analysis/runs/{id}/rerun` → new run_id.

### TC-3 · Export

**Expected**
- ✅ Export PDF / CSV button.

### TC-4 · Turbopack 500

**Expected**
- ✅ Note: `[id]` dynamic route — dùng webpack.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. | webpack. |

## Related screens

- **UAT-EN-027** hub.
