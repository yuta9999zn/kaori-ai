# UAT-EN-065 · Authz RBAC

| | |
|---|---|
| **Mã test** | UAT-EN-065 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/authz/rbac` |
| **Source FE** | `frontend/components/p2/templates/65-authz-rbac.tsx` |
| **Endpoint** | `GET/PATCH /api/v1/authz/rbac` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Bảng RBAC role × permission matrix. MANAGER assign role cho user, view permissions per role.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render matrix

**Expected**
- ✅ PageHeader "RBAC".
- ✅ Table: rows = roles (MANAGER/OPERATOR/ANALYST/VIEWER), cols = permissions (data:read, data:write, pipeline:run, ...).
- ✅ Cells: ✓ (allowed) / ✗ (denied) — read-only cho built-in roles.

### TC-2 · Assign user

**Expected**
- ✅ Tab "Users" → list users + role select per user.

### TC-3 · Permission detail

**Expected**
- ✅ Click permission → modal description + scope.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-066** custom-role.
- **UAT-EN-067** abac-builder.
