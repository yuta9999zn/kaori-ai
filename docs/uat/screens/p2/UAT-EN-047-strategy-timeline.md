# UAT-EN-047 · Strategy Timeline

| | |
|---|---|
| **Mã test** | UAT-EN-047 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/strategy/timeline` |
| **Source FE** | `frontend/components/p2/templates/fnew40-strategy-timeline.tsx` |
| **Endpoint** | `GET /api/v1/strategy/timeline` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Roadmap timeline view milestones + initiatives theo quarter.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render timeline

**Expected**
- ✅ Horizontal scroll timeline với markers Q1/Q2/Q3/Q4.
- ✅ Initiatives swimlane với bars color theo status.

### TC-2 · Add milestone

**Expected**
- ✅ Click empty space → modal new milestone.

### TC-3 · Drag bar to reschedule

**Expected**
- ✅ Drag initiative bar → PATCH dates.

### TC-4 · Filter by owner / department

**Expected**
- ✅ Dropdowns.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Drag-drop reschedule Phase 2. | Edit modal manual. |

## Related screens

- **UAT-EN-045** hub.
- **UAT-EN-046** OKR.
