# UAT-EN-068 · Authz Policy Simulator

| | |
|---|---|
| **Mã test** | UAT-EN-068 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/authz/simulate` |
| **Source FE** | `frontend/components/p2/templates/68-authz-simulate.tsx` |
| **Endpoint** | `POST /api/v1/authz/simulate` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Test trước khi enforce: pick user + resource + action → simulate policy decision (allow/deny + reason + missing_perms).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |
| P2 | Policy đã tạo. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Form: Subject (user select) + Resource (object select) + Action (read/write/delete).
- ✅ Button "Mô phỏng".

### TC-2 · Run simulate

**Expected**
- ✅ POST → result card: `{allow: bool, reason, policy_id, missing_perms[]}`.
- ✅ Allow → green; deny → red.

### TC-3 · Trace policy chain

**Expected**
- ✅ Section "Chuỗi đánh giá": list policies checked, kết quả từng cái.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-067** ABAC builder.
- **UAT-EN-069** audits.
