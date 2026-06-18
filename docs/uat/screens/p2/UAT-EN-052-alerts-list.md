# UAT-EN-052 · Alerts List

| | |
|---|---|
| **Mã test** | UAT-EN-052 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/alerts` |
| **Source FE** | `frontend/components/p2/templates/51-alerts-list.tsx` |
| **Endpoint** | `GET /api/v1/alerts?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ (F-037) |

---

## Mục tiêu test

Liệt kê alerts đang open: severity / type / source / acknowledged / resolved.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có alerts được fire (vd quota threshold, anomaly detected). |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Cảnh báo" + filter status (all / open / acknowledged / resolved).
- ✅ Table: Severity icon (red/yellow/green) · Title · Source · Created · Status badge · Actions.

### TC-2 · Acknowledge

**Expected**
- ✅ Click ack icon → POST → badge "Đã xác nhận".

### TC-3 · Resolve

**Expected**
- ✅ Click resolve icon → modal lý do → POST → status "resolved".

### TC-4 · Click row → detail

**Expected**
- ✅ Navigate `/p2/alerts/detail?id={uuid}` (UAT-EN-053).

### TC-5 · Real-time SSE update

**Expected**
- ✅ New alert fired → table prepend row + toast notification.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-053** detail.
