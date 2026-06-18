# UAT-EN-060 · Department Workflows

| | |
|---|---|
| **Mã test** | UAT-EN-060 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/departments/[deptId]/workflows` |
| **Source FE** | `frontend/components/p2/templates/fnew-department-workflows.tsx` |
| **Endpoint** | `GET /api/v1/departments/{deptId}/workflows` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Workflows assigned to 1 department (Sales / Marketing / Operations / ...). Cross-link với corporate hierarchy (mig 055-057).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Department tồn tại với workflows assigned. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Header: department name + parent (corporate group).
- ✅ Tab: Workflows · Members · KPIs.
- ✅ Workflow list filtered by deptId.

### TC-2 · Cross-workflow links

**Expected**
- ✅ View `v_workflow_cross_links_enriched` (mig 057) — workflow phụ thuộc workflow khác in tag.

### TC-3 · Turbopack 500

**Expected**
- ✅ Note: dynamic `[deptId]` — webpack.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. | webpack. |

## Related screens

- **UAT-EN-071** /p2/org-tree.
- **UAT-EN-054** workflows list.
