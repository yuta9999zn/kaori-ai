# UAT-EN-067 · Authz ABAC Policy Builder

| | |
|---|---|
| **Mã test** | UAT-EN-067 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/authz/abac-builder` |
| **Source FE** | `frontend/components/p2/templates/67-authz-abac-builder.tsx` |
| **Endpoint** | `POST /api/v1/authz/policies` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 2 🔵 (hybrid RBAC + ABAC) |

---

## Mục tiêu test

ABAC policy builder: visual conditional editor — user.department == resource.department AND resource.classification != "secret".

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render builder

**Expected**
- ✅ 3-panel: Subject attributes / Resource attributes / Conditions.
- ✅ Drag condition blocks (AND/OR/NOT).

### TC-2 · Define policy

**Expected**
- ✅ Build expression visual → preview JSON policy.

### TC-3 · Save

**Expected**
- ✅ POST → policy_id.

### TC-4 · Test simulate

**Expected**
- ✅ Link sang /p2/authz/simulate (UAT-EN-068).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | ABAC engine Phase 2 — visual editor complex. | Phase 1 JSON edit. |

## Related screens

- **UAT-EN-068** simulate.
- **UAT-EN-069** audits.
