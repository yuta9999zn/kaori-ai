# UAT-EN-066 · Authz Custom Roles

| | |
|---|---|
| **Mã test** | UAT-EN-066 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/authz/custom-role` |
| **Source FE** | `frontend/components/p2/templates/66-authz-custom-role.tsx` |
| **Endpoint** | `GET/POST/DELETE /api/v1/authz/custom-roles` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Tạo custom roles ngoài 4 built-in. Pick permissions từ catalog → save → assign user.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render list

**Expected**
- ✅ Table custom roles + permission count + user count + edit/delete.

### TC-2 · Create role

**Expected**
- ✅ Modal: name + description + multi-select permissions.
- ✅ Submit → POST → row appears.

### TC-3 · Edit / delete

**Expected**
- ✅ Standard CRUD.

### TC-4 · Block delete if assigned

**Expected**
- ✅ Delete role có users assigned → confirm warning + force option.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-065** RBAC.
