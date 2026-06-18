# UAT-EN-027 · Analysis Hub

| | |
|---|---|
| **Mã test** | UAT-EN-027 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/analysis/hub` |
| **Source FE** | `frontend/components/p2/templates/35-analyst-hub.tsx` |
| **Endpoint** | `GET /api/v1/analysis/hub` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Hub điều hướng 4 level analysis: Basic / Intermediate / Advanced / Scope. Mỗi level có description + entry button.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render hub

**Expected**
- ✅ PageHeader "Phân tích".
- ✅ Grid 4 cards (Cơ bản / Trung cấp / Nâng cao / Phạm vi) với icon + description + Vào →.

### TC-2 · Click level → sub-page

**Expected**
- ✅ /p2/analysis/basic / intermediate / advance / scope.

### TC-3 · Recent analyses sidebar

**Expected**
- ✅ Section recent runs từ analysis logs.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-028..031** sub-levels.
