# UAT-EN-041 · Auto Reports

| | |
|---|---|
| **Mã test** | UAT-EN-041 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/reports/auto` |
| **Source FE** | `frontend/components/p2/templates/47-reports-auto.tsx` |
| **Endpoint** | `GET/POST /api/v1/reports/auto` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (F-038) |

---

## Mục tiêu test

Report tự động theo schedule (daily/weekly/monthly) từ template. Manager subscribe + recipients.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render list scheduled reports

**Expected**
- ✅ Table: Tên · Template · Schedule · Recipients · Last sent · Toggle on/off.

### TC-2 · New auto report

**Expected**
- ✅ Modal: name + template select + cron schedule + recipients (email multi) + save.

### TC-3 · Trigger now

**Expected**
- ✅ Button "Gửi ngay" → POST → toast "Đã gửi".

### TC-4 · Disable

**Expected**
- ✅ Toggle off → no auto-send.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-040** hub.
- **UAT-EN-044** distribution.
