# UAT-EN-031 · Analysis Scope

| | |
|---|---|
| **Mã test** | UAT-EN-031 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/analysis/scope` |
| **Source FE** | `frontend/components/p2/templates/39-analysis-scope.tsx` |
| **Endpoint** | `GET/POST /api/v1/analysis/scope` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Định nghĩa phạm vi (scope) cho analysis: time window + filter conditions + grouping. Lưu scope để reuse trong các framework.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render scope builder

**Expected**
- ✅ Form: Date range / Filters (col + op + value) / Group by / Save name.

### TC-2 · Save scope

**Expected**
- ✅ `POST /analysis/scope` 200 → scope_id.

### TC-3 · Load saved scope

**Expected**
- ✅ List dropdown saved scopes → click load → form populate.

### TC-4 · Delete scope

**Expected**
- ✅ Trash icon → confirm → DELETE.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-027** hub.
