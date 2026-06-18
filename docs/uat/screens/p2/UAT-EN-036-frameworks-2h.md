# UAT-EN-036 · 2H Framework (Hindsight + Foresight)

| | |
|---|---|
| **Mã test** | UAT-EN-036 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks/2h` |
| **Source FE** | `frontend/components/p2/templates/42-frameworks-2h.tsx` |
| **Endpoint** | `POST /api/v1/frameworks/2h/generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

2H framework: looking back (Hindsight — what happened, lessons learned) + looking forward (Foresight — predictions, scenarios).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Có data lịch sử ≥ 3 tháng. |

## Test cases

### TC-1 · Render 2-panel form

**Expected**
- ✅ Layout 2 cột: Hindsight (events list) / Foresight (predictions).

### TC-2 · Generate

**Expected**
- ✅ POST → cả 2 panel populate.

### TC-3 · Timeline view

**Expected**
- ✅ Toggle list ↔ timeline view.

### TC-4 · Confidence per prediction

**Expected**
- ✅ Mỗi foresight item có confidence badge.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-033** hub.
