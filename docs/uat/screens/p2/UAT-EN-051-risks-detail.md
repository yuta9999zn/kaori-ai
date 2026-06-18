# UAT-EN-051 · Risk Detail

| | |
|---|---|
| **Mã test** | UAT-EN-051 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/risks/[riskId]` |
| **Source FE** | `frontend/components/p2/templates/f039-risks-detail.tsx` |
| **Endpoints** | `GET/PATCH/DELETE /api/v1/risks/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (BE PR #126/#140) |

---

## Mục tiêu test

Detail 1 risk: full info + history + mitigations + linked decisions + edit/delete.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Risk tồn tại. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Header: title + severity badge + owner.
- ✅ Sections: Description / Likelihood × Impact matrix / Mitigations list / Linked decisions / History timeline.

### TC-2 · Edit inline

**Expected**
- ✅ Click field → inline edit → PATCH.

### TC-3 · Add mitigation

**Expected**
- ✅ "+ Mitigation" → form → POST → list append.

### TC-4 · Delete risk

**Expected**
- ✅ Confirm modal → DELETE → redirect /p2/risks.

### TC-5 · Turbopack 500

**Expected**
- ✅ Note: `[riskId]` dynamic — dùng webpack.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. | webpack. |

## Related screens

- **UAT-EN-049** hub.
