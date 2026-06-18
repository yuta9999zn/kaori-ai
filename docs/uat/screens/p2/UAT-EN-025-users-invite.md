# UAT-EN-025 · Invite User

| | |
|---|---|
| **Mã test** | UAT-EN-025 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/users/invite` |
| **Source FE** | `frontend/components/p2/templates/12-user-invite.tsx` |
| **Endpoint** | `POST /api/v1/enterprises/users/invite` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ (F-015) |

---

## Mục tiêu test

Mời user mới qua email. Form: email + fullName + role + departments (optional).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ PageHeader "Mời người mới".
- ✅ Form: Email + Họ tên + Vai trò + (Phase 2) Departments multi-select.

### TC-2 · Submit

**Expected**
- ✅ `POST /enterprises/users/invite` 200.
- ✅ Toast "Đã gửi email mời".
- ✅ Navigate /p2/users/manager.

### TC-3 · Email duplicate

**Expected**
- ✅ BE 409 → ErrorBanner "Email đã tồn tại".

### TC-4 · Bulk invite (Phase 2)

**Expected**
- ⚠️ Phase 2 feature — chưa wire.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-023** list.
