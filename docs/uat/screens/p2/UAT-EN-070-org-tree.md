# UAT-EN-070 · Org Tree (Corporate Hierarchy)

| | |
|---|---|
| **Mã test** | UAT-EN-070 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/org-tree` |
| **Source FE** | `frontend/components/p2/templates/fnew-corporate-tree.tsx` |
| **Endpoint** | `GET /api/v1/corporate-tree` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (mig 055-056 — Vingroup demo) |

---

## Mục tiêu test

Hiển thị corporate hierarchy 3 cấp: Corporate Group → Business Division → Enterprise. Demo: Vingroup (1 group × 8 divisions × 16 subsidiaries).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace bound to corporate group (vd Vingroup demo data). |

## Test cases

### TC-1 · Render tree

**Expected**
- ✅ PageHeader "Cơ cấu tổ chức".
- ✅ Tree view 3 levels: Group (root) → Divisions → Enterprises.
- ✅ Mỗi node: icon + name + count children + expand/collapse.

### TC-2 · Click enterprise → workspace

**Expected**
- ✅ Click enterprise node → drawer hiện info workspace bound.

### TC-3 · Cross-link metadata

**Expected**
- ✅ Workflows cross-link tag hiện trên node có v_workflow_cross_links_enriched flag.

### TC-4 · Filter division

**Expected**
- ✅ Dropdown filter chỉ division X.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Drag-drop org tree builder defer Tuần 9. | Phase 1 read-only. |

## Related screens

- **UAT-EN-060** departments-workflows.
