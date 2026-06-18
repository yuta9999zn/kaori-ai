# UAT-EN-053 · Alert Detail

| | |
|---|---|
| **Mã test** | UAT-EN-053 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/alerts/detail` (literal — alert id qua query string) |
| **Source FE** | `frontend/components/p2/templates/52-alerts-detail.tsx` |
| **Endpoint** | `GET /api/v1/alerts/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Detail 1 alert: trigger condition + data snapshot + history actions + linked decisions/insights.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Alert ID hợp lệ. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Header: severity icon + title + created/updated.
- ✅ Sections: Description / Trigger condition / Data snapshot (mini chart) / Actions history / Linked decisions/insights.

### TC-2 · Acknowledge inline

**Expected**
- ✅ Button "Xác nhận" → POST → badge update.

### TC-3 · Resolve

**Expected**
- ✅ Modal lý do → POST → redirect /p2/alerts list.

### TC-4 · Mute future

**Expected**
- ✅ Toggle "Im lặng X giờ" → POST mute rule.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-052** list.
