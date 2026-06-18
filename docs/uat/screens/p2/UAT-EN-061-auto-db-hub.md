# UAT-EN-061 · Auto DB Hub

| | |
|---|---|
| **Mã test** | UAT-EN-061 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/auto-db` |
| **Source FE** | `frontend/components/p2/templates/61-auto-db-hub.tsx` |
| **Endpoint** | `GET /api/v1/auto-db` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Hub Auto Database: AI suggest schema từ unstructured data → auto-create tables + relationships. Form generator + quality trend.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render hub

**Expected**
- ✅ Grid 3 cards: Đề xuất schema · Sinh form · Chất lượng dữ liệu.

### TC-2 · Navigate

**Expected**
- ✅ Click → /p2/auto-db/{schema-suggestion,form-generate,quality-trend}.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-062..064** sub-pages.
