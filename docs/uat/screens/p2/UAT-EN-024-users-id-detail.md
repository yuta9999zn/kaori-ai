# UAT-EN-024 · User Detail (legacy mock)

| | |
|---|---|
| **Mã test** | UAT-EN-024 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/users/id-detail` (literal mock) |
| **Source FE** | `frontend/components/p2/templates/13-user-id-detail.tsx` |
| **Endpoint** | `GET /api/v1/enterprises/users/{id}` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ (F-015) |
| **Fix** | commit `399a629` — window.location → usePathname() |

---

## Mục tiêu test

Detail user trong workspace: edit profile + change role + reset password + activity log.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ User ID extracted từ pathname regex `/users/([^/?]+)/`.
- ✅ Header: avatar + name + role badge + status badge.
- ✅ Sections: Profile / Activity log / Permissions.
- ✅ Actions: Đổi role / Reset password / Vô hiệu / Xoá.

### TC-2 · Edit profile

**Expected**
- ✅ Inline edit fullName, position.
- ✅ Save → `PATCH /enterprises/users/{id}` 200.

### TC-3 · Change role

**Expected**
- ✅ Dropdown role (MANAGER/OPERATOR/ANALYST/VIEWER).
- ✅ Confirm modal nếu downgrade.

### TC-4 · Reset password

**Expected**
- ✅ `POST /enterprises/users/{id}/reset-password` → email sent toast.

### TC-5 · Deactivate

**Expected**
- ✅ Confirm modal.
- ✅ `PATCH` status="inactive".

### TC-6 · Activity log

**Expected**
- ✅ List recent logins, decisions accessed, pipelines created.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Legacy mock route. Production /p2/users/[id]. | (Future) |

## Related screens

- **UAT-EN-023** list.
- **UAT-EN-025** invite.
