# UAT-EN-040 · Reports Hub

| | |
|---|---|
| **Mã test** | UAT-EN-040 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/reports/hub` |
| **Source FE** | `frontend/components/p2/templates/46-reports-hub.tsx` |
| **Endpoint** | `GET /api/v1/reports` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (F-038) |

---

## Mục tiêu test

Hub điều hướng 4 mục: Auto reports (template-driven) / Builder (drag-drop) / Templates / Distribution (history + recipients).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render hub

**Expected**
- ✅ PageHeader "Báo cáo".
- ✅ 4 cards: Tự động · Builder · Mẫu · Phân phối.
- ✅ Recent reports list dưới.

### TC-2 · Click cards

**Expected**
- ✅ Navigate /p2/reports/{auto,builder,template,distribution}.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-041..044** sub-pages.
