# UAT-EN-033 · Frameworks Hub

| | |
|---|---|
| **Mã test** | UAT-EN-033 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks` |
| **Source FE** | `frontend/components/p2/templates/f034-frameworks-wired.tsx` |
| **Endpoint** | `GET /api/v1/frameworks` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (F-034) |

---

## Mục tiêu test

Hub chọn analysis framework: SWOT / 6W / 2H / Fishbone (Ishikawa) / MoM-YoY / Custom Analyst.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render hub

**Expected**
- ✅ PageHeader "Khung phân tích".
- ✅ Grid 6 cards, mỗi card icon + name + description + "Sử dụng →".

### TC-2 · Click card

**Expected**
- ✅ Navigate `/p2/frameworks/{slug}`.

### TC-3 · Custom framework

**Expected**
- ✅ Card cuối "Custom" → /p2/frameworks/custom-analyst.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-034..038** framework sub-pages.
