# UAT-EN-019 · Chart Categories Reference

| | |
|---|---|
| **Mã test** | UAT-EN-019 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/charts/categories` |
| **Source FE** | `frontend/components/p2/templates/30-chart-categories.tsx` |
| **Endpoint** | (FE only) |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Reference catalog các chart types theo category (comparison / trend / composition / etc.). Mỗi category có examples + use case description.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render catalog

**Expected**
- ✅ PageHeader "Chart Categories".
- ✅ Grid 5-6 category sections, mỗi section title + grid chart cards.
- ✅ Mỗi card: thumbnail + name + best-for.

### TC-2 · Drill chart type

**Expected**
- ✅ Click card → modal/drawer hiện sample interactive chart + use case detail.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Phase 2 — chart engine integration với Recharts/D3. | Phase 1 stub. |

## Related screens

- **UAT-EN-018** /p2/charts/picker.
