# UAT-EN-055 · Workflows Hub (Templates + Recent)

| | |
|---|---|
| **Mã test** | UAT-EN-055 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/workflows/hub` |
| **Source FE** | `frontend/components/p2/templates/54-workflows-hub.tsx` |
| **Endpoint** | `GET /api/v1/workflows/templates` (mig 069 25 templates) |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (P2-S15) |

---

## Mục tiêu test

Hub workflow: 25 production templates (mig 069 by `industry_vertical`) + curated palette + recent custom workflows.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render templates grid

**Expected**
- ✅ PageHeader "Workflows".
- ✅ Grid 25 template cards group by industry (Retail / Finance / Manufacturing / Services / ...).
- ✅ Mỗi card: icon + name + node count + "Sử dụng template".

### TC-2 · Search template

**Expected**
- ✅ Search input filter.

### TC-3 · Use template

**Expected**
- ✅ Click "Sử dụng" → POST `/workflows` body `{template_id}` → navigate `/p2/workflows/{id}` (UAT-EN-058).

### TC-4 · Recent custom workflows

**Expected**
- ✅ Section dưới: list custom workflows team đã tạo.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-054** list.
- **UAT-EN-056** new.
