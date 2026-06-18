# UAT-EN-023 · Users Manager

| | |
|---|---|
| **Mã test** | UAT-EN-023 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/users/manager` (alias `/p2/users`) |
| **Source FE** | `frontend/components/p2/templates/11-user-manager.tsx` |
| **Endpoint** | `GET /api/v1/enterprises/users?cursor=&limit=` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ (F-015) |

---

## Mục tiêu test

MANAGER quản lý team trong workspace của mình: list users + role + status + last login + actions (invite / edit / reset password / deactivate).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Người dùng" + button "+ Mời người" → `/p2/users/invite`.
- ✅ Table: Avatar + Họ tên · Email · Vai trò · Trạng thái · Đăng nhập cuối · Actions.
- ✅ Role badge: MANAGER current (gold), OPERATOR info, ANALYST operational, VIEWER default.

### TC-2 · Click row → detail

**Expected**
- ✅ Navigate `/p2/users/id-detail` (legacy mock — UAT-EN-024).

### TC-3 · Search

**Expected**
- ✅ Search input filter email/name.

### TC-4 · OPERATOR vào page

**Steps**
1. Login OPERATOR.

**Expected**
- ✅ Read-only mode: không có buttons mời/edit/deactivate.

### TC-5 · Empty / loading / error

**Expected**
- ✅ Skeleton + empty state + ErrorBanner.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-024** /p2/users/id-detail.
- **UAT-EN-025** /p2/users/invite.
