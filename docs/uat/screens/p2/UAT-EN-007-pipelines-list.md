# UAT-EN-007 · Pipelines List

| | |
|---|---|
| **Mã test** | UAT-EN-007 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines` |
| **Source FE** | `frontend/components/p2/templates/18-data-pipeline-manager.tsx` |
| **Endpoint** | `GET /api/v1/pipelines?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Liệt kê pipeline runs với status, duration, rows processed. Cursor pagination. Action: create new + drill-down detail.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Workspace có ≥ 1 pipeline run. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Pipelines" + button "+ Tạo pipeline mới" → `/p2/pipelines/new`.
- ✅ Filter status (all / running / succeeded / failed).
- ✅ Table columns: Pipeline ID · Tên dataset · Status · Stage hiện tại · Duration · Tạo lúc · Actions.
- ✅ Status Badge: `running` info, `succeeded` operational, `failed` error, `analysis_complete` operational.

### TC-2 · Click row → step detail

**Expected**
- ✅ Navigate `/p2/pipelines/{id}/step-2-columns` (current stage).

### TC-3 · Click "Tạo pipeline mới"

**Expected**
- ✅ Navigate `/p2/pipelines/new` (UAT-EN-008).

### TC-4 · Filter + pagination

**Expected**
- ✅ Status filter → reset cursor + refetch.
- ✅ "Sau →" load next page.

### TC-5 · Loading + empty + BE error

**Expected**
- ✅ Skeleton 5 rows / empty state / ErrorBanner.

### TC-6 · Cancel running pipeline

**Steps**
1. Click icon X ở row status running.

**Expected**
- ✅ Confirm modal → `POST /pipelines/{id}/cancel` → status đổi `cancelled`.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-008** /p2/pipelines/new.
- **UAT-EN-010..013** step-by-step detail.
