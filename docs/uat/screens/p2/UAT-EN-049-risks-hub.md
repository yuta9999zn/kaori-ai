# UAT-EN-049 · Risks Hub

| | |
|---|---|
| **Mã test** | UAT-EN-049 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/risks` |
| **Source FE** | `frontend/components/p2/templates/f039-risks-hub.tsx` |
| **Endpoint** | `GET /api/v1/risks?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (F-039) |

---

## Mục tiêu test

Liệt kê risks: severity / likelihood / impact / owner / status / mitigation.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Rủi ro" + button "+ Thêm risk".
- ✅ Table: Title · Severity badge · Likelihood · Owner · Status · Last reviewed · Actions.

### TC-2 · Filter severity

**Expected**
- ✅ Dropdown all / critical / high / medium / low.

### TC-3 · Click row → detail

**Expected**
- ✅ Navigate `/p2/risks/{id}` (UAT-EN-051).

### TC-4 · Add risk

**Expected**
- ✅ Modal: title + severity matrix click (likelihood × impact) + owner.
- ✅ POST → row appears.

### TC-5 · Export

**Expected**
- ✅ Link → `/p2/risks/export` (UAT-EN-050).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-050** export.
- **UAT-EN-051** detail.
