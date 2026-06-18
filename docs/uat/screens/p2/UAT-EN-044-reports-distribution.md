# UAT-EN-044 · Report Distribution History

| | |
|---|---|
| **Mã test** | UAT-EN-044 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/reports/distribution` |
| **Source FE** | `frontend/components/p2/templates/50-reports-distribution.tsx` |
| **Endpoint** | `GET /api/v1/reports/distribution?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Lịch sử distribution: report nào gửi cho ai, khi nào, status (sent/failed/pending). Resend / view fanned-out logs.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ Table: Report · Recipient · Channel (email/Telegram/Zalo) · Status · Sent at · Actions.

### TC-2 · Filter status

**Expected**
- ✅ Dropdown all / sent / failed / pending.

### TC-3 · Resend

**Expected**
- ✅ Click resend icon → POST → toast.

### TC-4 · View distribution detail

**Expected**
- ✅ Drawer hiện attempts log + error message nếu failed.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-041** auto reports.
