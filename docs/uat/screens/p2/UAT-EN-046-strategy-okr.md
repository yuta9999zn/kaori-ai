# UAT-EN-046 · Strategy OKR

| | |
|---|---|
| **Mã test** | UAT-EN-046 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/strategy/okr` |
| **Source FE** | `frontend/components/p2/templates/fnew40-strategy-okr.tsx` |
| **Endpoint** | `GET/POST /api/v1/strategy/okr` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (P2-M212-001) |

---

## Mục tiêu test

OKR framework: tree Objectives → Key Results → Initiatives. Auto-link với KPI từ Gold tier.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render tree

**Expected**
- ✅ Heading "OKR Q1 2026".
- ✅ Tree: Objectives (icon Target gold) → Key Results (icon TrendingUp) → Initiatives (text rows).
- ✅ Progress bar per KR with current/target value + % bar color.

### TC-2 · Add objective

**Expected**
- ✅ Button "+ Objective" → modal: title + owner + quarter + KR list.
- ✅ POST 200 → tree append.

### TC-3 · Link KR to KPI

**Expected**
- ✅ Edit KR → dropdown Gold KPI → auto-track progress.

### TC-4 · OKR check-in (weekly)

**Expected**
- ✅ Section "Check-in" + form weekly update progress.

### TC-5 · Export OKR PDF

**Expected**
- ✅ Button "Xuất PDF".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-045** hub.
