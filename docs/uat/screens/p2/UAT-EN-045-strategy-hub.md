# UAT-EN-045 · Strategy Hub

| | |
|---|---|
| **Mã test** | UAT-EN-045 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/strategy` |
| **Source FE** | `frontend/components/p2/templates/fnew40-strategy-hub.tsx` |
| **Endpoint** | `GET /api/v1/strategy` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Hub strategy: OKR / Timeline / Review meetings.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render hub

**Expected**
- ✅ 3 cards: OKR · Lộ trình · Họp review.
- ✅ Mỗi card có count + status summary.

### TC-2 · Navigate

**Expected**
- ✅ Click → sub-page.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-046..048** sub-pages.
